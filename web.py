import asyncio
import json
import hashlib
import base64
import struct
import os

from keymap import key_to_hid, char_to_hid

_WS_MAGIC = b"258EAFA5-E914-47DA-95CA-5AB9F3811C11"


def _ws_accept_key(ws_key):
    h = hashlib.sha1(ws_key.strip().encode() + _WS_MAGIC).digest()
    return base64.b64encode(h).decode()


class WebServer:
    """HTTP + WebSocket server for browser terminal.

    GET /     -> serves www/index.html
    GET /ws   -> WebSocket upgrade
    """

    def __init__(self, config, keystroke_queue, uart_buf, ip=None):
        self._port = config.get("web_port", 80)
        self._queue = keystroke_queue
        self._uart_buf = uart_buf
        self._config = config
        self._ip = ip or "0.0.0.0"
        self._ws_clients = {}
        self._client_id = 0
        self._uart_available = False
        self._html = None
        self._base_dir = os.path.dirname(os.path.abspath(__file__))

    def set_uart_available(self, available):
        self._uart_available = available

    def _load_html(self):
        if self._html is not None:
            return self._html
        try:
            path = os.path.join(self._base_dir, "www", "index.html")
            with open(path, "r") as f:
                self._html = f.read()
        except OSError:
            self._html = "<html><body><h1>KeyMesh</h1><p>index.html not found</p></body></html>"
        return self._html

    async def run(self):
        server = await asyncio.start_server(
            self._handle_request, "0.0.0.0", self._port
        )
        print("Web server listening on port %d" % self._port)
        asyncio.create_task(self._uart_fanout())
        async with server:
            await server.serve_forever()

    async def _handle_request(self, reader, writer):
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=5)
            if not line:
                writer.close()
                return
            request_line = line.decode().strip()
            parts = request_line.split(" ")
            if len(parts) < 2:
                writer.close()
                return
            method, path = parts[0], parts[1]

            headers = {}
            while True:
                line = await asyncio.wait_for(reader.readline(), timeout=5)
                if not line or line == b"\r\n":
                    break
                decoded = line.decode().strip()
                if ":" in decoded:
                    k, v = decoded.split(":", 1)
                    headers[k.strip().lower()] = v.strip()

            print("HTTP: %s %s | connection: %s" % (method, path, headers.get("connection", "")))
            if path == "/ws" and "upgrade" in headers.get("connection", "").lower():
                await self._ws_upgrade(reader, writer, headers)
            elif method == "GET" and path in ("/", "/index.html"):
                await self._serve_html(writer)
            else:
                await self._send_response(writer, 404, "Not Found")
        except Exception as e:
            import traceback
            print("Request error: %s" % e)
            traceback.print_exc()
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _serve_html(self, writer):
        html = self._load_html()
        header = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/html; charset=utf-8\r\n"
            "Content-Length: %d\r\n"
            "Connection: close\r\n\r\n" % len(html)
        )
        writer.write(header.encode())
        writer.write(html.encode())
        await writer.drain()

    async def _send_response(self, writer, code, message):
        body = "%d %s" % (code, message)
        header = (
            "HTTP/1.1 %d %s\r\n"
            "Content-Length: %d\r\n"
            "Connection: close\r\n\r\n" % (code, message, len(body))
        )
        writer.write(header.encode())
        writer.write(body.encode())
        await writer.drain()

    # --- WebSocket ---

    async def _ws_upgrade(self, reader, writer, headers):
        ws_key = headers.get("sec-websocket-key", "")
        accept = _ws_accept_key(ws_key)
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Accept: %s\r\n\r\n" % accept
        )
        writer.write(response.encode())
        await writer.drain()

        self._client_id += 1
        cid = "ws_%d" % self._client_id
        self._uart_buf.register(cid)
        self._ws_clients[cid] = writer

        await self._ws_send(writer, json.dumps({
            "type": "status",
            "uart": self._uart_available,
            "ip": self._ip,
            "mode": self._config.get("wifi_mode", "ap"),
        }))

        try:
            while True:
                opcode, payload = await self._ws_recv(reader)
                if opcode is None or opcode == 0x08:
                    break
                if opcode == 0x09:
                    await self._ws_send_frame(writer, 0x0A, payload)
                    continue
                if opcode == 0x01:
                    await self._handle_ws_message(payload)
        except Exception:
            pass
        finally:
            self._ws_clients.pop(cid, None)
            self._uart_buf.unregister(cid)

    async def _handle_ws_message(self, payload):
        try:
            msg = json.loads(payload)
        except ValueError:
            return
        msg_type = msg.get("type")
        if msg_type == "key":
            hid = key_to_hid(msg.get("key", ""), msg.get("mod", []))
            if hid:
                await self._queue.put(hid)
        elif msg_type == "raw":
            data = msg.get("data", "")
            for ch in data:
                hid = char_to_hid(ch)
                if hid:
                    await self._queue.put(hid)

    async def _uart_fanout(self):
        while True:
            dead = []
            for cid, writer in list(self._ws_clients.items()):
                data = self._uart_buf.read(cid)
                if data:
                    try:
                        encoded = base64.b64encode(data).decode()
                        msg = json.dumps({"type": "uart", "data": encoded})
                        await self._ws_send(writer, msg)
                    except Exception:
                        dead.append(cid)
            for cid in dead:
                self._ws_clients.pop(cid, None)
                self._uart_buf.unregister(cid)
            await asyncio.sleep(0.02)

    # --- WebSocket framing ---

    async def _ws_recv(self, reader):
        hdr = await reader.readexactly(2)
        opcode = hdr[0] & 0x0F
        masked = hdr[1] & 0x80
        length = hdr[1] & 0x7F
        if length == 126:
            raw = await reader.readexactly(2)
            length = struct.unpack(">H", raw)[0]
        elif length == 127:
            raw = await reader.readexactly(8)
            length = struct.unpack(">Q", raw)[0]
        mask = None
        if masked:
            mask = await reader.readexactly(4)
        payload = await reader.readexactly(length)
        if mask:
            payload = bytes(payload[i] ^ mask[i % 4] for i in range(len(payload)))
        return (opcode, payload)

    async def _ws_send(self, writer, text):
        data = text.encode() if isinstance(text, str) else text
        await self._ws_send_frame(writer, 0x01, data)

    async def _ws_send_frame(self, writer, opcode, data):
        b0 = 0x80 | opcode
        length = len(data)
        if length < 126:
            writer.write(bytes([b0, length]))
        elif length < 65536:
            writer.write(bytes([b0, 126]) + struct.pack(">H", length))
        else:
            writer.write(bytes([b0, 127]) + struct.pack(">Q", length))
        writer.write(data)
        await writer.drain()
