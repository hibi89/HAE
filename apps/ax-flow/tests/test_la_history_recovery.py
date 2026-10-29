import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[1]
LA_PACKAGE = REPO_ROOT / "packages" / "lightning-azent"
sys.path.insert(0, str(PACKAGE_ROOT))
sys.path.insert(0, str(LA_PACKAGE))

from axflow.la_adapter import execute as execute_through_hae
from axflow.planner import plan_request
from axflow.runlog import list_recent_runs
from lightning_azent import LAExecutor


class LAHistoryRecoveryTests(unittest.TestCase):
    def test_replay_recovers_history_stamp_after_exit_between_la_commit_and_hae_stamp(self):
        with tempfile.TemporaryDirectory(prefix="hae-la-history-recovery-") as folder:
            root = Path(folder)
            inputs = root / "input"
            inputs.mkdir()
            (inputs / "contacts.csv").write_bytes(b"id,name\n31,Alice\n32,Bob\n")
            state, business = root / "state.db", root / "business.db"
            run_id = "Guiabcdef123456"
            plan = plan_request("Import this CSV into local SQLite", "contacts.csv")
            payload = json.dumps({
                "plan": plan,
                "input_root": str(inputs),
                "state_path": str(state),
                "business_path": str(business),
                "run_id": run_id,
            })
            child = r'''
import json, os, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from lightning_azent import LAExecutor
data = json.loads(sys.argv[2])
executor = LAExecutor(Path(data["state_path"]), Path(data["business_path"]),
                      input_root=Path(data["input_root"]))
executor.execute(data["plan"], data["run_id"], approve_writes=True)
os._exit(73)  # Simulate HAE exiting after LA commits but before HAE records history metadata.
'''
            crashed = subprocess.run(
                [sys.executable, "-c", child, str(LA_PACKAGE), payload],
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(crashed.returncode, 73, crashed.stderr)
            self.assertEqual(list_recent_runs(state), [], "unrecorded LA start time must not be fabricated")
            with closing(sqlite3.connect(business)) as con:
                self.assertEqual(con.execute(
                    "SELECT COUNT(*) FROM csv_records WHERE run_id=?", (run_id,)
                ).fetchone()[0], 2)

            replay = execute_through_hae(
                plan, run_id, state_path=state, business_path=business,
                input_root=inputs, approve_writes=True,
            )
            self.assertEqual(replay["status"]["status"], "completed")
            self.assertIn("run_replayed", [item["event_type"] for item in replay["audit"]["events"]])
            recent = list_recent_runs(state)
            self.assertEqual([item["run_id"] for item in recent], [run_id])
            self.assertEqual(recent[0]["status"], "completed")
            with closing(sqlite3.connect(business)) as con:
                self.assertEqual(con.execute(
                    "SELECT COUNT(*) FROM csv_records WHERE run_id=?", (run_id,)
                ).fetchone()[0], 2, "same-run recovery must not duplicate business rows")
            with closing(sqlite3.connect(state)) as con:
                self.assertEqual(con.execute(
                    "SELECT COUNT(*) FROM approval_receipts WHERE run_id=?", (run_id,)
                ).fetchone()[0], 1, "replay must not duplicate approval evidence")


if __name__ == "__main__":
    unittest.main()
