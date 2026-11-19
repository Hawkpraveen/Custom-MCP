"""Authorize MCP operations before invoking the upstream HTTP transport."""
from ..protocol import error, parse_message, request_key, requires_approval
from .http_transport import relay_http


def handle_mcp(handler, raw):
    try:
        message = parse_message(raw)
    except ValueError:
        return handler.reply(400, error(None, "Invalid MCP request", -32600))
    broker = handler.server.broker
    scope = "http:" + handler.headers.get("Mcp-Session-Id", "single-user")
    key = (scope, request_key(message))
    gated = requires_approval(message)
    if gated:
        with handler.server.active_lock:
            if key in handler.server.active:
                return handler.reply(409, error(message["id"], "Duplicate in-flight request ID"))
            handler.server.active.add(key)
    try:
        if message.get("method") == "notifications/cancelled":
            broker.call(broker.manager.cancel, scope, message.get("params", {}).get("requestId"))
        if gated:
            try:
                state = handler.await_approval(message, handler.config.get("server_name", "upstream"), "remote MCP", scope)
            except ValueError:
                state = "unavailable"
            if state != "approved":
                return handler.reply(200, error(message["id"], "Request blocked by Guardian: " + state))
        if handler.disconnected():
            return
        relay_http(handler, raw)
    finally:
        if gated:
            with handler.server.active_lock:
                handler.server.active.discard(key)

