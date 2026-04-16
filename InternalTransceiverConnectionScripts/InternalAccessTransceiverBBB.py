import usb.core
import usb.util
import time
import sys

# --- CONFIGURATION PARAMETERS ---
TX_DIS = [0, 0, 0, 0]           
RX_AMPLIFIER = [5, 2, 2, 2]     

class FinisarManager:
    def __init__(self, vid=0x2086, pid=0x1114):
        print(f"Searching for Device 0x{vid:04x}:0x{pid:04x}...")
        self.dev = usb.core.find(idVendor=vid, idProduct=pid)
        
        if self.dev is None:
            sys.exit("Error: Device not found. Check cables/power.")
        
        self.EP_OUT = 0x02
        self.EP_IN = 0x86
        # FIX: Corrected indentation here
        self._initialize_usb()
            
    def _initialize_usb(self):
        try:
            if self.dev.is_kernel_driver_active(0):
                print("Detaching kernel driver...")
                self.dev.detach_kernel_driver(0)
            
            try:
                self.dev.get_active_configuration()
            except usb.core.USBError:
                self.dev.set_configuration()
            
            print("Switching to Alternate Setting 1 (Unlocking Endpoints)...")
            self.dev.set_interface_altsetting(interface=0, alternate_setting=1)
            
            # CRITICAL: Settle time for BBB hardware
            time.sleep(0.8) 
            usb.util.claim_interface(self.dev, 0)
            
            self.dev.clear_halt(self.EP_OUT)
            self.dev.clear_halt(self.EP_IN)
            
            # Flush ghost data
            try:
                self.dev.read(self.EP_IN, 64, timeout=100)
            except:
                pass

            print("USB successfully initialized in Data Mode.")

        except usb.core.USBError as e:
            # FIX: Combined exception handling
            sys.exit(f"Initialization Failed: {e}. Try 'sudo' or check #EPs in usb-devices.")

    def _send_command(self, cmd_list):
        padded_cmd = cmd_list + [0] * (32 - len(cmd_list))
        try:
            self.dev.write(self.EP_OUT, bytes(padded_cmd), timeout=2000)
            time.sleep(0.15) 
            res = self.dev.read(self.EP_IN, 64, timeout=3000)
            return bytes(res)[2:3].hex() if len(res) > 2 else "00"
        except usb.core.USBError as e:
            if e.errno == 110:
                return "TIMEOUT"
            return f"ERR:{e.errno}"

    def set_page(self, page_num):
        cmd = [0x08, 0x00, 0xda, 0xa0, 0,0,0,0, 0x08, 0x00, 0x9a, 0x7f, 0,0,0,0, 0x08, 0x00, 0xba, page_num]
        return self._send_command(cmd)

    def set_tx_disable_all(self, l):
        val = (l[3] << 3) | (l[2] << 2) | (l[1] << 1) | l[0]
        cmd = [0x08, 0x00, 0xda, 0xa0, 0,0,0,0, 0x08, 0x00, 0x9a, 0x56, 0,0,0,0, 0x08, 0x00, 0xba, val]
        return self._send_command(cmd)

    def set_rx_amplitude_all(self, v):
        val_ee = ((v[0] & 0x0F) << 4) | (v[1] & 0x0F)
        val_ef = ((v[2] & 0x0F) << 4) | (v[3] & 0x0F)
        
        # FIX: Check Acks for both commands
        ack1 = self._send_command([0x08,0x00,0xda,0xa0,0,0,0,0, 0x08,0x00,0x9a,0xee,0,0,0,0, 0x08,0x00,0xba,val_ee])
        ack2 = self._send_command([0x08,0x00,0xda,0xa0,0,0,0,0, 0x08,0x00,0x9a,0xef,0,0,0,0, 0x08,0x00,0xba,val_ef])
        return f"Ack1:{ack1}, Ack2:{ack2}"

def main():
    try:
        fm = FinisarManager()
        print("Starting Configuration...")
        
        print(f"Set Page 0: {fm.set_page(0)}")
        print(f"TX Disable result: {fm.set_tx_disable_all(TX_DIS)}")
        
        print(f"Set Page 3: {fm.set_page(3)}")
        print(f"RX Amplitude result: {fm.set_rx_amplitude_all(RX_AMPLIFIER)}")
        
        fm.set_page(0)
        print("\nSuccess: Transceiver configured.")

    except Exception as e:
        print(f"\nRuntime Error: {e}")

if __name__ == "__main__":
    main()