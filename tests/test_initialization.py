"""Exercise first-run and repeated CLI initialization without replacing secrets."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from support import ROOT
from guardian.config import ConfigurationError, initialize, load


class InitializationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Path(self.temp.name) / "private" / "config.json"

    def run_init(self):
        return subprocess.run([sys.executable, str(ROOT / "guardian.py"), "init", "--config", str(self.config)],
                              capture_output=True, text=True, timeout=10)

    def test_repeated_init_succeeds_and_preserves_exact_file_contents(self):
        first = self.run_init()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("Created private configuration", first.stdout)
        before = self.config.read_bytes()
        second = self.run_init()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("already exists and is valid", second.stdout)
        self.assertEqual(self.config.read_bytes(), before)
        for key in ("producer_token", "approver_token", "mcp_token"):
            self.assertNotIn(load(str(self.config))[key], first.stdout + second.stdout + second.stderr)

    def test_invalid_existing_json_is_explained_and_preserved(self):
        self.config.parent.mkdir()
        original = b'{"secret":"DO-NOT-PRINT", broken}'
        self.config.write_bytes(original)
        result = self.run_init()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Configuration error", result.stderr)
        self.assertIn("valid UTF-8 JSON", result.stderr)
        self.assertNotIn("DO-NOT-PRINT", result.stderr)
        self.assertEqual(self.config.read_bytes(), original)

    def test_invalid_token_types_return_safe_validation_errors(self):
        initialize(str(self.config))
        value = json.loads(self.config.read_text())
        value["producer_token"] = None
        self.config.write_text(json.dumps(value))
        result = self.run_init()
        self.assertEqual(result.returncode, 1)
        self.assertIn("producer_token must be a string", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_powershell_utf8_bom_is_accepted(self):
        initialize(str(self.config))
        original = self.config.read_bytes()
        self.config.write_bytes(b"\xef\xbb\xbf" + original)
        self.assertEqual(self.run_init().returncode, 0)

    def test_non_object_config_and_wrong_timeout_are_rejected(self):
        self.config.parent.mkdir()
        self.config.write_text("[]")
        with self.assertRaises(ConfigurationError):
            load(str(self.config))
        fresh = Path(self.temp.name) / "other.json"
        initialize(str(fresh))
        value = load(str(fresh))
        value["approval_timeout"] = "ninety"
        fresh.write_text(json.dumps(value))
        with self.assertRaises(ConfigurationError):
            load(str(fresh))

