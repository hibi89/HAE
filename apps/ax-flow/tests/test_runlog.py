import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from axflow.runlog import RunLogError, inspect_run


class RunLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / "runtime.db"
        with closing(sqlite3.connect(self.db)) as c:
            c.execute("CREATE TABLE runs (run_id TEXT PRIMARY KEY, plan_hash TEXT, status TEXT, output_json TEXT)")
            c.execute("CREATE TABLE steps (run_id TEXT, step_id TEXT, output_json TEXT)")
            c.execute("INSERT INTO runs VALUES ('Run1', 'abc123', 'running', NULL)")
            c.execute("INSERT INTO steps VALUES ('Run1', 'One', 'secret payload')")
            c.commit()

    def test_readonly_status_and_redaction(self):
        before = self.db.read_bytes()
        got = inspect_run(self.db, "Run1")
        self.assertEqual(got, {"run_id": "Run1", "status": "running", "steps_recorded": 1,
                              "step_outcomes": {"completed": 1, "failed": 0, "running": 0, "skipped": 0},
                              "plan_sha256": "abc123", "error_type": None, "result_summary": None})
        self.assertNotIn("secret", str(got))
        self.assertEqual(before, self.db.read_bytes())

    def test_result_summary_exposes_only_bounded_receipt_counts(self):
        with closing(sqlite3.connect(self.db)) as c:
            c.execute(
                "UPDATE runs SET status='completed', output_json=? WHERE run_id='Run1'",
                ('{"imported_rows":3,"duplicate_count":1,"duplicate_row_numbers":[2],'
                 '"source_sha256":"secret-hash","payload":{"customer":"secret"}}',),
            )
            c.commit()
        before = self.db.read_bytes()
        got = inspect_run(self.db, "Run1")
        self.assertEqual(got["result_summary"], {"kind": "saved", "count": 3, "duplicate_count": 1})
        self.assertNotIn("secret", str(got))
        self.assertNotIn("source_sha256", str(got))
        self.assertEqual(before, self.db.read_bytes())

    def test_unbounded_or_invalid_receipts_are_not_exposed(self):
        with closing(sqlite3.connect(self.db)) as c:
            c.execute("UPDATE runs SET output_json=? WHERE run_id='Run1'", ('{"imported_rows":true}',))
            c.commit()
        self.assertIsNone(inspect_run(self.db, "Run1")["result_summary"])

    def test_missing_and_untrusted_inputs_fail(self):
        for run_id in ("missing", "Bad' OR 1=1 --", "../etc/passwd", ""):
            with self.assertRaises(RunLogError):
                inspect_run(self.db, run_id)
        with self.assertRaises(RunLogError):
            inspect_run(self.db.parent / "absent.db", "Run1")
        self.assertFalse((self.db.parent / "absent.db").exists())


if __name__ == "__main__":
    unittest.main()

