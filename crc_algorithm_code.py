
#This program is an algorithm to calculate the CRC, part of the RS485 data packet for the sensor. 
 
def calculate_crc(data):

    crc = 0xFFFF  # Start with a CRC value of 0xFFFF

    for byte in data:
        crc ^= byte  # XOR byte into CRC
        for _ in range(8):  
            if crc & 0x0001:  
                crc >>= 1 
                crc ^= 0xA001  
            else:
                crc >>= 1 

    return crc

frame = [0x01, 0x03, 0x00, 0x20, 0x00, 0x07]
crc_value = calculate_crc(frame)
crc_low = crc_value & 0xFF  # Low byte (LSB)
crc_high = (crc_value >> 8) & 0xFF  # High byte (MSB)
frame.append(crc_low)
frame.append(crc_high)
print(f"The hex string is: {frame}")