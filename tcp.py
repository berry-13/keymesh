import asyncio
from keymap import byte_to_hid, parse_esc_sequence, KEY_ESC, MOD_NONE


class TCPServer:
    """Raw TCP server (default port 4444).

    Bidirectional transparent byte stream:
    - Bytes from client -> parsed into HID keystrokes -> keystroke queue
    - UART ring buffer data -> forwarded to client as-is
    """

    def __init__(self, config, keystroke_queue, uart_buf):
        self._port = config.get("tcp_port", 4444)
        self._queue = keystroke_queue
        self._uart_buf = uart_buf
        self._client_id = 0

    async def run(self):
        server = await asyncio.start_server(
            self._handle_client, "0.0.0.0", self._port
        )
        print("TCP server listening on port %d" % self._port)
        async with server:
            await server.serve_forever()

    async def _handle_client(self, reader, writer):
        self._client_id += 1
        cid = "tcp_%d" % self._client_id
        self._uart_buf.register(cid)
        addr = writer.get_extra_info("peername")
        print("TCP client connected: %s" % (addr,))
        try:
            read_task = asyncio.create_task(self._read_loop(reader))
            write_task = asyncio.create_task(self._write_loop(writer, cid))
            done, pending = await asyncio.wait(
                [read_task, write_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
        except Exception:
            pass
        finally:
            self._uart_buf.unregister(cid)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
            print("TCP client disconnected: %s" % (addr,))

    async def _read_loop(self, reader):
        esc_buf = b""
        in_esc = False
        while True:
            data = await reader.read(256)
            if not data:
                return
            i = 0
            while i < len(data):
                b = data[i]
                if in_esc:
                    esc_buf += bytes([b])
                    hid, consumed = parse_esc_sequence(esc_buf)
                    if hid:
                        await self._queue.put(hid)
                        in_esc = False
                        esc_buf = b""
                    elif len(esc_buf) > 6:
                        await self._queue.put((KEY_ESC, MOD_NONE))
                        in_esc = False
                        esc_buf = b""
                elif b == 0x1B:
                    in_esc = True
                    esc_buf = b""
                else:
                    hid = byte_to_hid(b)
                    if hid:
                        await self._queue.put(hid)
                i += 1
        if in_esc:
            await self._queue.put((KEY_ESC, MOD_NONE))

    async def _write_loop(self, writer, cid):
        while True:
            data = self._uart_buf.read(cid)
            if data:
                writer.write(data)
                await writer.drain()
            else:
                await asyncio.sleep(0.02)
