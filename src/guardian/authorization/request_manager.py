"""Single-event-loop approval state machine. No approved operation is retried."""
import asyncio
import hashlib
import json
import logging
import time
import uuid
from .models import Pending

log = logging.getLogger("guardian.audit")


class ApprovalManager:
    def __init__(self, timeout=90.0, lease_seconds=120.0, capacity=128):
        self.timeout = timeout
        self.lease_seconds = lease_seconds
        self.capacity = capacity
        self.pending: dict[str, Pending] = {}
        self.last_seen = 0.0
        self.approver_id: str | None = None
        self.closed = False

    def heartbeat(self, instance: str):
        self.sweep()
        if self.available and self.approver_id != instance:
            raise ValueError("Another approval app is already connected")
        self.approver_id = instance
        self.last_seen = time.monotonic()

    @property
    def available(self):
        return not self.closed and time.monotonic() - self.last_seen < self.lease_seconds

    def create(self, server: str, source: str, scope: str, message: dict) -> Pending:
        if not self.available:
            raise ValueError("Approval app is offline; request blocked")
        if len(self.pending) >= self.capacity:
            raise ValueError("Approval queue is full; request blocked")
        if any(p.scope == scope and type(p.message.get("id")) is type(message.get("id"))
               and p.message.get("id") == message.get("id") for p in self.pending.values()):
            raise ValueError("Duplicate in-flight request ID")
        frozen = json.dumps(message, sort_keys=True, ensure_ascii=True, allow_nan=False)
        now = time.time()
        pending = Pending(str(uuid.uuid4()), server, source, scope, json.loads(frozen),
                          hashlib.sha256(frozen.encode()).hexdigest(), now, now + self.timeout,
                          time.monotonic() + self.timeout,
                          asyncio.get_running_loop().create_future())
        self.pending[pending.id] = pending
        self.audit(pending, "pending")
        return pending

    def audit(self, pending, state):
        # Never record request parameters, credentials, names, or user-provided text.
        log.info("request=%s state=%s digest=%s", pending.id, state, pending.fingerprint[:12])

    def finish(self, pending: Pending, state: str):
        if pending.state != "pending":
            return False
        pending.state = state
        self.pending.pop(pending.id, None)
        if not pending.future.done():
            pending.future.set_result(state)
        self.audit(pending, state)
        return True

    def decide(self, request_id: str, fingerprint: str, allow: bool, instance: str):
        self.sweep()
        pending = self.pending.get(request_id)
        if not self.available or instance != self.approver_id or pending is None:
            raise ValueError("Approval expired, cancelled, or unavailable")
        if fingerprint != pending.fingerprint:
            raise ValueError("Request fingerprint mismatch")
        self.finish(pending, "approved" if allow else "denied")

    def cancel(self, scope: str, rpc_id):
        for pending in list(self.pending.values()):
            if pending.scope == scope and type(pending.message.get("id")) is type(rpc_id) and pending.message.get("id") == rpc_id:
                self.finish(pending, "cancelled")

    def sweep(self):
        for pending in list(self.pending.values()):
            if not self.available:
                self.finish(pending, "offline")
            elif time.monotonic() >= pending.expires_at:
                self.finish(pending, "expired")

    async def wait(self, pending: Pending):
        try:
            remaining = max(0, pending.expires_at - time.monotonic())
            return await asyncio.wait_for(asyncio.shield(pending.future), remaining)
        except TimeoutError:
            self.finish(pending, "expired")
            return "expired"
        except asyncio.CancelledError:
            self.finish(pending, "cancelled")
            raise

    def disconnect(self, instance: str):
        if instance == self.approver_id:
            self.last_seen = 0.0
            self.sweep()

    def close(self):
        self.closed = True
        self.sweep()

