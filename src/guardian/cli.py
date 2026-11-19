"""Command-line entry points; stdout is reserved for MCP in stdio mode."""
import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

from .config import ConfigurationError, initialize, load


def main():
    parser = argparse.ArgumentParser(description="MCP Guardian â€” human authorization before execution")
    sub = parser.add_subparsers(dest="action", required=True)
    init = sub.add_parser("init", help="Generate private, independent role tokens")
    init.add_argument("--config", default=".guardian/config.json")
    for name in ("serve", "ui", "stdio", "desktop-config", "web-config"):
        command = sub.add_parser(name)
        command.add_argument("--config", default=".guardian/config.json")
        if name == "serve":
            command.add_argument("--host", default="127.0.0.1")
            command.add_argument("--port", type=int, default=8765)
        if name == "stdio":
            command.add_argument("--server-name", default="upstream MCP")
            command.add_argument("command", nargs=argparse.REMAINDER)
        if name == "web-config":
            command.add_argument("--public-url", required=True, help="Public HTTPS gateway origin, without /mcp")
    demo = sub.add_parser("demo-server")
    demo.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    demo.add_argument("--ledger", default=".guardian/executions.jsonl")
    demo.add_argument("--host", default="127.0.0.1")
    demo.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s", stream=sys.stderr)
    try:
        if args.action == "init":
            try:
                target = initialize(args.config)
            except FileExistsError:
                load(args.config)
                print("Configuration already exists and is valid:", Path(args.config).resolve())
                print("Existing credentials were preserved. Next: python scripts/start_local.py")
            else:
                print("Created private configuration:", target)
                print("Next: python scripts/start_local.py")
            return
        if args.action == "demo-server":
            from .demo import http_demo, stdio_demo
            if args.transport == "http":
                http_demo(args.ledger, args.host, args.port)
            else:
                stdio_demo(args.ledger)
            return
        config = load(args.config)
        if args.action == "serve":
            from .http.server import serve
            config["_guardian_config_path"] = str(Path(args.config).resolve())
            serve(config, args.host, args.port)
        elif args.action == "ui":
            from .ui.tkinter.app import ApprovalApp
            ApprovalApp(config).run()
        elif args.action == "stdio":
            from .gateway.stdio_proxy import proxy
            command = args.command[1:] if args.command[:1] == ["--"] else args.command
            asyncio.run(proxy(config, command, args.server_name))
        elif args.action == "desktop-config":
            launcher = str(Path(__file__).resolve().parents[2] / "guardian.py")
            command = [launcher, "stdio", "--config", str(Path(args.config).resolve()), "--server-name", "guardian-demo", "--",
                       sys.executable, launcher, "demo-server", "--ledger", str(Path(".guardian/executions.jsonl").resolve())]
            print(json.dumps({"mcpServers": {"guardian-demo": {"command": sys.executable, "args": command}}}, indent=2))
        elif args.action == "web-config":
            from .config import validate_url
            validate_url(args.public_url)
            if not args.public_url.startswith("https://"):
                raise ValueError("Claude Web requires HTTPS")
            target = Path(args.config).resolve().parent / "claude-web-connection.txt"
            text = "PRIVATE â€” do not commit or record this file in a demo.\nMCP URL: " + args.public_url.rstrip("/") + "/mcp\nRequest header: Authorization\nValue: Bearer " + config["mcp_token"] + "\n"
            with target.open("x", encoding="utf-8") as stream:
                stream.write(text)
            print("Wrote private connector instructions to", target)
    except ConfigurationError as exc:
        print("Configuration error: " + str(exc), file=sys.stderr)
        print("The existing file was not changed. Correct it, or initialize a separate file with --config .guardian/new-config.json.", file=sys.stderr)
        raise SystemExit(1) from None
    except FileNotFoundError:
        print("A required file or executable was not found. Check --config and upstream executable paths; run python guardian.py init for first-time setup.", file=sys.stderr)
        raise SystemExit(1) from None
    except PermissionError:
        print("Permission denied. Check access to the configuration directory, files, and executable.", file=sys.stderr)
        raise SystemExit(1) from None
    except FileExistsError:
        print("The output file already exists and was preserved. For web-config, inspect the existing .guardian/claude-web-connection.txt privately.", file=sys.stderr)
        raise SystemExit(1) from None
    except (ValueError, OSError, KeyError):
        # Do not echo config contents, upstream command arguments, URLs, or tokens.
        print("Guardian could not start. Check configuration, paths, ports, and command syntax.", file=sys.stderr)
        raise SystemExit(1) from None


