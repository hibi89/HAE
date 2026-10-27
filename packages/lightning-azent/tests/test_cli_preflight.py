"""Fail-closed LA CLI: invalid commands must never initialize SQLite files."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]
FIXTURES = REPO_ROOT / "docs" / "lightning-azent" / "fixtures"


class CliNoWritePreflightTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.env = dict(os.environ)
        self.env["PYTHONPATH"] = str(PACKAGE_ROOT)

    def reject_without_db(self, plan_name, command, extra):
        original = FIXTURES / plan_name
        plan = self.root / plan_name
        plan.write_text(original.read_text(encoding="utf-8"), encoding="utf-8")
        state = self.root / "runtime.sqlite"
        business = self.root / "business.sqlite"
        args = [sys.executable, "-m", "lightning_azent", command, str(plan),
                "--state", str(state), "--data", str(business),
                "--synthetic", *extra]
        run = subprocess.run(args, cwd=self.root, env=self.env,
                             text=True, capture_output=True, timeout=12)
        self.assertEqual(run.returncode, 2, run.stderr)
        self.assertFalse(state.exists(), "request created the runtime database")
        self.assertFalse(business.exists(), "request created the business database")

    def test_invalid_run_id(self):
        self.reject_without_db("conditional-route.json", "run",
                               ["--run-id", "unsafe-id", "--approve-writes"])

    def test_missing_write_approval(self):
        self.reject_without_db("csv-filter-import.json", "run",
                               ["--run-id", "DeniedWrite", "--input-root", str(self.root)])

    def test_invalid_schedule_id(self):
        self.reject_without_db("interval-replay.json", "schedule",
                               ["--schedule-id", "unsafe-id", "--approve-writes"])

    def test_invalid_interval_count(self):
        self.reject_without_db("interval-replay.json", "schedule",
                               ["--schedule-id", "AllowedID", "--max-runs", "1001",
                                "--approve-writes"])

    def test_schedule_rejects_non_interval_trigger(self):
        self.reject_without_db("conditional-route.json", "schedule",
                               ["--schedule-id", "AllowedID", "--approve-writes"])


if __name__ == "__main__":
    unittest.main()
