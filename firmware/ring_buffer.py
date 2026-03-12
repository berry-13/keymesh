class RingBuffer:
    """Fixed-size byte ring buffer with per-client read cursors.

    Multiple consumers (web + TCP clients) can independently read from the
    buffer without interfering with each other. Data written beyond the buffer
    size overwrites the oldest bytes.
    """

    def __init__(self, size=4096):
        self._buf = bytearray(size)
        self._size = size
        self._total_written = 0
        self._cursors = {}

    def write(self, data):
        for b in data:
            self._buf[self._total_written % self._size] = b
            self._total_written += 1
        oldest = self._total_written - self._size
        for cid in self._cursors:
            if self._cursors[cid] < oldest:
                self._cursors[cid] = oldest

    def register(self, client_id):
        self._cursors[client_id] = self._total_written

    def unregister(self, client_id):
        self._cursors.pop(client_id, None)

    def read(self, client_id, max_bytes=512):
        if client_id not in self._cursors:
            return b""
        cursor = self._cursors[client_id]
        avail = self._total_written - cursor
        if avail <= 0:
            return b""
        n = min(avail, max_bytes)
        result = bytearray(n)
        for i in range(n):
            result[i] = self._buf[(cursor + i) % self._size]
        self._cursors[client_id] = cursor + n
        return bytes(result)

    def available(self, client_id):
        if client_id not in self._cursors:
            return 0
        return max(0, self._total_written - self._cursors[client_id])
