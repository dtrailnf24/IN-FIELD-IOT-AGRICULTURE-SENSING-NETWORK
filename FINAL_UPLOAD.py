import requests
import json
import pandas as pd
import time
import pytz

def hex_to_decimal(val):
    try:
        return int(str(val), 16)
    except:
        return None


API_KEY = "P8S6TPVU3UG2XTVR" #VERIFY THE API KEY with the design report
CHANNEL_ID = "2897487"	#VERIFY THE ID with the design report	
URL = f"https://api.thingspeak.com/channels/{CHANNEL_ID}/bulk_update.json"
local_tz = pytz.timezone("US/Mountain")

while True:
    time.sleep(5)

    try:
        df = pd.read_csv("raw_soil_data.csv", header=None, #THIS IS AN RELATIVE PATH, CHANGE TO ABSOLUTE
                         names=["created_at", "field1", "field2", "field3", "field4", "field5", "field6", "field7"])

        data = {
            "write_api_key": API_KEY,
            "updates": []
        }
        seen_timestamps = set()
        for _, row in df.iterrows():
            try:
                dt_local = pd.to_datetime(row["created_at"])
                dt_utc = dt_local.tz_localize(local_tz).astimezone(pytz.utc)
                created_time = pd.to_datetime(row["created_at"]).strftime('%Y-%m-%dT%H:%M:%SZ')
            except Exception as e:
                print("时间格式错误，跳过此行:", row["created_at"], e)
                continue
            if created_time in seen_timestamps:
                continue
            seen_timestamps.add(created_time)
            # 转换并缩放
            val1 = hex_to_decimal(row["field1"])
            val2 = hex_to_decimal(row["field2"])
            val3 = hex_to_decimal(row["field3"])
            val4 = hex_to_decimal(row["field4"])
            val5 = hex_to_decimal(row["field5"])
            val6 = hex_to_decimal(row["field6"])
            val7 = hex_to_decimal(row["field7"])

            update = {
                "created_at": created_time,
                "field1": val1 / 10 if val1 is not None else None,
                "field2": val2 / 10 if val2 is not None else None,
                "field3": val3,
                "field4": val4 / 100 if val4 is not None else None,
                "field5": val5,
                "field6": val6,
                "field7": val7
            }

            if all(v is None or isinstance(v, (int, float)) for k, v in update.items() if k != "created_at"):
                data["updates"].append(update)
            else:
                print("跳过包含非法值的数据：", update)

        if not data["updates"]:
            print("no data")
            continue

        print("Updating datas：")
        print(json.dumps(data, indent=2))

        headers = {"Content-Type": "application/json"}
        response = requests.post(URL, headers=headers, data=json.dumps(data))

        print(f"updating statue{response.status_code} - {response.text}")

    except Exception as e:
        print("fail：", e)
