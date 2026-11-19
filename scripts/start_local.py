"""Start the demo and broker with exactly one selected approval interface."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
import webbrowser
import secrets
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from guardian.config import initialize, load
from guardian.launcher import StartupError, require_free_port, wait_for_service, verify_dashboard, stop_owned_process


def main():
    parser = argparse.ArgumentParser(description="Start Guardian with one approval interface")
    parser.add_argument("--ui", choices=("tkinter", "web"), default="tkinter",
                        help="Choose the approval interface (default: tkinter)")
    args = parser.parse_args()
    if args.ui == "web" and not all((ROOT / "src/guardian/ui/react/static" / name).is_file() for name in ("index.html", "app.js", "app.css")):
        parser.error("React dashboard is not built. In src/guardian/ui/react/, run npm ci followed by npm run build.")
    os.chdir(ROOT)
    config_path = ROOT / ".guardian/config.json"
    if not config_path.exists():
        initialize(str(config_path))
    config = load(str(config_path))
    if urlsplit(config["broker_url"]).netloc not in {"127.0.0.1:8765", "localhost:8765"}:
        parser.error("The combined launcher uses local port 8765. Use manual startup for a custom broker_url.")
    try:
        for port in (8001, 8765):
            require_free_port(port)
    except StartupError as exc:
        parser.exit(1, str(exc) + "\n")
    environment = os.environ.copy()
    launch_id = secrets.token_hex(16)
    environment["GUARDIAN_LAUNCH_ID"] = launch_id
    # Optional workspace-local Tcl data, useful in restricted execution environments.
    runtime = ROOT / ".guardian/runtime"
    if (runtime / "tcl8.6/init.tcl").exists():
        environment["TCL_LIBRARY"] = str(runtime / "tcl8.6")
        environment["TK_LIBRARY"] = str(runtime / "tk8.6")
    processes = []
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    log_path = ROOT / ".guardian/local.log"
    with log_path.open("a", encoding="utf-8") as log:
        try:
            for command, url, service in [(["demo-server", "--transport", "http"], "http://127.0.0.1:8001/health", "guardian-demo"),
                                          (["serve"], "http://127.0.0.1:8765/health", "guardian")]:
                process = subprocess.Popen([sys.executable, str(ROOT / "guardian.py"), *command],
                    cwd=ROOT, env=environment, creationflags=flags, stdin=subprocess.PIPE, stdout=log, stderr=log)
                processes.append(process)
                wait_for_service(process, url, service, launch_id)
            if args.ui == "web":
                verify_dashboard("http://127.0.0.1:8765")
            if args.ui == "tkinter":
                ui = subprocess.Popen([sys.executable, str(ROOT / "guardian.py"), "ui"],
                    cwd=ROOT, env=environment, creationflags=flags, stdin=subprocess.PIPE, stdout=log, stderr=log)
                processes.append(ui)
            (ROOT / ".guardian/local-processes.json").write_text(json.dumps({
                "processes": [{"pid": p.pid} for p in processes]}), encoding="utf-8")
            if args.ui == "tkinter":
                print("Guardian started with Tkinter. Quit from its status window to stop the local services.", flush=True)
                ui.wait()
            else:
                url = "http://127.0.0.1:8765/dashboard/"
                print("Guardian started with the web interface: " + url, flush=True)
                print("Sign in using approver_token from .guardian/config.json. Keep this terminal running; Ctrl+C stops the services.", flush=True)
                webbrowser.open(url)
                while all(process.poll() is None for process in processes):
                    time.sleep(0.25)
        except KeyboardInterrupt:
            pass
        except StartupError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from None
        finally:
            for process in reversed(processes):
                stop_owned_process(process)


if __name__ == "__main__":
    main()


