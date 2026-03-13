import asyncio
import json
import base64
import os

from keymap import key_to_hid, char_to_hid

try:
    import websockets
    from websockets.server import serve as ws_serve
    _HAS_WEBSOCKETS = True
except ImportError:
    _HAS_WEBSOCKETS = False


class WebServer:
    """HTTP + WebSocket server for browser terminal.

    Uses the 'websockets' library for reliable WebSocket handling.
    HTTP serving (index.html) is done via the process_request hook.
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
        if not _HAS_WEBSOCKETS:
            print("ERROR: 'websockets' library not installed")
            print("Run: sudo pip3 install websockets")
            while True:
                await asyncio.sleep(3600)

        async with ws_serve(
            self._ws_handler,
            "0.0.0.0",
            self._port,
            process_request=self._process_request,
        ):
            print("Web server listening on port %d" % self._port)
            asyncio.create_task(self._uart_fanout())
            await asyncio.Future()  # run forever

    async def _process_request(self, path, request_headers):
        """Handle plain HTTP requests; return None to allow WebSocket upgrade."""
        if path in ("/", "/index.html"):
            html = self._load_html().encode()
            return (200, [
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Length", str(len(html))),
                ("Connection", "close"),
            ], html)
        if path == "/ws":
            return None  # let websockets library handle the upgrade
        return (404, [], b"404 Not Found")

    async def _ws_handler(self, websocket, path=None):
        """Handle a WebSocket connection."""
        self._client_id += 1
        cid = "ws_%d" % self._client_id
        self._uart_buf.register(cid)
        self._ws_clients[cid] = websocket
        print("WebSocket client connected: %s" % cid)

        try:
            await websocket.send(json.dumps({
                "type": "status",
                "uart": self._uart_available,
                "ip": self._ip,
                "mode": self._config.get("wifi_mode", "ap"),
            }))

            async for message in websocket:
                await self._handle_ws_message(message)
        except websockets.ConnectionClosed:
            pass
        except Exception as e:
            print("WS error (%s): %s" % (cid, e))
        finally:
            self._ws_clients.pop(cid, None)
            self._uart_buf.unregister(cid)
            print("WebSocket client disconnected: %s" % cid)

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
        """Push UART data to all connected WebSocket clients."""
        while True:
            dead = []
            for cid, websocket in list(self._ws_clients.items()):
                data = self._uart_buf.read(cid)
                if data:
                    try:
                        encoded = base64.b64encode(data).decode()
                        msg = json.dumps({"type": "uart", "data": encoded})
                        await websocket.send(msg)
                    except Exception:
                        dead.append(cid)
            for cid in dead:
                self._ws_clients.pop(cid, None)
                self._uart_buf.unregister(cid)
            await asyncio.sleep(0.02)
