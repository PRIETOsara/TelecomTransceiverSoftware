import usb.core
import usb.util
import sys
import time

# Vendor and Product IDs for Finisar EUI3
VID = 0x2086
PID_APP = 0x1115  # Operational mode (Firmware loaded)
PID_BOOT = 0x1114  # Bootloader mode


def main():
    print("Searching for Finisar USB board...")

    # 1. Connect to the device
    dev = usb.core.find(idVendor=VID, idProduct=PID_APP)

    if dev is None:
        if usb.core.find(idVendor=VID, idProduct=PID_BOOT):
            sys.exit("Error: Device is in Bootloader Mode (PID 1114). Firmware not loaded.")
        else:
            sys.exit("Error: Device not found. Check lsusb.")

    print(f"Success: Connected to Finisar EUI3 (VID: {hex(VID)}, PID: {hex(PID_APP)})")

    # 2. Detach Linux kernel drivers if they are holding the port
    interface_num = 0
    if dev.is_kernel_driver_active(interface_num):
        try:
            dev.detach_kernel_driver(interface_num)
            print("Detached active kernel driver.")
        except usb.core.USBError as e:
            sys.exit(f"Could not detach kernel driver: {e}")

    # 3. Set USB Configuration
    try:
        dev.set_configuration()
    except usb.core.USBError as e:
        sys.exit(f"Could not set configuration: {e}")

    usb.util.claim_interface(dev, interface_num)
    print("USB Interface claimed successfully.\n")

    """
    # =========================================================================
    # METHOD A: CONTROL TRANSFER
    # Use this if Wireshark shows "URB_CONTROL" packets to read the device.
    # =========================================================================
    print("--- Testing Control Transfer Method ---")
    try:
        # REPLACE THESE PLACEHOLDERS WITH YOUR WIRESHARK VALUES
        bmRequestType = 0x80  # 0xC0 means "Device to Host, Vendor Specific"
        bRequest = 0x06       # The custom Finisar command byte
        wValue = 0x0000       # Often used for Register Address (0x00)
        wIndex = 0x00       # Often used for I2C Address (0xA0)
        length = 1            # We want to read 1 byte

        # UNCOMMENT THE NEXT TWO LINES ONCE YOU HAVE YOUR VALUES
        response = dev.ctrl_transfer(bmRequestType, bRequest, wValue, wIndex, length)
        print(f"-> SUCCESS: Register 0x00 returned: {hex(response[0])}")

        print("(Code commented out - waiting for your Wireshark values)\n")
    except usb.core.USBError as e:
        print(f"Control transfer failed: {e}\n")

    """

    # =========================================================================
    # METHOD B: BULK TRANSFER
    # Use this if Wireshark shows "URB_BULK out" followed by "URB_BULK in".
    # =========================================================================
    print("--- Testing Bulk Transfer Method ---")
    try:
        # Find the Bulk IN and OUT endpoints
        cfg = dev.get_active_configuration()
        intf = cfg[(interface_num, 0)]
        ep_out = usb.util.find_descriptor(intf, custom_match=lambda e: usb.util.endpoint_direction(
            e.bEndpointAddress) == usb.util.ENDPOINT_OUT)
        ep_in = usb.util.find_descriptor(intf, custom_match=lambda e: usb.util.endpoint_direction(
            e.bEndpointAddress) == usb.util.ENDPOINT_IN)

        if ep_out and ep_in:
            # REPLACE THIS ARRAY WITH THE HEX PAYLOAD FROM WIRESHARK
            # Example: [Command, I2C_Address, Register, Length_to_read]
            # 31-byte Command Block Wrapper (CBW) Proposal
            # [0-3]   Signature: 'USBC' (0x55 53 42 43)
            # [4-7]   Tag: Unique ID for this command (e.g., 0x01 0x00 0x00 0x00)
            # [8-11]  Transfer Length: How many bytes you expect back
            # [12]    Flags: 0x80 for Data-In (Read), 0x00 for Data-Out (Write)
            # [13]    LUN: Logical Unit Number (usually 0x00)
            # [14]    CDB Length: Length of the actual Finisar command (usually 0x06 or 0x0A)
            # [15-30] CDB: The actual "Finisar-specific" command bytes

            magic_payload = [
                0x55, 0x53, 0x42, 0x43,  # Signature
                0x01, 0x00, 0x00, 0x00,  # Tag (increment this for each call)
                0x01, 0x00, 0x00, 0x00,  # Expecting 1 byte back (adjust based on Wireshark)
                0x80,  # Direction: In (Read)
                0x00,  # LUN
                0x06,  # CDB Length
                # --- The actual Finisar Command starts here (Example below) ---
                0x01, 0xA0, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
            ]

            try:    # Cleaning the buffer just in case
                dev.read(ep_in.bEndpointAddress, ep_in.wMaxPacketSize, timeout=10)
            except:
                pass
            # UNCOMMENT THE NEXT FOUR LINES ONCE YOU HAVE YOUR VALUES
            ep_out.write(magic_payload)
            time.sleep(0.05)  # Brief pause to let the QSFP module reply

            response = ep_in.read(64, timeout=5000) # Trying to read the QSFP module response
            print(f"-> SUCCESS: Register 0x00 returned: {hex(response[0])}")

            print("(Code commented out - waiting for your Wireshark values)\n")
        else:
            print("Could not find Bulk endpoints.")
    except usb.core.USBError as e:
        print(f"Bulk transfer failed: {e}\n")

    # 4. Clean up and release the device
    usb.util.dispose_resources(dev)
    print("Session closed cleanly.")


if __name__ == '__main__':
    main()
