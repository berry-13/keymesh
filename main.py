#!/usr/bin/env python3
import asyncio
import json
import os

from net import setup_wifi
from hid import HIDKeyboard
from uart_bridge import UARTBridge
from tcp import TCPServer
from web import WebServer
from ring_buffer import RingBuffer


async def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, "config.json")

    with open(config_path) as f:
        config = json.load(f)

    ip = setup_wifi(config)
    print("KeyMesh ready at %s" % ip)

    keystroke_queue = asyncio.Queue(maxsize=64)
    uart_buf = RingBuffer(size=4096)

    hid = HIDKeyboard()
    uart = UARTBridge(config, uart_buf)
    tcp = TCPServer(config, keystroke_queue, uart_buf)
    web = WebServer(config, keystroke_queue, uart_buf, ip=ip)
    web.set_uart_available(uart.uart_available)

    print("Starting services...")
    print("  Web UI:  http://%s:%d" % (ip, config.get("web_port", 80)))
    print("  Raw TCP: %s:%d" % (ip, config.get("tcp_port", 4444)))
    print("  UART:    %s" % ("active" if uart.uart_available else "not connected"))

    try:
        await asyncio.gather(
            hid.run(keystroke_queue),
            uart.run(),
            tcp.run(),
            web.run(),
        )
    finally:
        hid.close()
        uart.close()


if __name__ == "__main__":
    asyncio.run(main())
