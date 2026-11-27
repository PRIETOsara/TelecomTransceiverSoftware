#!/usr/bin/env bash
set -euo pipefail

mode="${1:-all}"   # all | out | in

pins_out=(P8_43 P8_44 P8_45 P8_46)  # PRU1 -> R30
pins_in=(P9_28 P9_29 P9_30 P9_31)   # PRU0 -> R31

do_out() { for p in "${pins_out[@]}"; do config-pin "$p" pruout; done; }
do_in()  { for p in "${pins_in[@]}";  do config-pin "$p" pruin;  done; }

case "$mode" in
  all) do_out; do_in ;;
  out) do_out ;;
  in)  do_in ;;
  *)   echo "Uso: $0 [all|out|in]"; exit 1 ;;
esac

echo "--- Estado ---"
for p in "${pins_out[@]}"; do config-pin -q "$p" || true; done
for p in "${pins_in[@]}";  do config-pin -q "$p" || true; done

echo "--- Configuring I2C_2 ---"
sudo config-pin P9_19 i2c 2>/dev/null || true   # SCL_2
sudo config-pin P9_20 i2c 2>/dev/null || true   # SDA_2

# ---1. First step go to page 00
i2cset -y 2 0x50 127 0         2>/dev/null || true   # Back to Page 0

# Force into low power mode first (usually clears some temporary states)
i2cset -y 2 0x50 93 0x01
sleep 0.5
# Then set to high power mode
#i2cset -y 2 0x50 93 0x00
#sleep 1

# ---- 1. Disable CDR (Page 0, Byte 98) --------------------------------------
i2cset -y 2 0x50 98 0x00       2>/dev/null || true

# ---- 2. Gain & Squelch (Page 3) -------------------------------------------
i2cset -y 2 0x50 127 0x03         2>/dev/null || true   # Select Page 3

# TX Gain / Input Equalization (Bytes 234 & 235)
i2cset -y 2 0x50 234 0x00      2>/dev/null || true
i2cset -y 2 0x50 235 0x00      2>/dev/null || true

# RX Gain / Output Amplitude (Bytes 238 & 239)
# CHANGE: Use 0x33 (Max valid amplitude for both channels) instead of 0x44
i2cset -y 2 0x50 238 0x33      2>/dev/null || true  
i2cset -y 2 0x50 239 0x33      2>/dev/null || true  

# Rate select
i2cset -y 2 0x50 87 0x00    2>/dev/null || true   # RX: all 4 lanes set to lowest rate
i2cset -y 2 0x50 88 0x00  2>/dev/null || true    # TX: all 4 lanes set to lowest rate

# Disable squelch
i2cset -y 2 0x50 240 0xFF      2>/dev/null || true

# -----High power class set to consume maximum 3.5 W
old=$(i2cget -y 2 0x50 93)
new=$((old | 0x0C))
i2cset -y 2 0x50 93 $new

# ---- 3. Back to Page 0 & Enable Lasers / High Power -----------------------
i2cset -y 2 0x50 127 0         2>/dev/null || true   # Back to Page 0
i2cset -y 2 0x50 86 0x00       2>/dev/null || true   # Enable all 4 TX lasers (0x00 = ON)
i2cset -y 2 0x50 93 0x00       2>/dev/null || true   # High Power Mode ON


# ----- Missing registers ------------
# ---- PAGE 00h ----
i2cset -y 2 0x50 127 0x00     2>/dev/null || true

# LPMode / signal configuration
i2cset -y 2 0x50 99 0x00      2>/dev/null || true

# Interrupt masks
for reg in 100 101 102 103 104; do
    i2cset -y 2 0x50 "$reg" 0x00    2>/dev/null || true
done

# ---- PAGE 03h ----
i2cset -y 2 0x50 127 0x03     2>/dev/null || true

# Optional FEC control
i2cset -y 2 0x50 230 0x00     2>/dev/null || true

# Tx Forced Squelch
i2cset -y 2 0x50 231 0x00     2>/dev/null || true

# Rx Output Emphasis
i2cset -y 2 0x50 236 0x3F     2>/dev/null || true
i2cset -y 2 0x50 237 0x3F     2>/dev/null || true

# Rx Output Disable
i2cset -y 2 0x50 241 0x00     2>/dev/null || true

# Return to Page 00h
i2cset -y 2 0x50 127 0x00     2>/dev/null || true