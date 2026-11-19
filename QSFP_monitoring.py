#!/usr/bin/env python3
# QSFP (SFF-8636) live monitor + control for the BBB.
# Usage: sudo python3 qsfp_rw.py
# The screen refreshes every second. Type a command and press Enter to change a value.
# Press ESC (or Ctrl+C) to quit.

import smbus
import math
import time
import curses

BUS = 2
ADDRESS = 0x50
PAGE_SELECT = 127   # byte 127 selects which upper page (128-255) is visible
REFRESH = 1.0       # seconds between readings

RX_AMP = {0: "100-400mV", 1: "300-600mV", 2: "400-800mV", 3: "600-1200mV"}

# Per-lane on/off controls: name -> (page, byte, bit of lane 1, inverted, description)
#   inverted=True means the bit in memory is a "disable" bit (1 = function OFF)
CONTROLS = {
    'txdis': (0, 86,  0, False, "Tx disable"),
    'rxdis': (3, 241, 4, False, "Rx output disable"),
    'txsq':  (3, 240, 0, True,  "Tx squelch"),
    'rxsq':  (3, 240, 4, True,  "Rx squelch"),
    'txcdr': (0, 98,  4, False, "Tx CDR"),
    'rxcdr': (0, 98,  0, False, "Rx CDR"),
}

HELP = [
    "Commands (lane = 1-4, a list like 1,3, or 'all'):",
    "  txdis|rxdis|txsq|rxsq|txcdr|rxcdr <lane> on|off     e.g. txdis 1 on",
    "  rxamp <lane> 0-3      0=100-400 1=300-600 2=400-800 3=600-1200 mV",
    "  hpclass on|off        allow power class 5-7 (byte 93 bit 2)",
    "  lpmode on|off|pin     LPMode by software, or back to the hardware pin",
    "  clear                 reset the accumulated alarms",
    "  r <page> <byte>       w <page> <byte> <value>       dump       help",
    "  ESC or Ctrl+C = quit",
]


# ---------------------------------------------------------------- low-level I2C
def read_bytes(bus, offset, length):
    data = []
    while length > 0:
        count = min(length, 32)
        chunk = bus.read_i2c_block_data(ADDRESS, offset, count)
        data.extend(chunk)
        offset += count
        length -= count
    return data

def read_page(bus, page, offset, length):
    """Read from an upper page (offset >= 128). Always returns to page 0."""
    if offset >= 128 and page != 0:
        bus.write_byte_data(ADDRESS, PAGE_SELECT, page)
        time.sleep(0.01)
    try:
        return read_bytes(bus, offset, length)
    finally:
        if offset >= 128 and page != 0:
            bus.write_byte_data(ADDRESS, PAGE_SELECT, 0)

def write_byte(bus, page, offset, value):
    """Write one byte and read it back to check it was applied."""
    if offset >= 128 and page != 0:
        bus.write_byte_data(ADDRESS, PAGE_SELECT, page)
        time.sleep(0.01)
    try:
        bus.write_byte_data(ADDRESS, offset, value & 0xFF)
        time.sleep(0.05)                       # give the module time to apply it
        readback = bus.read_byte_data(ADDRESS, offset)
    finally:
        if offset >= 128 and page != 0:
            bus.write_byte_data(ADDRESS, PAGE_SELECT, 0)
    return readback

def modify_bits(bus, page, offset, mask, bits):
    """Change only the bits in 'mask', keep the rest of the byte as it was."""
    old = read_page(bus, page, offset, 1)[0]
    new = (old & ~mask & 0xFF) | (bits & mask)
    readback = write_byte(bus, page, offset, new)
    result = "OK" if readback == new else "NOT APPLIED (read back 0x%02X)" % readback
    return "page %02Xh byte %d: 0x%02X -> 0x%02X %s" % (page, offset, old, new, result)


# ---------------------------------------------------------------- helpers
def u16(data, offset):
    return (data[offset] << 8) | data[offset + 1]

def ascii_field(data, start, length):
    return ''.join(chr(x) for x in data[start:start+length]).strip()

def parse_lanes(text):
    if text == 'all':
        return [0, 1, 2, 3]
    lanes = [int(x) - 1 for x in text.split(',')]
    if any(l < 0 or l > 3 for l in lanes):
        raise ValueError("lane must be 1-4")
    return lanes

def on_off(v):
    return "ON" if v else "off"


# ---------------------------------------------------------------- read
def status_lines(bus):
    lower = read_bytes(bus, 0, 128)
    upper = read_bytes(bus, 128, 128)
    p3 = read_page(bus, 3, 234, 8)              # page 03h bytes 234-241 (controls)

    temp = u16(lower, 22)
    if temp >= 32768:
        temp -= 65536

    lines = [
        "%s  %s  rev %s  SN %s  date %s      %s" % (
            ascii_field(upper, 20, 16), ascii_field(upper, 40, 16), ascii_field(upper, 56, 2),
            ascii_field(upper, 68, 16), ascii_field(upper, 84, 8), time.strftime("%H:%M:%S")),
        "Temperature: %.2f C    Supply voltage: %.4f V    LOS=0x%02X  Tx fault=0x%02X" % (
            temp / 256.0, u16(lower, 26) * 0.0001, lower[3], lower[4]),
        "",
        "Lane  RX power             TX bias    TxDis RxDis TxSq  RxSq  TxCDR RxCDR RxAmp",
    ]
    for lane in range(4):
        mw = u16(lower, 34 + lane * 2) * 0.0001
        dbm = "%6.2f dBm" % (10 * math.log10(mw)) if mw > 0 else "  no light"
        bias = u16(lower, 42 + lane * 2) * 0.002
        amp_byte = p3[4 + lane // 2]                       # bytes 238-239
        amp = (amp_byte >> 4) & 0xF if lane % 2 == 0 else amp_byte & 0xF
        lines.append("  %d   %.4f mW %s  %6.3f mA   %-5s %-5s %-5s %-5s %-5s %-5s %d %s" % (
            lane + 1, mw, dbm, bias,
            on_off((lower[86] >> lane) & 1),               # Tx disable
            on_off((p3[7] >> (4 + lane)) & 1),             # Rx output disable
            on_off(not (p3[6] >> lane) & 1),               # Tx squelch (stored as "disable")
            on_off(not (p3[6] >> (4 + lane)) & 1),         # Rx squelch (stored as "disable")
            on_off((lower[98] >> (4 + lane)) & 1),         # Tx CDR
            on_off((lower[98] >> lane) & 1),               # Rx CDR
            amp, RX_AMP.get(amp, "custom")))

    o193, o194 = upper[65], upper[66]                      # option bytes 193-194
    yn = lambda v: "yes" if v else "NO"
    lines += ["", "Module supports: TxSq=%s RxSq=%s RxDis=%s RxAmp=%s TxCDR=%s RxCDR=%s" % (
        yn(o194 & 0x02), yn(o194 & 0x08), yn(o194 & 0x04), yn(o193 & 0x01),
        yn(o194 & 0x80), yn(o194 & 0x40))]

    # --- power class (byte 129) and power control (byte 93)
    cls, watts = power_class(upper[1])
    b93 = lower[93]
    lpmode = ("software ON" if b93 & 2 else "software off") if b93 & 1 else "by pin"
    lines.append("Power class: %d (max %s)   High power class enable: %s   LPMode: %s   CDR present: Tx=%s Rx=%s" % (
        cls, watts, "ON" if b93 & 4 else "off", lpmode,
        yn(upper[1] & 0x08), yn(upper[1] & 0x04)))
    if cls >= 5 and not b93 & 4:
        lines.append("  !! Class %d module: it may not power up fully until you type 'hpclass on'" % cls)

    # --- alarms and flags. They clear when read, so they are accumulated until 'clear'
    for i in range(3, 15):
        STICKY[i] |= lower[i]
    s = STICKY
    lines += ["", "ALARMS (accumulated since last 'clear'):"]
    lines.append("  Temperature: %-12s  Vcc: %-12s" % (alarm_text(s[6] >> 4) or "ok", alarm_text(s[7] >> 4) or "ok"))
    lines.append("  Tx fault: %-10s  Tx LOS: %-10s  Rx LOS: %-10s" % (
        lane_list(s[4]), lane_list(s[3] >> 4), lane_list(s[3])))
    for lane in range(4):
        parts = []
        for name, base in (("Rx power", 9), ("Tx bias", 11), ("Tx power", 13)):
            b = s[base + lane // 2]
            n = (b >> 4) & 0xF if lane % 2 == 0 else b & 0xF
            if n:
                parts.append("%s %s" % (name, alarm_text(n)))
        if parts:
            lines.append("  Lane %d: %s" % (lane + 1, ", ".join(parts)))
    return lines

STICKY = [0] * 128

def power_class(b129):
    """Decode byte 129 -> (class number, max power)."""
    if b129 & 0x20:
        return 8, "see byte 107"
    if b129 & 0x03:
        c = 4 + (b129 & 0x03)
        return c, {5: "4.0 W", 6: "4.5 W", 7: "5.0 W"}[c]
    c = 1 + (b129 >> 6)
    return c, {1: "1.5 W", 2: "2.0 W", 3: "2.5 W", 4: "3.5 W"}[c]

def alarm_text(n):
    """Alarm nibble: bit3 high alarm, bit2 low alarm, bit1 high warning, bit0 low warning."""
    names = [t for bit, t in ((8, "HIGH ALARM"), (4, "LOW ALARM"), (2, "high warn"), (1, "low warn")) if n & bit]
    return "/".join(names)

def lane_list(bits):
    lanes = [str(l + 1) for l in range(4) if (bits >> l) & 1]
    return "lanes " + ",".join(lanes) if lanes else "none"


# ---------------------------------------------------------------- write
def set_control(bus, name, lanes, turn_on):
    page, offset, first_bit, inverted, desc = CONTROLS[name]
    mask = 0
    for lane in lanes:
        mask |= 1 << (first_bit + lane)
    bit_value = turn_on != inverted          # for "disable" bits, ON means writing 0
    return "%s %s: %s" % (desc, on_off(turn_on), modify_bits(bus, page, offset, mask, mask if bit_value else 0))

def set_rx_amp(bus, lanes, value):
    if not 0 <= value <= 15:
        raise ValueError("value must be 0-15 (normally 0-3)")
    for lane in lanes:
        offset = 238 + lane // 2                 # lanes 1,2 in byte 238; lanes 3,4 in 239
        if lane % 2 == 0:
            msg = modify_bits(bus, 3, offset, 0xF0, value << 4)   # lanes 1 and 3: upper nibble
        else:
            msg = modify_bits(bus, 3, offset, 0x0F, value)        # lanes 2 and 4: lower nibble
    return "Rx amplitude %d: %s" % (value, msg)

def run_command(bus, line):
    a = line.split()
    cmd = a[0].lower()
    if cmd in CONTROLS:
        return set_control(bus, cmd, parse_lanes(a[1]), a[2].lower() == 'on')
    if cmd == 'rxamp':
        return set_rx_amp(bus, parse_lanes(a[1]), int(a[2], 0))
    if cmd == 'hpclass':                         # byte 93 bit 2: allow power class 5-7
        on = a[1].lower() == 'on'
        return "High power class %s: %s" % (on_off(on), modify_bits(bus, 0, 93, 0x04, 0x04 if on else 0))
    if cmd == 'lpmode':                          # byte 93 bits 0-1: software LPMode override
        bits = {'on': 0x03, 'off': 0x01, 'pin': 0x00}[a[1].lower()]
        return "LPMode %s: %s" % (a[1], modify_bits(bus, 0, 93, 0x03, bits))
    if cmd == 'clear':
        STICKY[:] = [0] * 128
        return "Alarms cleared"
    if cmd == 'r':
        page, offset = int(a[1], 0), int(a[2], 0)
        return "page %02Xh byte %d = 0x%02X" % (page, offset, read_page(bus, page, offset, 1)[0])
    if cmd == 'w':
        page, offset, value = int(a[1], 0), int(a[2], 0), int(a[3], 0)
        return "written 0x%02X, read back 0x%02X" % (value, write_byte(bus, page, offset, value))
    if cmd == 'dump':
        data = read_bytes(bus, 0, 128) + read_bytes(bus, 128, 128) + read_page(bus, 3, 128, 128)
        with open("qsfp_dump.bin", "wb") as f:
            f.write(bytearray(data))
        return "Saved qsfp_dump.bin (%d bytes)" % len(data)
    return "Unknown command. Type 'help'."


# ---------------------------------------------------------------- live screen
def main(screen):
    bus = smbus.SMBus(BUS)
    screen.timeout(100)              # check the keyboard every 100 ms
    typed, message, show_help = "", "Type a command and press Enter. ESC = quit.", False
    lines, next_read = [], 0

    while True:
        # 1) read the module once per second
        if time.time() >= next_read:
            try:
                lines = status_lines(bus)
            except IOError as e:
                lines = ["I2C error: %s  (is the module inserted?)" % e]
            next_read = time.time() + REFRESH

        # 2) draw the screen
        screen.erase()
        height, width = screen.getmaxyx()
        for y, text in enumerate((lines + ([""] + HELP if show_help else []))[:height - 3]):
            screen.addnstr(y, 0, text, width - 1)
        screen.addnstr(height - 2, 0, message, width - 1, curses.A_BOLD)
        screen.addnstr(height - 1, 0, "qsfp> " + typed, width - 1)
        screen.refresh()

        # 3) handle the keyboard
        key = screen.getch()
        if key == 27:                                  # ESC -> quit
            break
        elif key in (10, 13):                          # Enter -> run the command
            if typed.strip() == 'help':
                show_help = not show_help
            elif typed.strip():
                try:
                    message = run_command(bus, typed.strip())
                except (ValueError, IndexError) as e:
                    message = "Bad command (%s). Type 'help'." % e
                except IOError as e:
                    message = "I2C error: %s" % e
                next_read = 0                          # refresh now to show the new value
            typed = ""
        elif key in (8, 127, curses.KEY_BACKSPACE):    # Backspace
            typed = typed[:-1]
        elif 32 <= key < 127:                          # normal character
            typed += chr(key)

    bus.close()

if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass