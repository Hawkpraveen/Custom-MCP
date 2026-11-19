"""Browser approval routes exercised against real gateway and upstream sockets."""
import http.cookiejar
import json
import unittest
import urllib.error
import urllib.request

from support import Harness, call
from guardian.client import api


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.addCleanup(self.h.close)
        api(self.h.base, "/api/disconnect", self.h.config["approver_token"], {"instance": self.h.instance})
        self.browser = urllib.request.build_opener(urllib.request.ProxyHandler({}),
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.csrf = None

    def request(self, path, body=None, headers=None):
        values = {"Content-Type": "application/json"}
        if body is not None:
            values["Origin"] = self.h.base
        if self.csrf:
            values["X-Guardian-CSRF"] = self.csrf
        values.update(headers or {})
        request = urllib.request.Request(self.h.base + "/dashboard/" + path,
            data=None if body is None else json.dumps(body).encode(), headers=values)
        return self.browser.open(request, timeout=4)

    def login(self):
        with self.request("session", {"token": self.h.config["approver_token"]}) as response:
            self.assertIn("HttpOnly", response.headers["Set-Cookie"])
            self.assertIn("SameSite=Strict", response.headers["Set-Cookie"])
            self.csrf = json.load(response)["csrf"]

    def pending(self, count=1):
        import time
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            with self.request("pending") as response:
                pending = json.load(response)["pending"]
            if len(pending) == count:
                return pending
            time.sleep(0.02)
        self.fail(f"Expected {count} requests, got {len(pending)}")

    def decide(self, pending, allow):
        with self.request("decision", {"id": pending["id"], "fingerprint": pending["fingerprint"], "allow": allow}) as response:
            self.assertTrue(json.load(response)["ok"])

    def test_static_assets_and_security_headers(self):
        for path in ("", "app.js", "app.css", "service-worker.js"):
            with self.request(path) as response:
                data = response.read().decode()
                self.assertEqual(response.status, 200)
                self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
                self.assertNotIn(self.h.config["approver_token"], data)
                self.assertTrue(data)

    def test_login_required_and_wrong_role_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("pending")
        self.assertEqual(caught.exception.code, 401)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("session", {"token": self.h.config["mcp_token"]})
        self.assertEqual(caught.exception.code, 401)

    def test_browser_approval_and_denial_gate_real_execution(self):
        self.login()
        first = self.h.submit(call(1, "browser approved"))
        pending = self.pending()[0]
        self.assertFalse(first.done())
        self.assertEqual(self.h.entries(), [])
        self.decide(pending, True)
        self.assertIn("result", first.result(timeout=3))
        second = self.h.submit(call(2, "browser blocked"))
        self.decide(self.pending()[0], False)
        self.assertIn("error", second.result(timeout=3))
        self.assertEqual([entry["note"] for entry in self.h.entries()], ["browser approved"])

    def test_browser_decisions_are_consumed_once(self):
        self.login()
        future = self.h.submit(call())
        pending = self.pending()[0]
        self.decide(pending, True)
        self.assertIn("result", future.result(timeout=3))
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.decide(pending, True)
        self.assertEqual(caught.exception.code, 409)
        self.assertEqual(len(self.h.entries()), 1)

    def test_timeout_setting_is_saved_and_applies_to_new_requests_only(self):
        self.login()
        self.h.config["_guardian_config_path"] = str(self.h.config_file)
        before = self.h.gateway.broker.call(
            self.h.gateway.broker.manager.create, "demo", "test", "before",
            call(100, "already pending"))
        original_deadline = before.deadline
        with self.request("settings") as response:
            self.assertEqual(json.load(response)["approval_timeout"], 2)
        with self.request("settings", {"approval_timeout": 240}) as response:
            self.assertEqual(json.load(response)["approval_timeout"], 240)
        self.assertEqual(self.h.gateway.broker.manager.timeout, 240)
        self.assertEqual(before.deadline, original_deadline)
        self.assertEqual(json.loads(self.h.config_file.read_text())["approval_timeout"], 240)
        after = self.h.gateway.broker.call(
            self.h.gateway.broker.manager.create, "demo", "test", "after",
            call(101, "new request"))
        self.assertGreater(after.deadline - after.created, 239)
        self.h.gateway.broker.call(self.h.gateway.broker.manager.finish, before, "cancelled")
        self.h.gateway.broker.call(self.h.gateway.broker.manager.finish, after, "cancelled")

    def test_invalid_timeout_settings_are_rejected_without_changes(self):
        self.login()
        for value in (True, 0, 601, "240", 2.5):
            with self.subTest(value=value), self.assertRaises(urllib.error.HTTPError) as caught:
                self.request("settings", {"approval_timeout": value})
            self.assertEqual(caught.exception.code, 400)
        self.assertEqual(self.h.gateway.broker.manager.timeout, 2)

    def test_tkinter_and_browser_are_mutually_exclusive(self):
        self.h.snapshot()
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.login()
        self.assertEqual(caught.exception.code, 409)
        api(self.h.base, "/api/disconnect", self.h.config["approver_token"], {"instance": self.h.instance})
        self.login()
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.h.snapshot()
        self.assertEqual(caught.exception.code, 409)

    def test_csrf_and_foreign_origins_are_rejected(self):
        self.login()
        for headers in ({"X-Guardian-CSRF": "wrong"}, {"Origin": "https://attacker.example"}):
            with self.subTest(headers=headers), self.assertRaises(urllib.error.HTTPError) as caught:
                self.request("logout", {}, headers)
            self.assertEqual(caught.exception.code, 403)

    def test_public_host_cannot_access_dashboard(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("", headers={"Host": "public-tunnel.example"})
        self.assertEqual(caught.exception.code, 403)

    def test_browser_logout_blocks_pending_work_and_revokes_session(self):
        self.login()
        future = self.h.submit(call())
        self.pending()
        with self.request("logout", {}):
            pass
        self.assertIn("error", future.result(timeout=3))
        self.assertEqual(self.h.entries(), [])
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("pending")
        self.assertEqual(caught.exception.code, 401)

    def test_page_disconnect_releases_lease_without_replaying(self):
        self.login()
        future = self.h.submit(call())
        self.pending()
        with self.request("disconnect", {"csrf": self.csrf}):
            pass
        self.assertIn("error", future.result(timeout=3))
        self.h.snapshot()  # Tkinter can acquire ownership after browser disconnect.
        self.assertEqual(self.h.entries(), [])

    def test_login_attempts_are_rate_limited(self):
        for attempt in range(6):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                self.request("session", {"token": "wrong"})
            self.assertEqual(caught.exception.code, 401 if attempt < 5 else 429)

