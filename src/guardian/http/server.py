"""Bounded HTTP worker lifecycle and service startup."""
import logging
import threading
from .listener import ExclusiveHTTPServer
from .lifecycle import follow_launcher
from ..authorization.service import Broker
from .handler import Handler
from ..ui.react.sessions import BrowserSessions

log = logging.getLogger("guardian.server")


class GuardianHTTPServer(ExclusiveHTTPServer):
    daemon_threads = True
    request_queue_size = 64

    def __init__(self, address, config):
        self.active = set()
        self.active_lock = threading.Lock()
        self.settings_lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(256)
        self.browser_sessions = BrowserSessions()
        super().__init__(address, Handler)
        self.broker = Broker(config)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            request.close()
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()

    def handle_error(self, request, client_address):
        log.warning("HTTP worker failed; request was closed")

    def server_close(self):
        if hasattr(self, "broker"):
            self.broker.close()
        super().server_close()



def serve(config, host="127.0.0.1", port=8765):
    server = GuardianHTTPServer((host, port), config)
    follow_launcher(server)
    log.info("Guardian listening on %s:%s", host, port)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


