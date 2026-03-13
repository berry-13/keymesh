import asyncio
import os
import subprocess


class UARTBridge:
    """Reads target's serial console into a shared ring buffer.

    Uses /dev/serial0 (Pi Zero 2 W GPIO UART) in non-blocking mode.
    If the serial device doesn't exist or can't be opened, the bridge
    marks uart_available=False and becomes a no-op.
    """

    def __init__(self, config, ring_buf):
        self.ring_buf = ring_buf
        self.uart_available = False
        self._fd = None
        self._ser = None

        if not config.get("uart_enabled", True):
            print("UART disabled in config")
            return

        device = config.get("uart_device", "/dev/serial0")
        baud = config.get("uart_baud", 115200)

        try:
            import serial
            self._ser = serial.Serial(device, baud, timeout=0)
            self.uart_available = True
            print("UART bridge: %s @ %d baud" % (device, baud))
        except ImportError:
            try:
                self._configure_tty(device, baud)
                self._fd = os.open(device, os.O_RDONLY | os.O_NONBLOCK)
                self.uart_available = True
                print("UART bridge: %s @ %d baud (raw)" % (device, baud))
            except OSError as e:
                print("UART init failed: %s" % e)
                print("Running without UART (keystroke-only mode)")
        except Exception as e:
            print("UART init failed: %s" % e)
            print("Running without UART (keystroke-only mode)")

    def _configure_tty(self, device, baud):
        """Set baud rate and raw mode using stty."""
        subprocess.run(
            ["stty", "-F", device, str(baud), "raw", "-echo"],
            check=True, capture_output=True,
        )

    async def run(self):
        if not self.uart_available:
            while True:
                await asyncio.sleep(3600)

        if self._ser is not None:
            await self._run_pyserial()
        else:
            await self._run_raw()

    async def _run_pyserial(self):
        while True:
            data = self._ser.read(256)
            if data:
                self.ring_buf.write(data)
            await asyncio.sleep(0.01)

    async def _run_raw(self):
        while True:
            try:
                data = os.read(self._fd, 256)
                if data:
                    self.ring_buf.write(data)
            except BlockingIOError:
                pass
            except OSError:
                pass
            await asyncio.sleep(0.01)

    def close(self):
        if self._ser is not None:
            self._ser.close()
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
