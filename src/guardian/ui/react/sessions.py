"""Bounded, in-memory browser sessions. Credentials never enter page storage."""
import secrets
import threading
import time
from dataclasses import dataclass


@dataclass
class BrowserSession:
    token: str
    csrf: str
    instance: str
    last_seen: float


class BrowserSessions:
    def __init__(self, lifetime=1800, capacity=8):
        self.lifetime = lifetime
        self.capacity = capacity
        self.sessions = {}
        self.lock = threading.Lock()
        self.failures = []

    def _expire(self):
        now = time.monotonic()
        self.sessions = {key: value for key, value in self.sessions.items()
                         if now - value.last_seen < self.lifetime}
        self.failures = [stamp for stamp in self.failures if now - stamp < 30]

    def login_allowed(self):
        with self.lock:
            self._expire()
            return len(self.failures) < 5

    def failed_login(self):
        with self.lock:
            self._expire()
            self.failures.append(time.monotonic())

    def create(self):
        with self.lock:
            self._expire()
            if len(self.sessions) >= self.capacity:
                raise ValueError("Browser session capacity reached")
            session = BrowserSession(secrets.token_urlsafe(32), secrets.token_urlsafe(32),
                                     "web:" + secrets.token_hex(16), time.monotonic())
            self.sessions[session.token] = session
            return session

    def get(self, token):
        with self.lock:
            self._expire()
            session = self.sessions.get(token)
            if session:
                session.last_seen = time.monotonic()
            return session

    def remove(self, token):
        with self.lock:
            self.sessions.pop(token, None)

