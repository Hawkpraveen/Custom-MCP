"""Startup checks that reject occupied ports and unrelated or stale services."""
import json
import os
import socket
import subprocess
import time
import urllib.error

from .client import opener


class StartupError(RuntimeError):
    pass


def stop_owned_process(process):
    """Stop only a launcher-owned process, including its Windows venv redirector child."""
    if process.poll() is not None:
        return
    if process.stdin is not None:
        process.stdin.close()
        try:
            process.wait(timeout=3)
            return
        except subprocess.TimeoutExpired:
            pass
    if os.name == "nt":
        # Windows venv python.exe starts the base interpreter as a child. Killing
        # only the redirector can leave that child serving the old gateway.
        result = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode == 0:
            process.wait(timeout=3)
            return
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def require_free_port(port):
    with socket.socket() as probe:
        probe.settimeout(0.5)
        if probe.connect_ex(("127.0.0.1", port)) == 0:
            owners = windows_listener_pids(port) if os.name == "nt" else []
            detail = f" Listener PID(s): {', '.join(map(str, owners))}." if owners else ""
            raise StartupError(f"Port {port} is already in use.{detail} Stop the previous Guardian launcher with Ctrl+C, then retry. If it has already closed, inspect the listener PID and stop only the verified old Guardian process. No existing process was replaced.")


def windows_listener_pids(port):
    """Read listener ownership for diagnostics, never terminate a discovered PID."""
    try:
        result = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True,
                                text=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return parse_listener_pids(result.stdout, port)


def parse_listener_pids(output, port):
    owners = set()
    for line in output.splitlines():
        fields = line.split()
        if len(fields) == 5 and fields[0] == "TCP" and fields[3] == "LISTENING":
            address = fields[1].rsplit(":", 1)
            if len(address) == 2 and address[1] == str(port) and fields[4].isdigit():
                owners.add(int(fields[4]))
    return sorted(owners)


def wait_for_service(process, url, service, launch_id, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise StartupError(f"The {service} process exited during startup. Inspect .guardian/local.log.")
        try:
            with opener().open(url, timeout=0.5) as response:
                health = json.load(response)
            if health.get("service") != service or health.get("launch_id") != launch_id:
                raise StartupError(f"A different or older service answered for {service}. Stop previous Guardian instances before retrying.")
            if health.get("status") == "ok" and process.poll() is None:
                return
        except (OSError, ValueError):
            time.sleep(0.1)
    raise StartupError(f"The {service} process did not become ready. Inspect .guardian/local.log.")


def verify_dashboard(base):
    for name, content_type in [("", "text/html"), ("app.js", "text/javascript"),
                               ("app.css", "text/css"), ("service-worker.js", "text/javascript")]:
        try:
            with opener().open(base.rstrip("/") + "/dashboard/" + name, timeout=2) as response:
                if response.status != 200 or response.headers.get_content_type() != content_type:
                    raise StartupError("The running gateway is not serving the React dashboard. Restart it after updating the source.")
                response.read(256)
        except (OSError, urllib.error.HTTPError):
            raise StartupError("The React dashboard is unavailable. Build it with npm ci and npm run build in src/guardian/ui/react/, then restart Guardian.") from None

