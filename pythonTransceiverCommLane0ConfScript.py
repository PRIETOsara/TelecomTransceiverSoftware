import usb.core
import usb.util
import time
import sys

class FinisarManager:
    def __init__(self, vid=0x2086, pid=0x1115):
        self.dev = usb.core.find(idVendor=vid, idProduct=pid)
        if self.dev is None:
            sys.exit("Device not found.")
        
        self.EP_OUT = 0x02
        self.EP_IN = 0x86
        self._initialize_usb()

    def _initialize_usb(self):
        try:
            if self.dev.is_kernel_driver_active(0):
                self.dev.detach_kernel_driver(0)
        except: pass
        
        self.dev.set_configuration()
        self.dev.reset()
        time.sleep(1)
        
        try:
            if self.dev.is_kernel_driver_active(0):
                self.dev.detach_kernel_driver(0)
            usb.util.claim_interface(self.dev, 0)
        except: pass

    def _send_command(self, cmd_list):
        self.dev.write(self.EP_OUT, bytes(cmd_list), timeout=5000)
        time.sleep(0.1)
        res = self.dev.read(self.EP_IN, 64)
        return bytes(res)[2:3].hex()

    def set_page(self, page_num):
        """Switches to the specified memory page (0, 3, etc.)"""
        cmd = [0x08, 0x00, 0xda, 0xa0, 0x00, 0x00, 0x00, 0x00, 
               0x08, 0x00, 0x9a, 0x7f, 0x00, 0x00, 0x00, 0x00, 
               0x08, 0x00, 0xba, page_num, 0x00, 0x00, 0x00, 0x00, 
               0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return self._send_command(cmd)

    def set_tx_dis(self, value):
        """Disable TX Lane 0 (1=Off, 0=On) - Page 00"""
        val = 1 if value >= 1 else 0
        cmd = [0x08, 0x00, 0xda, 0xa0, 0x00, 0x00, 0x00, 0x00, 
               0x08, 0x00, 0x9a, 0x56, 0x00, 0x00, 0x00, 0x00, 
               0x08, 0x00, 0xba, val, 0x00, 0x00, 0x00, 0x00, 
               0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return self._send_command(cmd)

    def set_rx_dis(self, value):
        """Disable RX Lane 0 (1=Mute, 0=Active) - Page 00"""
        val = 1 if value >= 1 else 0
        cmd = [0x08, 0x00, 0xda, 0xa0, 0x00, 0x00, 0x00, 0x00, 
               0x08, 0x00, 0x9a, 0x62, 0x00, 0x00, 0x00, 0x00, 
               0x08, 0x00, 0xba, val, 0x00, 0x00, 0x00, 0x00, 
               0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return self._send_command(cmd)

    def set_cdr_bypass_tx(self, bypass):
        """Bypass TX CDR Lane 0 (1=Bypass, 0=Active) - Page 00"""
        val = 0x00 if bypass == 1 else 0x01
        cmd = [0x08, 0x00, 0xda, 0xa0, 0x00, 0x00, 0x00, 0x00, 
               0x08, 0x00, 0x9a, 0x63, 0x00, 0x00, 0x00, 0x00, 
               0x08, 0x00, 0xba, val, 0x00, 0x00, 0x00, 0x00, 
               0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return self._send_command(cmd)

    def set_cdr_bypass_rx(self, bypass):
        """Bypass RX CDR Lane 0 (1=Bypass, 0=Active) - Page 00"""
        val = 0x00 if bypass == 1 else 0x10
        cmd = [0x08, 0x00, 0xda, 0xa0, 0x00, 0x00, 0x00, 0x00, 
               0x08, 0x00, 0x9a, 0x62, 0x00, 0x00, 0x00, 0x00, 
               0x08, 0x00, 0xba, val, 0x00, 0x00, 0x00, 0x00, 
               0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return self._send_command(cmd)

    def set_rx_amplitude(self, value):
        """Set RX Amplitude Lane 0 (0-15) - Page 03"""
        val_hex = (value & 0x0F) << 4
        cmd = [0x08, 0x00, 0xda, 0xa0, 0x00, 0x00, 0x00, 0x00, 
               0x08, 0x00, 0x9a, 0xee, 0x00, 0x00, 0x00, 0x00, 
               0x08, 0x00, 0xba, val_hex, 0x00, 0x00, 0x00, 0x00, 
               0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        return self._send_command(cmd)

# --- MAIN EXECUTION ---
def main():
    fm = FinisarManager()
    print("Finisar EUIG3 Initialized.")

    # Step 1: Page 00 Operations
    fm.set_page(0)
    print(f"TX Enable: {fm.set_tx_dis(0)}")
    print(f"RX Enable: {fm.set_rx_dis(0)}")
    print(f"CDR TX Bypass: {fm.set_cdr_bypass_tx(1)}")
    print(f"CDR RX Bypass: {fm.set_cdr_bypass_rx(1)}")

    # Step 2: Page 03 Operations
    fm.set_page(3)
    print(f"RX Amplitude (Level 5): {fm.set_rx_amplitude(6)}")

    # Step 3: Return to Page 00
    fm.set_page(0)
    print("Configuration Complete.")

if __name__ == "__main__":
    main()