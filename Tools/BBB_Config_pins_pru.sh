#!/usr/bin/env bash
set -euo pipefail

mode="${1:-all}"   # all | out | in

pins_out=(P8_43 P8_44 P8_45 P8_46)  # PRU1 -> R30
pins_in=(P9_28 P9_29 P9_30 P9_31)   # PRU0 -> R31 (doble bola 41/42)

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

# QSFP control sequence — OFS QSFP-LR4-40G on BeagleBone (bus 2, addr 0x50)
# Every line tolerates failure: 2>/dev/null || true
# SCL_2 / SDA_2 = I2C bus 2 clock/data; P0/P3 = register page; TX/RX = optical path

# ---- 1. CDR (Page 0, Byte 98) --------------------------------------
i2cset -y 2 0x50 98 0x00      2>/dev/null || true   # SCL_2/SDA_2 P0 b98=0x00  TX+RX CDR off
#i2cget -y 2 0x50 98           2>/dev/null || true   # SCL_2/SDA_2 verify (expect 0x00)

# ---- 2. Squelch (Page 3, Byte 240) --------------------------------
# NOTE: opt194=0x00 on this module => squelch NOT implemented. Harmless no-op.
i2cset -y 2 0x50 127 3        2>/dev/null || true   # SCL_2/SDA_2 P0->P3 select
i2cset -y 2 0x50 240 0xFF     2>/dev/null || true   # SCL_2/SDA_2 P3 b240=0xFF (squelch "off", inverted)
i2cset -y 2 0x50 127 0        2>/dev/null || true   # SCL_2/SDA_2 P3->P0 restore

# ---- 3. Power Mode (Page 0, Byte 93) ---------------------------------------
# NOTE: Let the hardware LPMode pin keep the module in low power.
i2cset -y 2 0x50 93 0x00      2>/dev/null || true   # SCL_2/SDA_2 P0 b93=0x00  HW pin controls LPMode (prevents voltage sag)

i2cset -y 2 0x50 93 0x00 2>/dev/null || true