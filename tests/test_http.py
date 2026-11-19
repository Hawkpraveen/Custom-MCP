import json
import socket
import time
import unittest
import urllib.error
import urllib.request

from support import Harness, call
from guardian.client import api, opener


class HTTPIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.addCleanup(self.h.close)

    def test_allow_executes_only_after_decision(self):
        future = self.h.submit(call(note="approved"))
        pending = self.h.pending()[0]
        self.assertFalse(future.done())
        self.assertEqual(self.h.entries(), [])
        self.h.decide(pending, True)
        self.assertIn("result", future.result(timeout=3))
        self.assertEqual([e["note"] for e in self.h.entries()], ["approved"])

    def test_block_never_executes(self):
        future = self.h.submit(call(note="blocked"))
        self.h.decide(self.h.pending()[0], False)
        self.assertIn("error", future.result(timeout=3))
        self.assertEqual(self.h.entries(), [])

    def test_concurrent_mixed_decisions_match_exact_requests(self):
        futures = {i: self.h.submit(call(i, f"note-{i}")) for i in range(8)}
        pending = self.h.pending(8)
        for item in reversed(pending):
            self.h.decide(item, item["message"]["id"] % 2 == 0)
        for i, future in futures.items():
            result = future.result(timeout=3)
            self.assertIn("result" if i % 2 == 0 else "error", result)
        self.assertEqual({e["request_id"] for e in self.h.entries()}, {0, 2, 4, 6})

    def test_initialize_is_forwarded_and_tools_list_requires_approval(self):
        initialized = self.h.post({"jsonrpc": "2.0", "id": "initialize", "method": "initialize"})
        self.assertIn("result", initialized)
        self.assertEqual(self.h.pending(0), [])

        future = self.h.submit({"jsonrpc": "2.0", "id": "tools-list", "method": "tools/list"})
        pending = self.h.pending()[0]
        self.assertEqual(pending["message"]["method"], "tools/list")
        self.assertFalse(future.done())
        self.h.decide(pending, True)
        self.assertIn("result", future.result(timeout=3))

    def test_missing_ui_fails_closed(self):
        api(self.h.base, "/api/disconnect", self.h.config["approver_token"], {"instance": self.h.instance})
        self.assertIn("error", self.h.post(call()))
        self.assertEqual(self.h.entries(), [])

    def test_timeout_rejects_stale_approval(self):
        self.h.gateway.broker.call(setattr, self.h.gateway.broker.manager, "timeout", 0.2)
        future = self.h.submit(call())
        pending = self.h.pending()[0]
        self.assertIn("error", future.result(timeout=3))
        with self.assertRaises(urllib.error.HTTPError):
            self.h.decide(pending, True)
        self.assertEqual(self.h.entries(), [])

    def test_wrong_role_and_origin_are_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            api(self.h.base, "/api/pending", self.h.config["mcp_token"])
        self.assertEqual(caught.exception.code, 401)
        request = urllib.request.Request(self.h.base + "/mcp", data=json.dumps(call()).encode(), headers={
            "Authorization": "Bearer " + self.h.config["mcp_token"], "Origin": "https://attacker.example"})
        with self.assertRaises(urllib.error.HTTPError) as caught:
            opener().open(request)
        self.assertEqual(caught.exception.code, 403)

    def test_notification_cannot_bypass_tool_approval(self):
        message = call()
        del message["id"]
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.h.post(message)
        self.assertEqual(caught.exception.code, 400)
        self.assertEqual(self.h.entries(), [])

    def test_client_disconnect_cancels_pending_request(self):
        sock = socket.create_connection(("127.0.0.1", self.h.gateway.server_port))
        raw = json.dumps(call()).encode()
        headers = ("POST /mcp HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer " + self.h.config["mcp_token"] +
                   "\r\nContent-Length: " + str(len(raw)) + "\r\n\r\n").encode()
        sock.sendall(headers + raw)
        pending = self.h.pending()[0]
        sock.close()
        self.h.pending(0)
        with self.assertRaises(urllib.error.HTTPError):
            self.h.decide(pending, True)
        self.assertEqual(self.h.entries(), [])

    def test_duplicate_inflight_ids_are_rejected(self):
        first = self.h.submit(call(7))
        pending = self.h.pending()[0]
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.h.post(call(7, "duplicate"))
        self.assertEqual(caught.exception.code, 409)
        self.h.decide(pending, False)
        self.assertIn("error", first.result(timeout=3))


