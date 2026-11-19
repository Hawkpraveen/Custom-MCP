import json
import queue
import subprocess
import sys
import threading
import unittest

from support import Harness, ROOT, call


class StdioIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness(timeout=2)
        self.addCleanup(self.h.close)
        launcher = str(ROOT / "guardian.py")
        self.process = subprocess.Popen([sys.executable, launcher, "stdio", "--config", str(self.h.config_file), "--",
            sys.executable, launcher, "demo-server", "--ledger", str(self.h.ledger)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.output = queue.Queue()
        def read():
            for line in self.process.stdout:
                self.output.put(json.loads(line))
        threading.Thread(target=read, daemon=True).start()
        self.addCleanup(self.cleanup_process)

    def cleanup_process(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        for stream in (self.process.stdin, self.process.stdout, self.process.stderr):
            stream.close()

    def send(self, message):
        self.process.stdin.write((json.dumps(message) + "\n").encode())
        self.process.stdin.flush()

    def test_real_subprocess_approval_and_blocking(self):
        self.send(call(1, "allowed stdio"))
        pending = self.h.pending()[0]
        self.assertTrue(self.output.empty())
        self.assertEqual(self.h.entries(), [])
        self.h.decide(pending, True)
        self.assertIn("result", self.output.get(timeout=3))
        self.send(call(2, "blocked stdio"))
        self.h.decide(self.h.pending()[0], False)
        self.assertIn("error", self.output.get(timeout=3))
        self.assertEqual([e["note"] for e in self.h.entries()], ["allowed stdio"])

    def test_concurrent_stdio_calls(self):
        self.send(call(1, "first"))
        self.send(call(2, "second"))
        pending = {p["message"]["id"]: p for p in self.h.pending(2)}
        self.h.decide(pending[2], True)
        self.h.decide(pending[1], False)
        responses = [self.output.get(timeout=3), self.output.get(timeout=3)]
        self.assertEqual({r["id"] for r in responses}, {1, 2})
        self.assertEqual([e["note"] for e in self.h.entries()], ["second"])

    def test_stdio_cancellation_prevents_late_execution(self):
        self.send(call(1))
        pending = self.h.pending()[0]
        self.send({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 1}})
        self.h.pending(0)
        self.assertTrue(self.output.empty())
        self.assertEqual(self.h.entries(), [])

