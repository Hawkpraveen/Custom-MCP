"""Run a real MCP conversation through Guardian and approve it in the UI."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from guardian.client import api
from guardian.config import load


def main():
    parser = argparse.ArgumentParser(description="Interactive MCP demo client; use the real popup to allow or block")
    parser.add_argument("--config", default=".guardian/config.json")
    parser.add_argument("--transport", choices=("http", "stdio"), default="http")
    args = parser.parse_args()
    config = load(args.config)
    child = None
    if args.transport == "stdio":
        child = subprocess.Popen([sys.executable, str(ROOT / "guardian.py"), "stdio", "--config", str(Path(args.config).resolve()),
            "--server-name", "guardian-demo", "--", sys.executable, str(ROOT / "guardian.py"), "demo-server",
            "--ledger", str(ROOT / ".guardian/executions.jsonl")], stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def send(message):
        if child:
            child.stdin.write((json.dumps(message) + "\n").encode())
            child.stdin.flush()
            if "id" not in message:
                return None
            while True:
                line = child.stdout.readline()
                if not line:
                    raise RuntimeError("Gateway closed")
                result = json.loads(line)
                if result.get("id") == message["id"] and "method" not in result:
                    return result
        return api(config["broker_url"], "/mcp", config["mcp_token"], message,
                   timeout=config.get("approval_timeout", 90) + 15)

    try:
        print("Approve initialize and tools/list, then allow the first note and block the second.", flush=True)
        initialized = send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-11-25", "capabilities": {}, "clientInfo": {"name": "guardian-demo-client", "version": "0.1.0"}}})
        print("initialize:", json.dumps(initialized), flush=True)
        if "error" in initialized:
            return 1
        if child:
            send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        else:
            # Notifications return 202 with an empty body, so use the HTTP transport directly.
            from guardian.client import opener
            import urllib.request
            notification = urllib.request.Request(config["broker_url"].rstrip("/") + "/mcp",
                data=b'{"jsonrpc":"2.0","method":"notifications/initialized"}',
                headers={"Authorization": "Bearer " + config["mcp_token"], "Content-Type": "application/json"})
            with opener().open(notification, timeout=5):
                pass
        print("tools/list:", json.dumps(send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})), flush=True)
        for request_id, note in [(3, "ALLOW: this note should appear in the ledger"), (4, "BLOCK: this note must not appear in the ledger")]:
            print("Pending note:", note, flush=True)
            result = send({"jsonrpc": "2.0", "id": request_id, "method": "tools/call",
                           "params": {"name": "record_note", "arguments": {"note": note}}})
            print("Response:", json.dumps(result), flush=True)
        print("Inspect .guardian/executions.jsonl for execution evidence.", flush=True)
    finally:
        if child:
            child.stdin.close()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.terminate()
                child.wait(timeout=3)
            child.stdout.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

