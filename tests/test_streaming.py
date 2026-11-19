import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from support import Harness, call
from guardian.client import opener


class UpstreamHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        self.server.seen.append((dict(self.headers), self.rfile.read(int(self.headers["Content-Length"]))))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Mcp-Session-Id", "upstream-session")
        self.end_headers()
        self.wfile.write(b'event: message\ndata: {"jsonrpc":"2.0","method":"notifications/progress"}\n\n')
        self.wfile.flush()
        self.server.release.wait(timeout=3)
        self.wfile.write(b'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"content":[]}}\n\n')
        self.wfile.flush()


class StreamingTests(unittest.TestCase):
    def setUp(self):
        self.h = Harness()
        self.addCleanup(self.h.close)
        self.upstream = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
        self.upstream.seen = []
        self.upstream.release = threading.Event()
        self.thread = threading.Thread(target=self.upstream.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()
        self.h.config["upstream_url"] = f"http://127.0.0.1:{self.upstream.server_port}/mcp"
        self.addCleanup(self.cleanup_upstream)

    def cleanup_upstream(self):
        self.upstream.release.set()
        self.upstream.shutdown()
        self.upstream.server_close()
        self.thread.join(timeout=2)

    def test_sse_is_streamed_and_credentials_are_separated(self):
        self.h.config["upstream_token"] = "independent-upstream-token"
        request = urllib.request.Request(self.h.base + "/mcp", data=json.dumps(call()).encode(), headers={
            "Authorization": "Bearer " + self.h.config["mcp_token"],
            "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-11-25"})
        future = self.h.pool.submit(opener().open, request, timeout=5)
        self.h.decide(self.h.pending()[0], True)
        with future.result(timeout=3) as response:
            self.assertEqual(response.headers["Mcp-Session-Id"], "upstream-session")
            # The upstream has not sent its final result: an early line proves no whole-response buffering.
            first_line = self.h.pool.submit(response.readline)
            self.assertEqual(first_line.result(timeout=1), b"event: message\n")
            self.upstream.release.set()
            self.assertIn(b'"result"', response.read())
        headers, raw = self.upstream.seen[0]
        self.assertEqual(headers["Authorization"], "Bearer independent-upstream-token")
        self.assertEqual(json.loads(raw), call())
        self.assertEqual(len(self.upstream.seen), 1)

    def test_unreachable_upstream_does_not_retry(self):
        # Shut down the test upstream, retaining its now-closed port in config.
        self.upstream.shutdown()
        self.upstream.server_close()
        future = self.h.submit(call())
        self.h.decide(self.h.pending()[0], True)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            future.result(timeout=3)
        self.assertEqual(caught.exception.code, 502)
        self.assertEqual(self.h.entries(), [])

