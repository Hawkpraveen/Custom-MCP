"""Prevent duplicate listeners and false readiness from old gateway processes."""
import unittest
import socket
import subprocess
import sys
import os
from pathlib import Path
from unittest.mock import Mock

from support import Harness, ROOT
from guardian.demo import create_http_server
from guardian.http.server import GuardianHTTPServer
from guardian.launcher import StartupError, require_free_port, verify_dashboard, wait_for_service, stop_owned_process, parse_listener_pids


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.addCleanup(self.h.close)

    def test_second_gateway_cannot_bind_the_same_port(self):
        with self.assertRaises(OSError):
            GuardianHTTPServer(("127.0.0.1", self.h.gateway.server_port), self.h.config)

    def test_second_demo_cannot_bind_the_same_port(self):
        with self.assertRaises(OSError):
            create_http_server(self.h.ledger, port=self.h.demo.server_port)

    def test_occupied_port_is_reported_before_launch(self):
        with self.assertRaisesRegex(StartupError, "already in use"):
            require_free_port(self.h.gateway.server_port)

    def test_listener_diagnostics_ignore_peer_ports_and_closed_connections(self):
        output = """TCP 127.0.0.1:8001 0.0.0.0:0 LISTENING 123
TCP 127.0.0.1:18001 0.0.0.0:0 LISTENING 999
TCP 127.0.0.1:8001 127.0.0.1:4000 TIME_WAIT 0
TCP 127.0.0.1:4000 127.0.0.1:8001 ESTABLISHED 456"""
        self.assertEqual(parse_listener_pids(output, 8001), [123])

    def test_old_health_response_cannot_satisfy_a_new_launch(self):
        process = Mock()
        process.poll.return_value = None
        with self.assertRaisesRegex(StartupError, "different or older"):
            wait_for_service(process, self.h.base + "/health", "guardian", "new-launch", timeout=1)

    def test_exited_child_is_not_reported_as_ready(self):
        process = Mock()
        process.poll.return_value = 1
        with self.assertRaisesRegex(StartupError, "exited during startup"):
            wait_for_service(process, self.h.base + "/health", "guardian", "manual")

    def test_current_dashboard_is_verified_before_browser_launch(self):
        verify_dashboard(self.h.base)

    def test_shutdown_releases_child_listener_including_venv_interpreters(self):
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        environment = dict(os.environ, GUARDIAN_LAUNCH_ID="shutdown-regression")
        process = subprocess.Popen([sys.executable, str(ROOT / "guardian.py"), "serve", "--config", str(self.h.config_file), "--port", str(port)],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment)
        try:
            wait_for_service(process, f"http://127.0.0.1:{port}/health", "guardian", "shutdown-regression")
            stop_owned_process(process)
            with socket.socket() as probe:
                probe.settimeout(0.5)
                self.assertNotEqual(probe.connect_ex(("127.0.0.1", port)), 0)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=3)
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()

