import json
import unittest

from support import call
from guardian.protocol import parse_message, requires_approval
from guardian.config import validate_url


class ProtocolTests(unittest.TestCase):
    def test_duplicate_json_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            parse_message('{"jsonrpc":"2.0","id":1,"method":"ping","method":"tools/call"}')

    def test_setup_handshakes_bypass_approval_and_operations_are_gated(self):
        for method in ("tools/list", "tools/call", "resources/read", "prompts/get", "ping", "custom/action"):
            message = {"jsonrpc": "2.0", "id": 0, "method": method}
            self.assertTrue(requires_approval(parse_message(json.dumps(message))))
        for method in ("initialize", "server/discover"):
            message = {"jsonrpc": "2.0", "id": 1, "method": method}
            self.assertFalse(requires_approval(parse_message(json.dumps(message))))

    def test_malformed_messages_fail_closed(self):
        for value in ([call()], {"jsonrpc": "1.0", "id": 1, "method": "ping"},
                      {"jsonrpc": "2.0", "id": True, "method": "ping"},
                      {"jsonrpc": "2.0", "id": None, "method": "ping"},
                      {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": []}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_message(json.dumps(value))

    def test_remote_plaintext_and_credentials_in_url_are_rejected(self):
        for url in ("http://public.example", "https://user:password@example.com", "https://example.com?token=secret"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url(url)
        validate_url("https://example.com")
        validate_url("http://127.0.0.1:8765")



