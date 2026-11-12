"""Local-only preflight checks; full P53 acceptance uses p53_acceptance.py."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import p53_acceptance as gate


class P53AcceptancePreflightTests(unittest.TestCase):
    def test_missing_original_source_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(gate, "TOOL_ROOT", Path(tmp)):
                with self.assertRaisesRegex(RuntimeError, "authorized full P53 checkout missing"):
                    gate.perform()
            self.assertFalse(list(Path(tmp).iterdir()))

    def test_synthetic_source_fixtures_are_deterministic_and_local(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = gate.write_fixtures(Path(tmp))
            original_a, original_b = gate.snapshot(a), gate.snapshot(b)
            self.assertEqual(len(original_a), 4)
            self.assertEqual(len(original_b), 4)
            self.assertNotEqual(original_a["src/lib.ts"], original_b["src/lib.ts"])
            self.assertEqual(original_a, gate.snapshot(a))
            self.assertEqual(original_b, gate.snapshot(b))
            self.assertIn("SYNTHETIC_NEVER_IN_BUYER_ZIP", (a / "src/private-marker-ONLY-FOR-TEST.ts").read_text())


if __name__ == "__main__":
    unittest.main()
