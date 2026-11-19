"""Cooperative shutdown when a combined launcher's lifetime pipe closes."""
import os
import sys
import threading


def follow_launcher(server):
    if not os.environ.get("GUARDIAN_LAUNCH_ID"):
        return
    def watch():
        try:
            sys.stdin.buffer.read()
        finally:
            server.shutdown()
    threading.Thread(target=watch, daemon=True).start()
