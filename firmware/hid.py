"""USB HID Keyboard for Pico W.

Configures the Pico W as a composite CDC+HID USB device.
CDC is handled by MicroPython's built-in driver (preserves REPL).
HID keyboard is handled by this module.

This module is imported from boot.py so USB descriptors are
configured before the USB subsystem initializes.
"""

import machine
import struct
import asyncio

# --- USB HID Report Descriptor (standard 6-key rollover keyboard) ---
_REPORT_DESC = bytes([
    0x05, 0x01,        # Usage Page (Generic Desktop)
    0x09, 0x06,        # Usage (Keyboard)
    0xA1, 0x01,        # Collection (Application)
    0x05, 0x07,        #   Usage Page (Keyboard/Keypad)
    0x19, 0xE0,        #   Usage Minimum (Left Control)
    0x29, 0xE7,        #   Usage Maximum (Right GUI)
    0x15, 0x00,        #   Logical Minimum (0)
    0x25, 0x01,        #   Logical Maximum (1)
    0x75, 0x01,        #   Report Size (1)
    0x95, 0x08,        #   Report Count (8)
    0x81, 0x02,        #   Input (Data, Variable, Absolute) - Modifier byte
    0x95, 0x01,        #   Report Count (1)
    0x75, 0x08,        #   Report Size (8)
    0x81, 0x01,        #   Input (Constant) - Reserved byte
    0x95, 0x06,        #   Report Count (6)
    0x75, 0x08,        #   Report Size (8)
    0x15, 0x00,        #   Logical Minimum (0)
    0x25, 0x65,        #   Logical Maximum (101)
    0x05, 0x07,        #   Usage Page (Keyboard/Keypad)
    0x19, 0x00,        #   Usage Minimum (0)
    0x29, 0x65,        #   Usage Maximum (101)
    0x81, 0x00,        #   Input (Data, Array) - 6 key codes
    0xC0,              # End Collection
])

# --- USB Descriptors for Composite CDC + HID Device ---
# Device Descriptor (18 bytes)
_DEV_DESC = bytes([
    0x12,              # bLength
    0x01,              # bDescriptorType (Device)
    0x00, 0x02,        # bcdUSB (2.00)
    0xEF,              # bDeviceClass (Miscellaneous - composite with IAD)
    0x02,              # bDeviceSubClass (Common Class)
    0x01,              # bDeviceProtocol (Interface Association Descriptor)
    0x40,              # bMaxPacketSize0 (64)
    0x09, 0x12,        # idVendor (0x1209 - pid.codes open source)
    0xDE, 0xC0,        # idProduct (0xC0DE)
    0x00, 0x01,        # bcdDevice (1.00)
    0x01,              # iManufacturer (string index 1)
    0x02,              # iProduct (string index 2)
    0x00,              # iSerialNumber (none)
    0x01,              # bNumConfigurations
])

# Configuration Descriptor: CDC (IAD + Comm Itf + Data Itf) + HID Interface
# Total length: 9+8+9+5+5+4+5+7+9+7+7+9+9+7 = 100
_CFG_DESC = bytes([
    # Configuration Descriptor Header (9 bytes)
    0x09,              # bLength
    0x02,              # bDescriptorType (Configuration)
    0x64, 0x00,        # wTotalLength (100)
    0x03,              # bNumInterfaces (CDC Comm + CDC Data + HID)
    0x01,              # bConfigurationValue
    0x00,              # iConfiguration
    0x80,              # bmAttributes (Bus powered)
    0xFA,              # bMaxPower (500mA)

    # --- CDC: Interface Association Descriptor (8 bytes) ---
    0x08,              # bLength
    0x0B,              # bDescriptorType (IAD)
    0x00,              # bFirstInterface (0)
    0x02,              # bInterfaceCount (2: Comm + Data)
    0x02,              # bFunctionClass (CDC)
    0x02,              # bFunctionSubClass (ACM)
    0x00,              # bFunctionProtocol
    0x00,              # iFunction

    # --- CDC Communication Interface (interface 0) ---
    0x09,              # bLength
    0x04,              # bDescriptorType (Interface)
    0x00,              # bInterfaceNumber (0)
    0x00,              # bAlternateSetting
    0x01,              # bNumEndpoints (1 - notification)
    0x02,              # bInterfaceClass (CDC)
    0x02,              # bInterfaceSubClass (ACM)
    0x00,              # bInterfaceProtocol
    0x00,              # iInterface

    # CDC Header Functional Descriptor (5 bytes)
    0x05,              # bLength
    0x24,              # bDescriptorType (CS_INTERFACE)
    0x00,              # bDescriptorSubtype (Header)
    0x10, 0x01,        # bcdCDC (1.10)

    # CDC Call Management Functional Descriptor (5 bytes)
    0x05,              # bLength
    0x24,              # bDescriptorType (CS_INTERFACE)
    0x01,              # bDescriptorSubtype (Call Management)
    0x00,              # bmCapabilities
    0x01,              # bDataInterface (1)

    # CDC Abstract Control Management Functional Descriptor (4 bytes)
    0x04,              # bLength
    0x24,              # bDescriptorType (CS_INTERFACE)
    0x02,              # bDescriptorSubtype (ACM)
    0x02,              # bmCapabilities (line coding + serial state)

    # CDC Union Functional Descriptor (5 bytes)
    0x05,              # bLength
    0x24,              # bDescriptorType (CS_INTERFACE)
    0x06,              # bDescriptorSubtype (Union)
    0x00,              # bControlInterface (0)
    0x01,              # bSubordinateInterface0 (1)

    # CDC Notification Endpoint (7 bytes)
    0x07,              # bLength
    0x05,              # bDescriptorType (Endpoint)
    0x82,              # bEndpointAddress (IN 2)
    0x03,              # bmAttributes (Interrupt)
    0x08, 0x00,        # wMaxPacketSize (8)
    0x10,              # bInterval (16ms)

    # --- CDC Data Interface (interface 1) ---
    0x09,              # bLength
    0x04,              # bDescriptorType (Interface)
    0x01,              # bInterfaceNumber (1)
    0x00,              # bAlternateSetting
    0x02,              # bNumEndpoints (2 - bulk in/out)
    0x0A,              # bInterfaceClass (CDC Data)
    0x00,              # bInterfaceSubClass
    0x00,              # bInterfaceProtocol
    0x00,              # iInterface

    # CDC Data OUT Endpoint (7 bytes)
    0x07,              # bLength
    0x05,              # bDescriptorType (Endpoint)
    0x01,              # bEndpointAddress (OUT 1)
    0x02,              # bmAttributes (Bulk)
    0x40, 0x00,        # wMaxPacketSize (64)
    0x00,              # bInterval

    # CDC Data IN Endpoint (7 bytes)
    0x07,              # bLength
    0x05,              # bDescriptorType (Endpoint)
    0x81,              # bEndpointAddress (IN 1)
    0x02,              # bmAttributes (Bulk)
    0x40, 0x00,        # wMaxPacketSize (64)
    0x00,              # bInterval

    # --- HID Interface (interface 2) ---
    0x09,              # bLength
    0x04,              # bDescriptorType (Interface)
    0x02,              # bInterfaceNumber (2)
    0x00,              # bAlternateSetting
    0x01,              # bNumEndpoints (1 - interrupt in)
    0x03,              # bInterfaceClass (HID)
    0x01,              # bInterfaceSubClass (Boot Interface)
    0x01,              # bInterfaceProtocol (Keyboard)
    0x00,              # iInterface

    # HID Descriptor (9 bytes)
    0x09,              # bLength
    0x21,              # bDescriptorType (HID)
    0x11, 0x01,        # bcdHID (1.11)
    0x00,              # bCountryCode
    0x01,              # bNumDescriptors
    0x22,              # bDescriptorType (Report)
    len(_REPORT_DESC) & 0xFF, len(_REPORT_DESC) >> 8,  # wDescriptorLength

    # HID Interrupt IN Endpoint (7 bytes)
    0x07,              # bLength
    0x05,              # bDescriptorType (Endpoint)
    0x83,              # bEndpointAddress (IN 3)
    0x03,              # bmAttributes (Interrupt)
    0x08, 0x00,        # wMaxPacketSize (8)
    0x0A,              # bInterval (10ms)
])

# HID endpoint address
_HID_EP_IN = 0x83
_HID_ITF_NUM = 2

# Module-level state set by USB callbacks
_ep_in = None
_is_ready = False


def _open_itf_cb(desc):
    global _ep_in, _is_ready
    # desc is a memoryview into _CFG_DESC for one interface/IAD.
    # Check if this is our HID interface (bInterfaceClass == 0x03).
    if len(desc) >= 9 and desc[0] == 0x09 and desc[1] == 0x04:
        if desc[5] == 0x03:  # HID class
            # Walk to find the endpoint descriptor
            offset = 0
            while offset < len(desc) - 1:
                d_len = desc[offset]
                d_type = desc[offset + 1]
                if d_type == 0x05:  # Endpoint descriptor
                    _ep_in = desc[offset + 2]  # bEndpointAddress
                    _is_ready = True
                    return
                offset += d_len


def _reset_cb():
    global _ep_in, _is_ready
    _ep_in = None
    _is_ready = False


def _control_xfer_cb(stage, request):
    """Handle USB control transfers for HID interface."""
    # request is a memoryview of 8 bytes: bmRequestType, bRequest, wValue, wIndex, wLength
    bmRequestType = request[0]
    bRequest = request[1]
    wValue = request[2] | (request[3] << 8)
    wIndex = request[4] | (request[5] << 8)
    wLength = request[6] | (request[7] << 8)

    if stage == 1:  # SETUP stage
        # GET_DESCRIPTOR (standard request to interface)
        if bmRequestType == 0x81 and bRequest == 0x06:
            desc_type = wValue >> 8
            if desc_type == 0x22 and wIndex == _HID_ITF_NUM:
                # HID Report Descriptor
                return _REPORT_DESC[:wLength]

        # HID class requests (bmRequestType & 0x60 == 0x20 means class request)
        if (bmRequestType & 0x60) == 0x20 and wIndex == _HID_ITF_NUM:
            if bRequest == 0x0A:  # SET_IDLE
                return True
            if bRequest == 0x0B:  # SET_PROTOCOL
                return True
            if bRequest == 0x01:  # GET_REPORT
                return bytes(8)

        return None  # Let built-in driver try

    if stage == 3:  # ACK stage
        return True

    return True


def _xfer_cb(ep, result, num_bytes):
    pass


# --- Configure USB device on module import ---
try:
    _usbd = machine.USBDevice()
    _usbd.builtin_driver = _usbd.BUILTIN_CDC
    _usbd.config(
        desc_dev=_DEV_DESC,
        desc_cfg=_CFG_DESC,
        desc_strs=("KeyMesh", "KeyMesh HID Keyboard"),
        open_itf_cb=_open_itf_cb,
        reset_cb=_reset_cb,
        control_xfer_cb=_control_xfer_cb,
        xfer_cb=_xfer_cb,
    )
    _usbd.active(1)
    print("USB HID keyboard configured")
except Exception as e:
    _usbd = None
    print("USB HID init failed: %s" % e)
    print("HID keyboard will not be available")


class HIDKeyboard:
    """Async USB HID keyboard driver.

    Consumes (keycode, modifier) tuples from an asyncio.Queue and
    sends them as USB HID keyboard reports.
    """

    def __init__(self):
        self._report = bytearray(8)

    async def send_keystroke(self, keycode, modifiers=0):
        if not _is_ready or _ep_in is None or _usbd is None:
            return
        # Key down
        self._report[0] = modifiers
        self._report[1] = 0
        self._report[2] = keycode
        for i in range(3, 8):
            self._report[i] = 0
        _usbd.submit_xfer(_ep_in, bytes(self._report))
        await asyncio.sleep_ms(10)
        # Key up (empty report)
        for i in range(8):
            self._report[i] = 0
        _usbd.submit_xfer(_ep_in, bytes(self._report))
        await asyncio.sleep_ms(10)

    async def run(self, queue):
        """Main loop: consume (keycode, modifier) from queue, send as HID."""
        while True:
            keycode, modifiers = await queue.get()
            try:
                await self.send_keystroke(keycode, modifiers)
            except OSError:
                # USB not ready, discard keystroke
                await asyncio.sleep_ms(100)
