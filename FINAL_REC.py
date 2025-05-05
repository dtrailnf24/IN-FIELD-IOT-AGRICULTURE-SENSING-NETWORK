import meshtastic
import meshtastic.serial_interface
import time
import logging
import cbor2
import os
import csv
from pubsub import pub
from collections import defaultdict

# receive processing errors on receive typically come from random LoRa packets, you can probably ignore these
# ignored packets are also the same deal
# the system can receive multiple chunks from different packets at the same time, so don't worry about that

#The way the code is automated, are through the cron service, type "sudo crontab -e" on the terminal to find them
#Logs of each of the pieces of code also exist on each system, and are created with the the cronjobs


# system config
SERIAL_PORT = "/dev/cu.usbmodem48CA433E0ED01"  # CHANGE DEPENDING ON OS, open online serial monitor to find port
OUTPUT_FILE_PATH = "/Users/napahat_/Desktop/received_data.csv"  # change for final system or if on different one, MAKE SURE PATH IS ABSOLUTE OR THE CRONJOB BREAKS
CHANNEL_ID = 0

# logging system for output
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

interface = None
buffer = defaultdict(dict)

def init_csv():
    # >>> Creates the CSV file with headers if it doesn't already exist
    if not os.path.exists(OUTPUT_FILE_PATH):
        with open(OUTPUT_FILE_PATH, "w") as f:
            writer = csv.writer(f)
            writer.writerow([
                "timestamp", "moisture", "temperature",
                "conductivity", "ph", "nitrogen",
                "phosphorus", "potassium"
            ])

def process_complete_line(timestamp):
    try:
        parts = buffer[timestamp]

        # Ensure all 4 parts exist
        expected_parts = [1, 2, 3, 4]
        if not all(p in parts for p in expected_parts):
            logging.warning(f"Missing parts for timestamp {timestamp}: {sorted(parts.keys())}")
            return False

        # Validate keys in each part
        required_keys = {
            1: ['m', 't'],
            2: ['c', 'p'],
            3: ['n', 'ph'],
            4: ['k']
        }

        for part_num, keys in required_keys.items():
            data = parts.get(part_num)
            if not isinstance(data, dict) or not all(k in data for k in keys):
                logging.warning(f"Malformed or missing keys in chunk {part_num} for timestamp {timestamp}")
                return False

        # Reconstruct original fields
        line_data = {
            'timestamp': timestamp,
            'moisture': parts[1]['m'],
            'temperature': parts[1]['t'],
            'conductivity': parts[2]['c'],
            'ph': parts[2]['p'],
            'nitrogen': parts[3]['n'],
            'phosphorus': parts[3]['ph'],
            'potassium': parts[4]['k']
        }

        # Append the reconstructed data to the CSV file
        with open(OUTPUT_FILE_PATH, "a") as f:
            writer = csv.writer(f)
            writer.writerow([
                line_data['timestamp'],
                line_data['moisture'],
                line_data['temperature'],
                line_data['conductivity'],
                line_data['ph'],
                line_data['nitrogen'],
                line_data['phosphorus'],
                line_data['potassium']
            ])

        logging.info(f"Saved: {timestamp}")
        del buffer[timestamp]  # >>> Clean up buffer
        return True

    except Exception as e:
        logging.error(f"Save error for ts={timestamp}: {e}")
        return False

def on_receive(packet, interface):
    try:
        if "decoded" not in packet or "payload" not in packet["decoded"]:
            return

        rssi = packet.get("rxSnr", 0)
        payload = bytes(packet["decoded"]["payload"])

        if len(payload) <= 6:
            logging.info(f"Ignored packet (size: {len(payload)} bytes) - too small")
            return

        try:
            chunk = cbor2.loads(payload)
        except Exception as e:
            logging.error(f"CBOR decode error: {e} (RSSI: {rssi:.1f} dBm)")
            return

        timestamp = chunk.get('ts')
        part_num = chunk.get('pt')
        part_data = chunk.get('d')
        total_parts = chunk.get('tp')

        if None in (timestamp, part_num, part_data, total_parts):
            logging.warning("Incomplete chunk, skipping")
            return

        buffer[timestamp][part_num] = part_data
        logging.info(f" Received chunk {part_num}/{total_parts} for ts={timestamp} (RSSI: {rssi:.1f} dBm)")

        if len(buffer[timestamp]) == total_parts:
            if process_complete_line(timestamp):
                interface.sendText("COMPLETE", destinationId=packet["from"])
            else:
                interface.sendText("ERROR", destinationId=packet["from"])

    except Exception as e:
        logging.error(f"Receive processing error: {e}")

def main():
    global interface
    init_csv()

    try:
        interface = meshtastic.serial_interface.SerialInterface(SERIAL_PORT)
        logging.info("Connected to LoRa Module")
        logging.info("Waiting 5 seconds to ignore initial packets...")
        time.sleep(5)

        # Show basic info that works
        node = interface.localNode
        print(f"Serial Port: {SERIAL_PORT}")
        print(f"Device ID: {node.nodeNum}")
        print(f"Channel URL: {node.getURL()}")

    except Exception as e:
        logging.error(f"Connection failed: {e}")
        return

    pub.subscribe(on_receive, "meshtastic.receive")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info("Stopped by user")
    finally:
        interface.close()
        logging.info("Disconnected")


if __name__ == "__main__":
    main()
