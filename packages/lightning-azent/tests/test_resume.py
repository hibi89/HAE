"""Executed-only acceptance tests for safe manual run recovery, API and CLI."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]
FIXTURES = REPO_ROOT / "docs" / "lightning-azent" / "fixtures"
sys.path.insert(0, str(PACKAGE_ROOT))

from lightning_azent import LAExecutor, NATIVE_VERSION
from lightning_azent.engine import ApprovalRequired, Engine, InjectedStop, PlanError
from lightning_azent.runlog import RunLogError


class ResumeAcceptanceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.state = self.root / "runs.sqlite"
        self.business = self.root / "business.sqlite"
        self.executor = LAExecutor(self.state, self.business, self.root)
        self.env = dict(os.environ, PYTHONPATH=str(PACKAGE_ROOT))

    def fixture(self, name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))

    def cli(self, command, path, run_id, *, approve=False):
        args = [sys.executable, "-m", "lightning_azent", command, str(path),
                "--state", str(self.state), "--data", str(self.business),
                "--input-root", str(self.root), "--run-id", run_id, "--synthetic"]
        if approve:
            args.append("--approve-writes")
        return subprocess.run(args, cwd=self.root, env=self.env,
                              capture_output=True, text=True, timeout=12)

    def test_missing_resume_does_not_create_either_database(self):
        plan = self.fixture("conditional-route.json")
        with self.assertRaises(RunLogError):
            self.executor.resume(plan, "MissingRun")
        candidate = self.root / "plan.json"
        candidate.write_text(json.dumps(plan), encoding="utf-8")
        outcome = self.cli("resume", candidate, "MissingRun")
        self.assertEqual(outcome.returncode, 2, outcome.stderr)
        self.assertFalse(self.state.exists())
        self.assertFalse(self.business.exists())

    def test_completed_native_cli_run_can_resume_without_duplicate(self):
        plan = self.fixture("conditional-route.json")
        plan["version"] = NATIVE_VERSION
        path = self.root / "native.json"
        path.write_text(json.dumps(plan), encoding="utf-8")
        first = self.cli("run", path, "Repeated")
        resumed = self.cli("resume", path, "Repeated")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(json.loads(first.stdout), {"route": "accepted"})
        self.assertEqual(json.loads(resumed.stdout), json.loads(first.stdout))
        with sqlite3.connect(self.state) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0], 1)
        self.assertEqual(self.executor.status("Repeated")["status"], "completed")

    def test_changed_plan_cannot_resume_existing_run(self):
        original = self.fixture("conditional-route.json")
        self.assertEqual(self.executor.execute(original, "Pinned"), {"route": "accepted"})
        altered = self.fixture("conditional-route.json")
        altered["steps"][0]["value"]["amount"] = 1
        with self.assertRaises(PlanError):
            self.executor.resume(altered, "Pinned")
        self.assertEqual(self.executor.status("Pinned")["status"], "completed")
        self.assertEqual(self.executor.resume(original, "Pinned"), {"route": "accepted"})

    def test_interrupted_business_write_resumes_without_duplicate(self):
        plan = self.fixture("interval-replay.json")
        plan.pop("trigger")
        with self.assertRaises(InjectedStop):
            Engine(self.state, self.business, input_root=self.root).execute(
                plan, "CrashAfterBusiness", approve_writes=True,
                inject_stop_after_business=True)
        native = dict(plan, version=NATIVE_VERSION)
        with self.assertRaises(ApprovalRequired):
            # Reject a missing approval without mutating the failed ledger.
            self.executor.resume(native, "CrashAfterBusiness")
        self.assertEqual(self.executor.status("CrashAfterBusiness")["status"], "failed")
        result = self.executor.resume(native, "CrashAfterBusiness", approve_writes=True)
        self.assertEqual(result, {"source": "synthetic"})
        with sqlite3.connect(self.business) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM records").fetchone()[0], 1)
        self.assertEqual(self.executor.status("CrashAfterBusiness")["status"], "completed")


    def test_changed_plan_does_not_recreate_missing_business_database(self):
        original = self.fixture("conditional-route.json")
        self.assertEqual(self.executor.execute(original, "PinnedNoWrite"), {"route": "accepted"})
        self.assertTrue(self.business.exists())
        self.business.unlink()  # Disposable synthetic database in the test temp directory.
        changed = self.fixture("conditional-route.json")
        changed["steps"][0]["value"]["amount"] = 0
        with self.assertRaises(PlanError):
            self.executor.resume(changed, "PinnedNoWrite")
        self.assertFalse(self.business.exists())
        self.assertEqual(self.executor.status("PinnedNoWrite")["status"], "completed")


if __name__ == "__main__":
    unittest.main()
