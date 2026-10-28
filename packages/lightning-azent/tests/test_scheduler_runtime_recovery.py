"""Real process-death recovery after a scheduled SQLite business write."""
from __future__ import annotations

from contextlib import closing
import hashlib
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

from lightning_azent import LAExecutor


CRASH_HARNESS = r'''
import os
import sys
import json
from pathlib import Path
from lightning_azent import LAExecutor
from lightning_azent.engine import Engine

original = Engine._evaluate_step
def crash_after_commit(self, step, results, outcomes, run_id,
                       inject_stop_after_business, *, sqlite_timeout=5):
    value = original(self, step, results, outcomes, run_id,
                     inject_stop_after_business, sqlite_timeout=sqlite_timeout)
    if step["op"] == "sqlite_put":
        os._exit(73)
    return value

Engine._evaluate_step = crash_after_commit
plan = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
executor = LAExecutor(sys.argv[2], sys.argv[3], sys.argv[4])
list(executor.schedule(plan, "CrashSchedule", max_runs=1, approve_writes=True,
                       clock=lambda: 0.0, sleeper=lambda _: None))
os._exit(74)
'''


class ScheduledRuntimeRecoveryTests(unittest.TestCase):
    def test_process_death_after_commit_replays_same_tick_without_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state, business = root / "state.sqlite", root / "business.sqlite"
            plan_path = FIXTURES / "interval-replay.json"
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            harness = root / "crash_after_commit.py"
            harness.write_text(CRASH_HARNESS, encoding="utf-8")
            env = os.environ.copy()
            env["PYTHONPATH"] = os.pathsep.join(
                [str(PACKAGE_ROOT), env.get("PYTHONPATH", "")]
            ).rstrip(os.pathsep)

            crashed = subprocess.run(
                [sys.executable, str(harness), str(plan_path), str(state),
                 str(business), str(root)],
                cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(crashed.returncode, 73, crashed.stderr)

            run_id = "S" + hashlib.sha256(b"CrashSchedule:0").hexdigest()[:31]
            executor = LAExecutor(state, business, root)
            interrupted = executor.status(run_id)
            self.assertEqual(interrupted["status"], "running")
            self.assertEqual(interrupted["step_outcomes"]["running"], 1)
            with closing(sqlite3.connect(business)) as con:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM records").fetchone()[0], 1)

            recovered = list(LAExecutor(state, business, root).schedule(
                plan, "CrashSchedule", max_runs=1, approve_writes=True,
                clock=lambda: 0.0, sleeper=lambda _: None,
            ))

            self.assertEqual(len(recovered), 1)
            self.assertEqual(recovered[0]["tick"], 0)
            self.assertTrue(recovered[0]["advanced"])
            self.assertEqual(recovered[0]["run_id"], run_id)
            self.assertEqual(LAExecutor(state, business).status(run_id)["status"], "completed")
            with closing(sqlite3.connect(business)) as con:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM records").fetchone()[0], 1)
            audit = LAExecutor(state, business).audit(run_id)
            event_types = [event["event_type"] for event in audit["events"]]
            self.assertIn("run_started", event_types)
            self.assertIn("run_resumed", event_types)
            self.assertEqual(event_types[-1], "run_completed")
            self.assertEqual(len(audit["approval_receipts"]), 2)


if __name__ == "__main__":
    unittest.main()
