import meshtastic
import meshtastic.serial_interface
import time
import logging
import cbor2
import threading
import os
from pubsub import pub

#Please read comments for modification of the code to suit needs of project


# System Config
SERIAL_PORT = "/dev/ttyACM0"  # modify depending on OS, your best bet for finding the path is going on an online serial monitor and seeing where it is plugged in
CSV_FILE_PATH = "sample_data.csv" #This is not an absolute path, for modification of your setup make sure you use the whole path name for where you want to output it, on the UG itself it is correctly setup
LINE_DELAY = 15  # Delay between full soil sample
MAX_RETRIES = 3  # Retry attempts per chunk of soil sample
ACK_TIMEOUT = 45  # Timeout to wait for ACK, first one tends to be super long
STARTUP_DELAY = 5  # waits so we can ignore cached packets

# logging system for output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("sender.log")]
)

interface = None
latest_rssi = None
ack_event = threading.Event()

# Connect to the LoRa module
def connect_device():
    global interface
    try:
        interface = meshtastic.serial_interface.SerialInterface(SERIAL_PORT)
        logging.info("Connected to LoRa module")
        logging.info(f"Waiting {STARTUP_DELAY} seconds before transmission to avoid cache...")
        time.sleep(STARTUP_DELAY)

        # device info
        node = interface.localNode
        print(f"Serial Port: {SERIAL_PORT}")
        print(f"Device ID: {node.nodeNum}")
        print(f"Channel URL: {node.getURL()}")

        return True
    except Exception as e:
        logging.error(f"Connection failed: {e}")
        return False

# Send a chunk and wait for ACK
def send_chunk(data_part, part_num, total_parts, timestamp):
    try:
        chunk = {
            'ts': timestamp,
            'pt': part_num,
            'tp': total_parts,
            'd': data_part
        }

        encoded = cbor2.dumps(chunk)
        size_bytes = len(encoded)

        ack_event.clear()
        interface.sendData(encoded, wantAck=True)
        logging.info(f"Sent chunk {part_num}/{total_parts} | Size: {size_bytes} bytes")

        if ack_event.wait(ACK_TIMEOUT):
            logging.info(f"ACK received for chunk {part_num}")
            return True
        else:
            logging.warning(f"ACK timed out for chunk {part_num}")
            return False

    except Exception as e:
        logging.error(f" Send error: {e}")
        return False

# Sending soil sample
def send_line(line):
    try:
        fields = line.strip().split(',')
        timestamp = fields[0]

        parts = [
            {'m': fields[1], 't': fields[2]},
            {'c': fields[3], 'p': fields[4]},
            {'n': fields[5], 'ph': fields[6]},
            {'k': fields[7]}
        ]

        for part_num in range(1, len(parts) + 1):
            for retry in range(MAX_RETRIES + 1):
                if send_chunk(parts[part_num - 1], part_num, len(parts), timestamp):
                    break
                if retry < MAX_RETRIES:
                    logging.info(f"Retrying chunk {part_num} ({MAX_RETRIES - retry} left)")
                    time.sleep(2 * (retry + 1))
            else:
                logging.error(f"Failed to send chunk {part_num} after {MAX_RETRIES} retries")
                return False

        return True
    except Exception as e:
        logging.error(f"Line error: {e}")
        return False

# Delete sent lines from the CSV file to avoid over storage
def delete_sent_lines(successful_lines):
    try:
        with open(CSV_FILE_PATH, "r") as f:
            all_lines = f.readlines()

        remaining_lines = [line for line in all_lines if line not in successful_lines]

        with open(CSV_FILE_PATH, "w") as f:
            f.writelines(remaining_lines)

        logging.info(f"Deleted {len(successful_lines)} successfully sent lines")

    except Exception as e:
        logging.error(f"Error deleting lines: {e}")

# ACK handler
def on_ack_received(packet, interface=None):
    global latest_rssi
    try:
        if "decoded" not in packet or "payload" not in packet["decoded"]:
            return

        ack = packet['decoded']['payload']
        latest_rssi = packet.get("rxSnr", None)

        rssi_str = f"{latest_rssi:.1f} dBm" if latest_rssi is not None else "Unknown dBm"
        logging.info(f"ACK received: {ack.hex()} | RSSI: {rssi_str}")

        ack_event.set()

    except Exception as e:
        logging.error(f"ACK handler error: {e}")

# Power off pi
#the pi modules can also control power, and this section of code could interfere with it
def power_off_pi():
    try:
        logging.info("Powering off pi...")
        os.system("sudo shutdown now")  # shuts down the Pi
    except Exception as e:
        logging.error(f"Error powering off Raspberry Pi: {e}")

def main():
    if not connect_device():
        return

    pub.subscribe(on_ack_received, "meshtastic.receive")
    successful_lines = []

    try:
        with open(CSV_FILE_PATH, "r") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue

                if send_line(stripped):
                    successful_lines.append(line)
                    time.sleep(LINE_DELAY)
                else:
                    logging.warning(f"Failed line: {line[:50]}...")

        if successful_lines:
            delete_sent_lines(successful_lines)

        power_off_pi()  # Shutdown the Pi after processing all lines
        logging.info("Finished all lines and shutting down")

    finally:
        if interface:
            interface.close()
            logging.info("Disconnected")

if __name__ == "__main__":
    main()