import usb.core
import usb.util
import time
import sys

TX_DIS = [0,0,0,0]
RX_DIS = [0,0,0,0]
TX_SQUEILCH_DIS = [0,0,0,0]
RX_SQUEILCH_DIS = [0,0,0,0]
CDR_BYPASS_TX = [1,1,1,1]
CDR_BYPASS_RX = [1,1,1,1]
RX_AMPLIFIER = [5,2,2,2]
class FinisarManager:
    def __init__(self, vid=0x2086, pid=0x1115):
        # 1. Initialize Device
        self.dev = usb.core.find(idVendor=vid, idProduct=pid)
        if self.dev is None:
            sys.exit("Error: Finisar EUIG3 device not found. Check USB connection.")
        
        self.EP_OUT = 0x02
        self.EP_IN = 0x86
        self._initialize_usb()

    def _initialize_usb(self):
        """Prepares the USB interface for communication."""
        try:
            if self.dev.is_kernel_driver_active(0):
                self.dev.detach_kernel_driver(0)
        except: pass
        
        self.dev.set_configuration()
        self.dev.reset() 
        time.sleep(1) # Wait for hardware to stabilize after reset
        
        try:
            if self.dev.is_kernel_driver_active(0):
                self.dev.detach_kernel_driver(0)
            usb.util.claim_interface(self.dev, 0)
        except: pass

    def _send_command(self, cmd_list):
        """Internal helper to write 32-byte commands and read the Ack."""
        self.dev.write(self.EP_OUT, bytes(cmd_list), timeout=5000)
        time.sleep(0.05)
        res = self.dev.read(self.EP_IN, 64)
        return bytes(res)[2:3].hex() # Returns the Ack byte (e.g., '5a' or '00')

    def set_page(self, page_num):
        """Switches the memory bank floor (Page 00, 03, etc.)"""
        cmd = [0x08, 0x00, 0xda, 0xa0, 0x00, 0x00, 0x00, 0x00, 
               0x08, 0x00, 0x9a, 0x7f, 0x00, 0x00, 0x00, 0x00, 
               0x08, 0x00, 0xba, page_num, 0x00, 0x00, 0x00, 0x00, 
               0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return self._send_command(cmd)

    def set_tx_disable_all(self, l):
        """
        Disables TX lanes (1=Off, 0=On). 
        Register 86 uses 1 bit per lane (Bit 0=Lane 0, Bit 1=Lane 1, etc.)
        """
        val = (l[3] << 3) | (l[2] << 2) | (l[1] << 1) | l[0]
        cmd = [0x08, 0x00, 0xda, 0xa0, 0x00, 0x00, 0x00, 0x00, 
               0x08, 0x00, 0x9a, 0x56, 0x00, 0x00, 0x00, 0x00, 
               0x08, 0x00, 0xba, val, 0x00, 0x00, 0x00, 0x00, 
               0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return self._send_command(cmd)

    def set_tx_squelch_disable_all(self, s):
        """
        Disables TX Squelch (1=Squelch OFF, 0=Squelch ON).
        Note: Requires Page 03.
        Register 240 (0xF0). Bits 0-3 map to Lanes 0-3.
        """
        val = (s[3] << 3) | (s[2] << 2) | (s[1] << 1) | s[0]
        cmd = [0x08, 0x00, 0xda, 0xa0, 0x00, 0x00, 0x00, 0x00, 
               0x08, 0x00, 0x9a, 0xf0, 0x00, 0x00, 0x00, 0x00, 
               0x08, 0x00, 0xba, val, 0x00, 0x00, 0x00, 0x00, 
               0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return self._send_command(cmd)

    def set_rx_squelch_disable_all(self, s):
        """
        Disables RX Squelch (1=Squelch OFF, 0=Squelch ON).
        Note: Requires Page 03.
        Register 241 (0xF1). Bits 0-3 map to Lanes 0-3.
        """
        val = (s[3] << 3) | (s[2] << 2) | (s[1] << 1) | s[0]
        cmd = [0x08, 0x00, 0xda, 0xa0, 0x00, 0x00, 0x00, 0x00, 
               0x08, 0x00, 0x9a, 0xf1, 0x00, 0x00, 0x00, 0x00, 
               0x08, 0x00, 0xba, val, 0x00, 0x00, 0x00, 0x00, 
               0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return self._send_command(cmd)

    def set_rx_amplitude_all(self, v):
        """
        Sets unique RX Amplitude (0-15) for all 4 lanes. 
        Note: Needs Page 03.
        Reg 238 (0xEE) = Lane 0 (High Nibble) | Lane 1 (Low Nibble)
        Reg 239 (0xEF) = Lane 2 (High Nibble) | Lane 3 (Low Nibble)
        """
        # Register 238
        val_ee = ((v[0] & 0x0F) << 4) | (v[1] & 0x0F)
        # Register 239
        val_ef = ((v[2] & 0x0F) << 4) | (v[3] & 0x0F)
        
        a1 = self._send_command([0x08, 0x00, 0xda, 0xa0, 0,0,0,0, 0x08, 0x00, 0x9a, 0xee, 0,0,0,0, 0x08, 0x00, 0xba, val_ee, 0,0,0,0, 0,0,0,0, 0,0,0,0])
        a2 = self._send_command([0x08, 0x00, 0xda, 0xa0, 0,0,0,0, 0x08, 0x00, 0x9a, 0xef, 0,0,0,0, 0x08, 0x00, 0xba, val_ef, 0,0,0,0, 0,0,0,0, 0,0,0,0])
        return [a1, a2]

    def set_cdr_bypass_all(self, b):
        """
        Bypass CDR (1=Bypass/OFF, 0=Active/ON). 
        TX CDR (Reg 99) Bits 0-3. RX CDR (Reg 98) Bits 4-7.
        """
        tx_val = (b[3] << 3) | (b[2] << 2) | (b[1] << 1) | b[0]
        rx_val = (b[3] << 7) | (b[2] << 6) | (b[1] << 5) | (b[0] << 4)
        
        r1 = self._send_command([0x08, 0x00, 0xda, 0xa0, 0,0,0,0, 0x08, 0x00, 0x9a, 0x63, 0,0,0,0, 0x08, 0x00, 0xba, tx_val, 0,0,0,0, 0,0,0,0, 0,0,0,0])
        r2 = self._send_command([0x08, 0x00, 0xda, 0xa0, 0,0,0,0, 0x08, 0x00, 0x9a, 0x62, 0,0,0,0, 0x08, 0x00, 0xba, rx_val, 0,0,0,0, 0,0,0,0, 0,0,0,0])
        return [r1, r2]

def main():
    fm = FinisarManager()
    print("--- Finisar EUIG3 Multilane Controller ---")

    # Example 1: Set unique status for TX Lanes on Page 00
    fm.set_page(0)
    # Turn OFF Lane 0 and 2, keep Lane 1 and 3 ON
    ack_tx = fm.set_tx_disable_all(TX_DIS)
    print(f"TX Multi-Lane State Set. Ack: {ack_tx}")

    # Example 2: Set unique RX Amplitudes on Page 03
    fm.set_page(3)
    # L0=2, L1=5, L2=8, L3=14
    ack_rx = fm.set_rx_amplitude_all(RX_AMPLIFIER)
    print(f"RX Amplitudes (L0:2, L1:5, L2:8, L3:14) Acks: {ack_rx}")

    print(f"TX Squelch Disable: {fm.set_tx_squelch_disable_all(TX_SQUEILCH_DIS)}")
    print(f"RX Squelch Disable: {fm.set_rx_squelch_disable_all(RX_SQUEILCH_DIS)}")

    # Example 3: Set CDR Bypass on Page 00
    fm.set_page(0)
    # Bypass all CDRs for raw signal testing
    ack_cdr = fm.set_cdr_bypass_all(CDR_BYPASS_TX)
    print(f"CDR All Bypassed. Acks: {ack_cdr}")

    fm.set_page(0)
    print("\nConfiguration Complete.")

if __name__ == "__main__":
    main()