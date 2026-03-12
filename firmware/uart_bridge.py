import asyncio
from machine import UART, Pin


class UARTBridge:
    """Reads UART RX into a shared ring buffer.

    If UART hardware is not connected or init fails, the bridge
    sets uart_available=False and the run() coroutine becomes a no-op.
    """

    def __init__(self, config, ring_buf):
        self.ring_buf = ring_buf
        self.uart_available = False
        self._uart = None
        try:
            self._uart = UART(
                0,
                baudrate=config.get("uart_baud", 115200),
                tx=Pin(config.get("uart_tx_pin", 0)),
                rx=Pin(config.get("uart_rx_pin", 1)),
                bits=8,
                parity=None,
                stop=1,
            )
            self.uart_available = True
            print("UART bridge initialized (baud=%d)" % config.get("uart_baud", 115200))
        except Exception as e:
            print("UART init failed: %s" % e)
            print("Running without UART (keystroke-only mode)")

    async def run(self):
        if not self.uart_available or self._uart is None:
            # No UART — sleep forever so gather() doesn't exit
            while True:
                await asyncio.sleep(3600)
        while True:
            data = self._uart.read(256)
            if data:
                self.ring_buf.write(data)
            await asyncio.sleep_ms(10)
