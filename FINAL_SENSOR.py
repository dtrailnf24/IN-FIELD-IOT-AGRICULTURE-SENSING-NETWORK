import RPi.GPIO as GPIO
import serial
import time
from datetime import datetime

MODE = 0
if MODE == 1:
    EN_485 = 4
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(EN_485, GPIO.OUT)
    GPIO.output(EN_485, GPIO.HIGH)

# Init
ser = serial.Serial("/dev/ttyAMA0", 9600, timeout=2) #verify path is using on different hardware

def send_command(command_bytes):
    """ Send Modbus command and return the response """
    try:
        ser.write(command_bytes)
        ser.flush()
        time.sleep(0.1)

        response = ser.read(ser.in_waiting)
        if response:
            return response
        else:
            return None
    except Exception as e:
        return None

def read_moisture_and_temp():
    """ Read soil moisture and temperature from a single command """
    command = bytes.fromhex("01 03 00 12 00 02 64 0E")
    response = send_command(command)
    if response and len(response) >= 5:
        moisture = (response[3] << 8 | response[4])
        temperature = (response[5] << 8 | response[6])
        return moisture, temperature
    return None, None

def read_conductivity():
    """ Read soil conductivity """
    command = bytes.fromhex("01 03 00 15 00 01 95 CE")
    response = send_command(command)
    if response and len(response) >= 5:
        conductivity = (response[3] << 8 | response[4])
        return conductivity
    return None

def read_ph():
    """ Read soil pH """
    command = bytes.fromhex("01 03 00 06 00 01 64 0B")
    response = send_command(command)
    if response and len(response) >= 5:
        ph = (response[3] << 8 | response[4])
        return ph
    return None

def read_npk():
    """ Read soil NPK values """
    command = bytes.fromhex("01 03 00 1E 00 03 65 CD")
    response = send_command(command)
    if response and len(response) >= 9:
        nitrogen = response[3] << 8 | response[4]
        phosphorus = response[5] << 8 | response[6]
        potassium = response[7] << 8 | response[8]
        return nitrogen, phosphorus, potassium
    return None, None, None

# Main
while True:
    t=1 # Time delay to sleep
    try:
        moisture, temperature = read_moisture_and_temp()
        conductivity = read_conductivity()
        ph = read_ph()
        nitrogen, phosphorus, potassium = read_npk()
        now=datetime.now()
        timestamp = f"{now.year}/{now.month}/{now.day} {now.hour:02}:{now.minute:02}"
        with open("sensor_log.txt", "a") as log_file: #THIS PATH IS RELATIVE, MAKE SURE IT IS ABSOLUTE IN USE
            log_file.write(f"{timestamp},{moisture:04X},{temperature:04X},{conductivity:04X},{ph:04X},{nitrogen:04X},{phosphorus:04X},)        
            time.sleep(t)

    except KeyboardInterrupt: #For manual exit
        break
    break #Remove this break and adjust t to have device periodically measure

if MODE == 1:
    GPIO.cleanup()