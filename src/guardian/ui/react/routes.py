"""Loopback-only dashboard routes with HttpOnly sessions and CSRF checks."""
import hmac
import json
from http.cookies import SimpleCookie, CookieError
from pathlib import Path
from ...config import MAX_APPROVAL_TIMEOUT, MIN_APPROVAL_TIMEOUT, persist_approval_timeout

STATIC = Path(__file__).parent / "static"
ASSETS = {"/dashboard": ("index.html", "text/html; charset=utf-8"),
          "/dashboard/": ("index.html", "text/html; charset=utf-8"),
          "/dashboard/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/dashboard/app.css": ("app.css", "text/css; charset=utf-8"),
          "/dashboard/service-worker.js": ("service-worker.js", "text/javascript; charset=utf-8")}
COOKIE = "guardian_dashboard"


def local_request(handler):
    """Reject public tunnel hosts and DNS rebinding; ignore forwarded headers."""
    port = handler.server.server_port
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    host = handler.headers.get_all("Host", [])
    if handler.client_address[0] not in {"127.0.0.1", "::1"} or len(host) != 1 or host[0] not in hosts:
        handler.reply(403, {"error": "Dashboard is available only through its local loopback address."})
        return False
    origin = handler.headers.get("Origin")
    expected = "http://" + host[0]
    if (origin and origin != expected) or (handler.command == "POST" and origin != expected):
        handler.reply(403, {"error": "Dashboard requests must come from the same local origin."})
        return False
    return True


def session_for(handler):
    cookie = SimpleCookie()
    try:
        cookie.load(handler.headers.get("Cookie", ""))
    except CookieError:
        return None
    value = cookie.get(COOKIE)
    return handler.server.browser_sessions.get(value.value if value else "")


def dashboard_get(handler):
    if not local_request(handler):
        return
    if handler.path in ASSETS:
        name, content_type = ASSETS[handler.path]
        try:
            data = (STATIC / name).read_bytes()
        except FileNotFoundError:
            return handler.reply(503, {"error": "React dashboard is not built. Run npm ci and npm run build inside src/guardian/ui/react/."})
        handler.send_response(200)
        for key, value in {"Content-Type": content_type, "Content-Length": str(len(data)),
                           "Cache-Control": "no-store", "Connection": "close", "X-Frame-Options": "DENY",
                           "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; worker-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"}.items():
            handler.send_header(key, value)
        handler.end_headers()
        handler.close_connection = True
        handler.wfile.write(data)
        return
    session = session_for(handler)
    if session is None:
        return handler.reply(401, {"error": "Sign in with your approver token."})
    if handler.path == "/dashboard/session":
        return handler.reply(200, {"csrf": session.csrf})
    if handler.path == "/dashboard/pending":
        broker = handler.server.broker
        def snapshot():
            broker.manager.heartbeat(session.instance)
            return [pending.public() for pending in broker.manager.pending.values()]
        try:
            pending = broker.call(snapshot)
        except ValueError:
            return handler.reply(409, {"error": "Another approval interface is connected. Disconnect it, then retry."})
        return handler.reply(200, {"pending": pending})
    if handler.path == "/dashboard/settings":
        timeout = handler.server.broker.call(lambda: handler.server.broker.manager.timeout)
        return handler.reply(200, {"approval_timeout": timeout,
                                   "min_timeout": MIN_APPROVAL_TIMEOUT,
                                   "max_timeout": MAX_APPROVAL_TIMEOUT})
    handler.reply(404, {"error": "Not found"})


def dashboard_post(handler):
    if not local_request(handler):
        return
    if handler.headers.get_content_type() != "application/json":
        return handler.reply(415, {"error": "Send application/json."})
    body = json.loads(handler.body())
    if not isinstance(body, dict):
        raise ValueError("Expected object")
    sessions = handler.server.browser_sessions
    broker = handler.server.broker
    if handler.path == "/dashboard/session":
        if not sessions.login_allowed():
            return handler.reply(429, {"error": "Too many sign-in attempts. Wait 30 seconds, then retry."})
        token = body.get("token")
        if not isinstance(token, str) or not hmac.compare_digest(token.encode(), handler.config["approver_token"].encode()):
            sessions.failed_login()
            return handler.reply(401, {"error": "The approver token is incorrect."})
        session = sessions.create()
        try:
            broker.call(broker.manager.heartbeat, session.instance)
        except ValueError:
            sessions.remove(session.token)
            return handler.reply(409, {"error": "Another approval interface is connected. Disconnect it, then sign in."})
        return handler.reply(200, {"csrf": session.csrf}, {
            "Set-Cookie": f"{COOKIE}={session.token}; HttpOnly; SameSite=Strict; Path=/dashboard; Max-Age=1800"})
    session = session_for(handler)
    if session is None:
        return handler.reply(401, {"error": "Your session expired. Sign in again."})
    csrf = handler.headers.get("X-Guardian-CSRF", body.get("csrf", ""))
    if not isinstance(csrf, str) or not hmac.compare_digest(csrf.encode(), session.csrf.encode()):
        return handler.reply(403, {"error": "Invalid session verification. Reload the dashboard."})
    if handler.path == "/dashboard/decision":
        if type(body.get("allow")) is not bool:
            raise ValueError("Expected boolean decision")
        broker.call(broker.manager.decide, body["id"], body["fingerprint"], body["allow"], session.instance)
        return handler.reply(200, {"ok": True})
    if handler.path == "/dashboard/settings":
        timeout = body.get("approval_timeout")
        if type(timeout) is not int or not MIN_APPROVAL_TIMEOUT <= timeout <= MAX_APPROVAL_TIMEOUT:
            return handler.reply(400, {"error": f"Choose a whole number from {MIN_APPROVAL_TIMEOUT} to {MAX_APPROVAL_TIMEOUT} seconds."})
        with handler.server.settings_lock:
            try:
                persist_approval_timeout(handler.config, timeout)
            except OSError:
                return handler.reply(500, {"error": "Could not save the setting. The active timeout was not changed."})
            broker.call(broker.set_timeout, timeout)
        return handler.reply(200, {"approval_timeout": timeout,
                                   "min_timeout": MIN_APPROVAL_TIMEOUT,
                                   "max_timeout": MAX_APPROVAL_TIMEOUT})
    if handler.path in {"/dashboard/logout", "/dashboard/disconnect"}:
        broker.call(broker.manager.disconnect, session.instance)
        if handler.path == "/dashboard/logout":
            sessions.remove(session.token)
            return handler.reply(200, {"ok": True}, {
                "Set-Cookie": f"{COOKIE}=; HttpOnly; SameSite=Strict; Path=/dashboard; Max-Age=0"})
        return handler.reply(200, {"ok": True})
    handler.reply(404, {"error": "Not found"})



