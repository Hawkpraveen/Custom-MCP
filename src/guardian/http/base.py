"""HTTP framing, authentication, bounded reads, and disconnect detection."""
import concurrent.futures
import hmac
import json
import select
import socket
from http.server import BaseHTTPRequestHandler
from ..protocol import MAX_MESSAGE_BYTES


class BaseHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "Guardian"

    def setup(self):
        super().setup()
        self.connection.settimeout(15)


    def log_message(self, *args):
        pass  # Default HTTP logs may include tokens in malformed URLs.


    @property
    def config(self):
        return self.server.broker.config


    def reply(self, status, data=None, headers=None):
        content = b"" if data is None else json.dumps(data, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.close_connection = True
        if content:
            self.wfile.write(content)


    def authorized(self, role):
        # Reject duplicate authorization headers rather than choosing one.
        values = self.headers.get_all("Authorization", [])
        expected = "Bearer " + self.config[role + "_token"]
        if len(values) != 1 or not hmac.compare_digest(values[0].encode(), expected.encode()):
            self.reply(401, {"error": "Authentication required"}, {"WWW-Authenticate": "Bearer"})
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in self.config.get("allowed_origins", ["https://claude.ai"]):
            self.reply(403, {"error": "Origin not allowed"})
            return False
        return True


    def body(self):
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("Chunked request bodies are unsupported; send Content-Length")
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1:
            raise ValueError("Exactly one Content-Length is required")
        length = int(lengths[0])
        if not 0 < length <= MAX_MESSAGE_BYTES:
            raise ValueError("Request must be between 1 byte and 1 MiB")
        data = self.rfile.read(length)
        if len(data) != length:
            raise ValueError("Incomplete request")
        return data


    def disconnected(self):
        if select.select([self.connection], [], [], 0)[0]:
            try:
                return self.connection.recv(1, socket.MSG_PEEK) == b""
            except OSError:
                return True
        return False


    def await_approval(self, message, server, source, scope):
        broker = self.server.broker
        pending = broker.call(broker.manager.create, server, source, scope, message)
        future = broker.wait(pending)
        try:
            while True:
                try:
                    state = future.result(timeout=0.1)
                    if self.disconnected():
                        return "cancelled"
                    return state
                except concurrent.futures.TimeoutError:
                    if self.disconnected():
                        broker.call(broker.manager.finish, pending, "cancelled")
                        return "cancelled"
        finally:
            if not future.done():
                future.cancel()


