"""Real SQLite scheduled-tick recovery after a committed business write."""
from __future__ import annotations

from contextlib import closing
import json
import hashlib
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]
FIXTURES = REPO_ROOT / "docs" / "lightning-azent" / "fixtures"
sys.path.insert(0, str(PACKAGE_ROOT))

from lightning_azent import LAExecutor
from lightning_azent.engine import Engine, InjectedStop


class ScheduledRuntimeRecoveryTests(unittest.TestCase):
    def test_interrupted_due_tick_replays_same_run_and_preserves_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state, business = root / "state.sqlite", root / "business.sqlite"
            plan = json.loads((FIXTURES / "interval-replay.json").read_text(encoding="utf-8"))
            executor = LAExecutor(state, business, root)
            original_execute = Engine.execute

            def stop_after_business_write(engine, workflow, run_id, *, approve_writes=False,
                                          inject_stop_after_business=False, interval_tick=False):
                return original_execute(
                    engine, workflow, run_id, approve_writes=approve_writes,
                    inject_stop_after_business=True, interval_tick=interval_tick,
                )

            with patch.object(Engine, "execute", stop_after_business_write):
                with self.assertRaises(InjectedStop):
                    list(executor.schedule(
                        plan, "CrashSchedule", max_runs=1, approve_writes=True,
                        clock=lambda: 0.0, sleeper=lambda _: None,
                    ))

            run_id = "S" + hashlib.sha256(b"CrashSchedule:0").hexdigest()[:31]
            failed = executor.status(run_id)
            self.assertEqual(failed["status"], "failed")
            with closing(sqlite3.connect(business)) as con:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM records").fetchone()[0], 1)

            recovered = list(LAExecutor(state, business, root).schedule(
                plan, "CrashSchedule", max_runs=1, approve_writes=True,
                clock=lambda: 0.0, sleeper=lambda _: None,
            ))

            self.assertEqual(len(recovered), 1)
            self.assertEqual(recovered[0]["tick"], 0)
            self.assertTrue(recovered[0]["advanced"])
            self.assertEqual(recovered[0]["run_id"], failed["run_id"])
            self.assertEqual(LAExecutor(state, business).status(recovered[0]["run_id"])["status"], "completed")
            with closing(sqlite3.connect(business)) as con:
                self.assertEqual(con.execute("SELECT COUNT(*) FROM records").fetchone()[0], 1)
            audit = LAExecutor(state, business).audit(recovered[0]["run_id"])
            event_types = [event["event_type"] for event in audit["events"]]
            self.assertIn("run_failed", event_types)
            self.assertIn("run_resumed", event_types)
            self.assertEqual(event_types[-1], "run_completed")
            self.assertEqual(len(audit["approval_receipts"]), 2)


if __name__ == "__main__":
    unittest.main()
