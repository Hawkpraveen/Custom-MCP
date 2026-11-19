"""Background approval-channel I/O; this module never calls Tk."""
import json
import queue
import threading
import urllib.request
import uuid

from ...client import api, opener


class ApprovalConnection:
    def __init__(self, config):
        self.config = config
        self.instance = str(uuid.uuid4())
        self.events = queue.Queue()
        self.actions = queue.Queue()
        self.stopped = threading.Event()

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def decide(self, pending, allow):
        self.actions.put({"id": pending["id"], "fingerprint": pending["fingerprint"],
                          "allow": allow, "instance": self.instance})

    def _send_decisions(self):
        while True:
            try:
                action = self.actions.get_nowait()
            except queue.Empty:
                return
            try:
                api(self.config["broker_url"], "/api/decision", self.config["approver_token"], action)
                self.events.put(("decided", action["id"]))
            except Exception:
                self.events.put(("decision_failed", action["id"]))

    def _run(self):
        while not self.stopped.is_set():
            try:
                self._send_decisions()
                request = urllib.request.Request(self.config["broker_url"].rstrip("/") + "/api/pending",
                    headers={"Authorization": "Bearer " + self.config["approver_token"],
                             "X-Guardian-Instance": self.instance})
                with opener().open(request, timeout=3) as response:
                    self.events.put(("snapshot", json.load(response)["pending"]))
            except Exception:
                self.events.put(("offline", None))
            self.stopped.wait(0.6)

    def close(self):
        self.stopped.set()
        def disconnect():
            try:
                api(self.config["broker_url"], "/api/disconnect", self.config["approver_token"],
                    {"instance": self.instance}, 2)
            except Exception:
                pass  # The server's heartbeat lease independently expires.
        threading.Thread(target=disconnect, daemon=True).start()


