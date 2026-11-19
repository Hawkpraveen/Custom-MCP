"""Real loopback servers and clients used by transport integration tests."""
import concurrent.futures
import json
import secrets
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from guardian.client import api, opener
from guardian.demo import create_http_server
from guardian.http.server import GuardianHTTPServer


def call(request_id=1, note="test"):
    return {"jsonrpc": "2.0", "id": request_id, "method": "tools/call",
            "params": {"name": "record_note", "arguments": {"note": note}}}


class Harness:
    def __init__(self, timeout=2):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = Path(self.temp.name) / "executions.jsonl"
        self.demo = create_http_server(self.ledger, port=0)
        self.config = {key + "_token": secrets.token_urlsafe(32) for key in ("producer", "approver", "mcp")}
        self.config.update({"approval_timeout": timeout, "lease_seconds": 5,
                            "allowed_origins": ["https://claude.ai"], "server_name": "test demo",
                            "upstream_url": f"http://127.0.0.1:{self.demo.server_port}/mcp"})
        self.gateway = GuardianHTTPServer(("127.0.0.1", 0), self.config)
        self.base = f"http://127.0.0.1:{self.gateway.server_port}"
        self.config["broker_url"] = self.base
        self.config_file = Path(self.temp.name) / "config.json"
        self.config_file.write_text(json.dumps(self.config), encoding="utf-8")
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=16)
        self.threads = []
        for server in (self.demo, self.gateway):
            thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
            thread.start()
            self.threads.append(thread)
        self.instance = "test-approver"
        self.snapshot()

    def snapshot(self):
        request = urllib.request.Request(self.base + "/api/pending", headers={
            "Authorization": "Bearer " + self.config["approver_token"], "X-Guardian-Instance": self.instance})
        with opener().open(request, timeout=3) as response:
            return json.load(response)["pending"]

    def pending(self, count=1):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            pending = self.snapshot()
            if len(pending) == count:
                return pending
            time.sleep(0.02)
        raise AssertionError(f"Expected {count} pending requests, got {len(pending)}")

    def decide(self, pending, allow):
        return api(self.base, "/api/decision", self.config["approver_token"], {
            "id": pending["id"], "fingerprint": pending["fingerprint"], "allow": allow, "instance": self.instance})

    def post(self, message):
        return api(self.base, "/mcp", self.config["mcp_token"], message, timeout=6)

    def submit(self, message):
        return self.pool.submit(self.post, message)

    def entries(self):
        if not self.ledger.exists():
            return []
        return [json.loads(line) for line in self.ledger.read_text(encoding="utf-8").splitlines()]

    def close(self):
        self.gateway.shutdown()
        self.gateway.server_close()
        self.demo.shutdown()
        self.demo.server_close()
        self.pool.shutdown(wait=True, cancel_futures=True)
        for thread in self.threads:
            thread.join(timeout=2)
        self.temp.cleanup()

