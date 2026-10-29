import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path

from axflow.engine import Engine
from axflow.runlog import list_recent_runs
from axflow.web import _recent_runs_payload


class RecentRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "runtime.db"
        self.business = self.root / "business.db"
        with closing(sqlite3.connect(self.state)) as con:
            # Simulate a runtime ledger created before the timestamp migration.
            con.execute("CREATE TABLE runs (run_id TEXT PRIMARY KEY, plan_hash TEXT NOT NULL, status TEXT NOT NULL, output_json TEXT)")
            con.execute("CREATE TABLE steps (run_id TEXT, step_id TEXT, output_json TEXT)")
            con.execute("INSERT INTO runs VALUES ('Gui000000000000','legacy-hash','failed','{}')")
            con.execute("INSERT INTO steps VALUES ('Gui000000000000','old-step','secret row payload')")
            con.commit()
        self.engine = Engine(self.state, self.business)

    def test_run_creation_migrates_ledger_additively_and_records_utc_time(self):
        plan = {"version": "axflow.ir.v0", "steps": [
            {"id": "seed", "op": "literal", "value": {"marker": "SyntheticOnly"}},
            {"id": "save", "op": "sqlite_put", "from": "seed"},
        ]}
        self.engine.execute(plan, "Gui000000000001", approve_writes=True)
        with closing(sqlite3.connect(self.state)) as con:
            columns = {row[1] for row in con.execute("PRAGMA table_info(runs)")}
            stamp = con.execute("SELECT created_at FROM runs WHERE run_id='Gui000000000001'").fetchone()[0]
            legacy_stamp = con.execute("SELECT created_at FROM runs WHERE run_id='Gui000000000000'").fetchone()[0]
        self.assertIn("created_at", columns)
        self.assertIsNone(legacy_stamp, "migration must not invent historical creation times")
        self.assertTrue(stamp.endswith("Z"))
        self.assertIsNotNone(datetime.fromisoformat(stamp[:-1]))
        self.assertEqual([run["run_id"] for run in list_recent_runs(self.state)], ["Gui000000000001"])

    def test_recent_run_index_is_bounded_read_only_and_redacted(self):
        plan = {"version": "axflow.ir.v0", "steps": [
            {"id": "seed", "op": "literal", "value": {"marker": "SensitiveSyntheticMarker"}},
            {"id": "save", "op": "sqlite_put", "from": "seed"},
        ]}
        self.engine.execute(plan, "Gui000000000002", approve_writes=True)
        before = self.state.read_bytes()
        rows = list_recent_runs(self.state, limit=2)
        self.assertEqual([row["run_id"] for row in rows], ["Gui000000000002"])
        self.assertEqual(rows[0]["status"], "completed")
        self.assertEqual(rows[0]["step_outcomes"]["completed"], 2)
        self.assertEqual(set(rows[0]), {"run_id", "status", "created_at", "steps_recorded", "step_outcomes"})
        self.assertNotIn("SensitiveSyntheticMarker", json.dumps(rows))
        self.assertNotIn(str(self.root), json.dumps(rows))
        self.assertEqual(before, self.state.read_bytes(), "history reads must leave the runtime DB unchanged")
        legacy = next((run for run in list_recent_runs(self.state, limit=20)
                       if run["run_id"] == "Gui000000000000"), None)
        self.assertIsNone(legacy, "unknown historical timestamps must not be presented as recent")
        for limit in (0, 21, True, "10"):
            with self.assertRaises(ValueError):
                list_recent_runs(self.state, limit=limit)

    def test_read_only_http_payload_caps_and_validates_limit(self):
        status, payload = _recent_runs_payload(self.state, "limit=1")
        self.assertEqual(status, 200)
        self.assertEqual(payload["limit"], 1)
        self.assertEqual(payload["runs"], [], "legacy run without a verified timestamp must not be labeled recent")
        for query in ("limit=0", "limit=21", "limit=1&limit=2", "limit=x", "other=1"):
            code, response = _recent_runs_payload(self.state, query)
            self.assertEqual(code, 400, query)
            self.assertEqual(response, {"error": "limit must be an integer from 1 through 20"})

    def test_recent_list_returns_at_most_twenty_web_run_ids(self):
        with closing(sqlite3.connect(self.state)) as con:
            for index in range(1, 26):
                con.execute(
                    "INSERT INTO runs(run_id,plan_hash,status,output_json,error_type) VALUES (?,?,?,NULL,NULL)",
                    (f"Gui{index:012x}", "hash", "completed"),
                )
            con.commit()
        rows = list_recent_runs(self.state, limit=20)
        self.assertEqual(len(rows), 20)
        self.assertEqual(rows[0]["run_id"], "Gui000000000019")
        self.assertTrue(all(row["run_id"].startswith("Gui") for row in rows))

    def test_empty_history_does_not_create_a_runtime_database(self):
        absent = self.root / "not-created.db"
        self.assertEqual(list_recent_runs(absent), [])
        self.assertEqual(_recent_runs_payload(absent, ""), (200, {"runs": [], "limit": 10}))
        self.assertFalse(absent.exists())


if __name__ == "__main__":
    unittest.main()
