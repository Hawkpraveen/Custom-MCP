"""Route authenticated HTTP requests to approval or MCP services."""
import json
import logging
import os
from .base import BaseHandler
from ..authorization.routes import handle_api
from ..gateway.http_proxy import handle_mcp
from ..gateway.http_transport import relay_http
from ..ui.react.routes import dashboard_get, dashboard_post

log = logging.getLogger("guardian.http")


class Handler(BaseHandler):
    def do_GET(self):
        try:
            if self.path == "/dashboard" or self.path.startswith("/dashboard/"):
                return dashboard_get(self)
            if self.path == "/health":
                return self.reply(200, {"status": "ok", "service": "guardian", "launch_id": os.environ.get("GUARDIAN_LAUNCH_ID", "manual")})
            if self.path == "/api/pending":
                if not self.authorized("approver"):
                    return
                instance = self.headers.get("X-Guardian-Instance", "")
                if not 1 <= len(instance) <= 128:
                    raise ValueError("Missing approval app instance ID")
                broker = self.server.broker
                def snapshot():
                    broker.manager.heartbeat(instance)
                    broker.manager.sweep()
                    return [p.public() for p in broker.manager.pending.values()]
                return self.reply(200, {"pending": broker.call(snapshot)})
            if self.path == "/mcp":
                if self.authorized("mcp"):
                    return relay_http(self, None)  # Legacy GET notification stream.
                return
            self.reply(404, {"error": "Not found"})
        except ValueError:
            self.reply(409, {"error": "Invalid request or another approval app is connected"})
        except (BrokenPipeError, ConnectionError, OSError):
            self.close_connection = True


    def do_DELETE(self):
        if self.path != "/mcp":
            return self.reply(404)
        if self.authorized("mcp"):
            # Transport teardown never executes a tool and must remain available.
            relay_http(self, None)


    def do_POST(self):
        try:
            if self.path.startswith("/dashboard/"):
                return dashboard_post(self)
            roles = {"/api/authorize": "producer", "/api/cancel": "producer",
                     "/api/decision": "approver", "/api/disconnect": "approver", "/mcp": "mcp"}
            role = roles.get(self.path)
            if role is None:
                return self.reply(404)
            if not self.authorized(role):
                return
            raw = self.body()
            if self.path == "/mcp":
                return handle_mcp(self, raw)
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise ValueError("Expected object")
            handle_api(self, body)
        except (ValueError, KeyError, TypeError, UnicodeError):
            self.reply(409, {"error": "Invalid, expired, offline, or conflicting request"})
        except (BrokenPipeError, ConnectionError, OSError):
            self.close_connection = True
        except Exception:
            log.warning("Request failed closed")
            self.reply(503, {"error": "Gateway unavailable; request blocked"})


