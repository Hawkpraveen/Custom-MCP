"""Approval API operations, independent of MCP transport forwarding."""
import json
from ..protocol import parse_message, requires_approval


def handle_api(handler, body):
    broker = handler.server.broker
    manager = broker.manager
    if handler.path == "/api/authorize":
        message = parse_message(json.dumps(body["message"]))
        if not requires_approval(message):
            raise ValueError("Expected a request")
        if not all(isinstance(body.get(key), str) and 0 < len(body[key]) <= 256 for key in ("server", "source", "scope")):
            raise ValueError("Invalid request context")
        state = handler.await_approval(message, body["server"], body["source"], body["scope"])
        return handler.reply(200, {"state": state, "allowed": state == "approved"})
    if handler.path == "/api/cancel":
        broker.call(manager.cancel, body["scope"], body["request_id"])
    elif handler.path == "/api/disconnect":
        broker.call(manager.disconnect, body["instance"])
    elif handler.path == "/api/decision":
        if type(body.get("allow")) is not bool:
            raise ValueError("allow must be a boolean")
        broker.call(manager.decide, body["id"], body["fingerprint"], body["allow"], body["instance"])
    handler.reply(200, {"ok": True})
