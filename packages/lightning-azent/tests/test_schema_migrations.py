"""Durable, fail-closed SQLite ledger initialization and schema upgrades."""
from __future__ import annotations

import hashlib
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from lightning_azent.engine import Engine, LEDGER_SCHEMA_VERSION, PlanError


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LedgerSchemaMigrationTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.state = self.root / "state.sqlite"
        self.business = self.root / "business.sqlite"

    def test_legacy_ledgers_upgrade_and_preserve_rows(self):
        with closing(sqlite3.connect(self.state)) as con:
            con.execute("CREATE TABLE runs (run_id TEXT PRIMARY KEY, plan_hash TEXT NOT NULL, status TEXT NOT NULL, output_json TEXT)")
            con.execute("CREATE TABLE steps (run_id TEXT NOT NULL, step_id TEXT NOT NULL, output_json TEXT NOT NULL, PRIMARY KEY(run_id,step_id))")
            con.execute("INSERT INTO runs VALUES ('LegacyRun', 'digest', 'completed', '{}')")
            con.execute("INSERT INTO steps VALUES ('LegacyRun', 'Step1', '{}')")
            con.commit()
        with closing(sqlite3.connect(self.business)) as con:
            con.execute("CREATE TABLE records (run_id TEXT NOT NULL, step_id TEXT NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY(run_id,step_id))")
            con.execute("CREATE TABLE csv_records (run_id TEXT, import_step_id TEXT, row_number INTEGER, payload_json TEXT)")
            con.execute("INSERT INTO records VALUES ('LegacyRun', 'Step1', '{}')")
            con.commit()

        Engine(self.state, self.business)

        with closing(sqlite3.connect(self.state)) as con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], LEDGER_SCHEMA_VERSION)
            self.assertEqual(con.execute("SELECT status FROM runs WHERE run_id='LegacyRun'").fetchone()[0], "completed")
            self.assertEqual(con.execute("SELECT COUNT(*) FROM steps WHERE run_id='LegacyRun'").fetchone()[0], 1)
            self.assertTrue({"status", "error_type", "attempt_count"} <= {
                row[1] for row in con.execute("PRAGMA table_info(steps)")
            })
        with closing(sqlite3.connect(self.business)) as con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], LEDGER_SCHEMA_VERSION)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM records").fetchone()[0], 1)
            self.assertIn("source_sha256", {row[1] for row in con.execute("PRAGMA table_info(csv_records)")})

    def test_future_schema_version_is_rejected_without_mutation(self):
        with closing(sqlite3.connect(self.state)) as con:
            con.execute("CREATE TABLE runs (run_id TEXT, plan_hash TEXT, status TEXT)")
            con.execute("CREATE TABLE steps (run_id TEXT, step_id TEXT, output_json TEXT)")
            con.execute(f"PRAGMA user_version={LEDGER_SCHEMA_VERSION + 1}")
            con.commit()
        before = digest(self.state)

        with self.assertRaisesRegex(PlanError, "newer"):
            Engine(self.state, self.business)

        self.assertEqual(digest(self.state), before)
        self.assertFalse(self.business.exists())

    def test_v1_ledgers_migrate_to_v2_audit_schema(self):
        with closing(sqlite3.connect(self.state)) as con:
            con.execute("CREATE TABLE runs (run_id TEXT PRIMARY KEY, plan_hash TEXT NOT NULL, status TEXT NOT NULL, output_json TEXT, error_type TEXT)")
            con.execute("CREATE TABLE steps (run_id TEXT NOT NULL, step_id TEXT NOT NULL, output_json TEXT NOT NULL, status TEXT NOT NULL, error_type TEXT, attempt_count INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(run_id,step_id))")
            con.execute("PRAGMA user_version=1")
            con.commit()
        with closing(sqlite3.connect(self.business)) as con:
            con.execute("CREATE TABLE records (run_id TEXT NOT NULL, step_id TEXT NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY(run_id,step_id))")
            con.execute("CREATE TABLE csv_records (run_id TEXT NOT NULL, import_step_id TEXT NOT NULL, source_sha256 TEXT NOT NULL, row_number INTEGER NOT NULL CHECK(row_number > 0), payload_json TEXT NOT NULL, PRIMARY KEY(run_id,import_step_id,row_number))")
            con.execute("PRAGMA user_version=1")
            con.commit()

        Engine(self.state, self.business)

        with closing(sqlite3.connect(self.state)) as con:
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], LEDGER_SCHEMA_VERSION)
            tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue({"audit_events", "approval_receipts"} <= tables)

    def test_v2_missing_audit_table_fails_without_changing_either_ledger(self):
        Engine(self.state, self.business)
        with closing(sqlite3.connect(self.state)) as con:
            con.execute("DROP TABLE audit_events")
            con.commit()
        state_before, business_before = digest(self.state), digest(self.business)

        with self.assertRaisesRegex(PlanError, "audit schema is incomplete"):
            Engine(self.state, self.business)

        self.assertEqual(digest(self.state), state_before)
        self.assertEqual(digest(self.business), business_before)

    def test_incompatible_business_ledger_is_rejected_before_state_creation(self):
        with closing(sqlite3.connect(self.business)) as con:
            con.execute("CREATE TABLE records (unrelated TEXT)")
            con.commit()
        before = digest(self.business)

        with self.assertRaisesRegex(PlanError, "incompatible"):
            Engine(self.state, self.business)

        self.assertFalse(self.state.exists())
        self.assertEqual(digest(self.business), before)

    def test_corrupt_business_ledger_is_rejected_before_state_creation(self):
        self.business.write_bytes(b"not a sqlite database")
        before = digest(self.business)

        with self.assertRaisesRegex(PlanError, "corrupt or unreadable"):
            Engine(self.state, self.business)

        self.assertFalse(self.state.exists())
        self.assertEqual(digest(self.business), before)


if __name__ == "__main__":
    unittest.main()
