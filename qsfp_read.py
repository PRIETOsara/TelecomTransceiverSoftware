
#!/usr/bin/env python3

import smbus
import math

BUS = 2
ADDRESS = 0x50

def read_bytes(bus, offset, length):
    data = []
    while length > 0:
        count = min(length, 32)
        chunk = bus.read_i2c_block_data(ADDRESS, offset, count)
        data.extend(chunk)
        offset += count
        length -= count
    return data

def u16(data, offset):
    return (data[offset] << 8) | data[offset + 1]

def ascii_field(data, start, length):
    return ''.join(chr(x) for x in data[start:start+length]).strip()

def main():
    bus = smbus.SMBus(BUS)

    print("Reading QSFP module...")
    lower = read_bytes(bus, 0, 128)
    upper = read_bytes(bus, 128, 128)
    bus.close()

    with open("qsfp_dump.bin", "wb") as f:
        f.write(bytearray(lower + upper))

    print("\n--- MODULE IDENTIFICATION ---")
    print("Identifier: 0x%02X" % upper[0])
    print("Vendor:     %s" % ascii_field(upper, 20, 16))
    print("Part:       %s" % ascii_field(upper, 40, 16))
    print("Revision:   %s" % ascii_field(upper, 56, 2))
    print("Serial:     %s" % ascii_field(upper, 68, 16))
    print("Date:       %s" % ascii_field(upper, 84, 8))

    print("\n--- STATUS ---")
    print("Status byte 1: 0x%02X" % lower[1])
    print("Status byte 2: 0x%02X" % lower[2])

    print("\n--- ELECTRICAL MONITORS ---")

    temp = u16(lower, 22)
    if temp >= 32768:
        temp -= 65536
    temperature = temp / 256.0

    voltage = u16(lower, 26) * 0.0001

    print("Temperature: %.2f C" % temperature)
    print("Supply voltage: %.4f V" % voltage)

    print("\n--- RX OPTICAL POWER ---")
    for lane in range(4):
        value = u16(lower, 34 + lane * 2)
        power_mw = value * 0.0001

        if power_mw > 0:
            power_dbm = 10 * math.log10(power_mw)
            print("RX lane %d: %.4f mW / %.2f dBm" %
                  (lane + 1, power_mw, power_dbm))
        else:
            print("RX lane %d: no measurable power" % (lane + 1))

    print("\n--- TX LASER BIAS ---")
    for lane in range(4):
        value = u16(lower, 42 + lane * 2)
        bias = value * 0.002
        print("TX lane %d: %.3f mA" % (lane + 1, bias))

    print("\n--- RAW LOWER MEMORY ---")
    for i in range(0, 128, 16):
        print("%03d: %s" %
              (i, ' '.join("%02X" % x for x in lower[i:i+16])))

    print("\n--- RAW UPPER MEMORY ---")
    for i in range(0, 128, 16):
        print("%03d: %s" %
              (128+i, ' '.join("%02X" % x for x in upper[i:i+16])))

    print("\nRaw EEPROM saved to qsfp_dump.bin")
    print("Done.")

if __name__ == "__main__":
    try:
        main()
    except IOError as e:
        print("I2C error: %s" % e)

