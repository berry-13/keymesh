"""USB HID Keyboard via Linux USB Gadget (/dev/hidg0).

The gadget device is created by gadget.sh (configfs) before this runs.
We just write 8-byte HID keyboard reports to /dev/hidg0.
"""

import asyncio
import os

_HIDG_PATH = "/dev/hidg0"
_EMPTY_REPORT = b"\x00" * 8


class HIDKeyboard:

    def __init__(self):
        self._fd = None
        try:
            self._fd = os.open(_HIDG_PATH, os.O_WRONLY)
            print("USB HID keyboard ready (%s)" % _HIDG_PATH)
        except OSError as e:
            print("USB HID not available: %s" % e)
            print("Is the USB gadget configured? Run: sudo /opt/keymesh/gadget.sh")

    async def send_keystroke(self, keycode, modifiers=0):
        if self._fd is None:
            return
        report = bytes([modifiers, 0, keycode, 0, 0, 0, 0, 0])
        try:
            os.write(self._fd, report)
            await asyncio.sleep(0.01)
            os.write(self._fd, _EMPTY_REPORT)
            await asyncio.sleep(0.01)
        except OSError:
            pass

    async def run(self, queue):
        while True:
            keycode, modifiers = await queue.get()
            try:
                await self.send_keystroke(keycode, modifiers)
            except Exception:
                await asyncio.sleep(0.1)

    def close(self):
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
