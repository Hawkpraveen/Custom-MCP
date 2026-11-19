"""Forward an approved HTTP message and stream the upstream response."""
import urllib.error
import urllib.request
from ..client import opener


def relay_http(handler, body):
    url = handler.config.get("upstream_url")
    if not url:
        return handler.reply(503, {"error": "No upstream configured"})
    # Upstream address is operator-configured, never derived from a request.
    headers = {}
    for key, value in handler.headers.items():
        if key.lower() in {"accept", "content-type", "mcp-session-id", "mcp-protocol-version", "last-event-id", "mcp-method", "mcp-name"} or key.lower().startswith("mcp-param-"):
            headers[key] = value
    if handler.config.get("upstream_token"):
        headers["Authorization"] = "Bearer " + handler.config["upstream_token"]
    request = urllib.request.Request(url, data=body, headers=headers, method=handler.command)
    try:
        upstream = opener().open(request, timeout=120)
    except urllib.error.HTTPError as exc:
        upstream = exc
    except (OSError, urllib.error.URLError):
        return handler.reply(502, {"error": "Upstream unavailable; no automatic retry"})
    with upstream:
        handler.send_response(upstream.status)
        for key in ("Content-Type", "Mcp-Session-Id", "MCP-Protocol-Version", "Allow", "WWW-Authenticate"):
            if key in upstream.headers:
                handler.send_header(key, upstream.headers[key])
        handler.send_header("Cache-Control", "no-store")
        handler.send_header("X-Accel-Buffering", "no")
        handler.send_header("Connection", "close")
        handler.end_headers()
        handler.close_connection = True
        # Close-delimited HTTP/1.1 streams preserve JSON and SSE without buffering.
        while True:
            chunk = upstream.read1(16384)
            if not chunk:
                break
            handler.wfile.write(chunk)
            handler.wfile.flush()

