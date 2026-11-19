"""One listener per address, including on Windows where SO_REUSEADDR can share ports."""
import os
import socket
from http.server import ThreadingHTTPServer


class ExclusiveHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = os.name != "nt"

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()
