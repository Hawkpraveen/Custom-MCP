"""A real MCP server with an append-only execution ledger; no email is sent."""
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from .protocol import encode, error, parse_message
from .http.listener import ExclusiveHTTPServer
from .http.lifecycle import follow_launcher

SUPPORTED = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]


class DemoServer:
    def __init__(self, ledger):
        self.ledger = Path(ledger)
        self.lock = threading.Lock()

    def handle(self, message):
        method, rpc_id = message.get("method"), message.get("id")
        if "id" not in message:
            return None
        if method == "initialize":
            version = message.get("params", {}).get("protocolVersion")
            result = {"protocolVersion": version if version in SUPPORTED else SUPPORTED[0],
                      "capabilities": {"tools": {}}, "serverInfo": {"name": "guardian-demo", "version": "0.1.0"}}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": [{"name": "record_note", "description": "Append a note to the local execution ledger. This creates a real file side effect.",
                "inputSchema": {"type": "object", "properties": {"note": {"type": "string", "maxLength": 4096}},
                                "required": ["note"], "additionalProperties": False}}]}
        elif method == "tools/call":
            params = message.get("params", {})
            args = params.get("arguments", {})
            if params.get("name") != "record_note" or not isinstance(args, dict) or not isinstance(args.get("note"), str) or len(args["note"]) > 4096 or set(args) != {"note"}:
                return error(rpc_id, "Invalid tool or arguments", -32602)
            entry = {"executed_at": time.time(), "request_id": rpc_id, "note": args["note"]}
            with self.lock:
                self.ledger.parent.mkdir(parents=True, exist_ok=True)
                with self.ledger.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(entry) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            result = {"content": [{"type": "text", "text": "Recorded note: " + args["note"]}], "isError": False}
        else:
            return error(rpc_id, "Method not found", -32601)
        return {"jsonrpc": "2.0", "id": rpc_id, "result": result}


def stdio_demo(ledger):
    demo = DemoServer(ledger)
    for line in sys.stdin.buffer:
        try:
            response = demo.handle(parse_message(line))
        except (ValueError, UnicodeError):
            response = error(None, "Invalid request", -32600)
        if response is not None:
            sys.stdout.buffer.write(encode(response))
            sys.stdout.buffer.flush()


def create_http_server(ledger, host="127.0.0.1", port=8001):
    demo = DemoServer(ledger)
    class DemoHandler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            if self.path != "/mcp":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1024 * 1024:
                    raise ValueError("Invalid size")
                response = demo.handle(parse_message(self.rfile.read(length)))
                data = b"" if response is None else encode(response)
                self.send_response(202 if response is None else 200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except (ValueError, UnicodeError):
                self.send_error(400)

        def do_GET(self):
            if self.path == "/health":
                data = json.dumps({"status": "ok", "service": "guardian-demo", "launch_id": os.environ.get("GUARDIAN_LAUNCH_ID", "manual")}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self.send_response(405)
            self.send_header("Allow", "POST")
            self.send_header("Content-Length", "0")
            self.end_headers()
    return ExclusiveHTTPServer((host, port), DemoHandler)


def http_demo(ledger, host="127.0.0.1", port=8001):
    server = create_http_server(ledger, host, port)
    follow_launcher(server)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

