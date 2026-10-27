import json
import hashlib
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path

from axflow.engine import (ApprovalRequired, Engine, InjectedStop, PlanError, StepRetryExhausted,
                           StepTimeout, validate)
from axflow.runlog import inspect_run
from axflow.state_backup import StateBackupError, backup_runtime_state, restore_runtime_state
from axflow.planner import plan_request, requires_write_approval
from axflow.templates import build_template


class TestEngine(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.engine = Engine(self.root / "state.db", self.root / "business.db")
        self.plan = {"version": "axflow.ir.v0", "steps": [
            {"id": "source", "op": "literal", "value": {"name": "fixture", "count": 2}},
            {"id": "field", "op": "field", "from": "source", "field": "count"},
            {"id": "save", "op": "sqlite_put", "from": "source"},
            {"id": "read", "op": "sqlite_get", "from": "save"},
        ]}

    def test_three_end_to_end_workflows_and_duplicate_replay(self):
        for suffix in ("a", "b", "c"):
            self.assertEqual(self.engine.execute(self.plan, "Run"+suffix, approve_writes=True), {"count": 2, "name": "fixture"})
        self.assertEqual(self.engine.execute(self.plan, "Runa", approve_writes=True), {"count": 2, "name": "fixture"})
        with closing(sqlite3.connect(self.root / "business.db")) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM records").fetchone()[0], 3)

    def test_write_requires_explicit_approval(self):
        with self.assertRaises(ApprovalRequired):
            self.engine.execute(self.plan, "Block")
        with closing(sqlite3.connect(self.root / "business.db")) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM records").fetchone()[0], 0)

    def test_runtime_ledger_backup_and_restore_verify_fresh_paths_without_overwrite(self):
        self.engine.execute(self.plan, "BackupRun", approve_writes=True)
        source = self.root / "state.db"
        workspace_temp = Path(__file__).resolve().parents[3] / ".verification-temp"
        workspace_temp.mkdir(exist_ok=True)
        destinations = tempfile.TemporaryDirectory(prefix="p42-engine-backup-", dir=workspace_temp)
        self.addCleanup(destinations.cleanup)
        output_root = Path(destinations.name)
        backup = output_root / "state-backup.sqlite"
        restored = output_root / "state-restored.sqlite"
        source_before = (hashlib.sha256(source.read_bytes()).hexdigest(), source.stat().st_size,
                         source.stat().st_mtime_ns)

        result = backup_runtime_state(source, backup)
        self.assertEqual(result["sqlite_integrity"], "ok")
        self.assertTrue(result["source_unchanged"])
        self.assertEqual(inspect_run(backup, "BackupRun")["status"], "completed")
        restored_result = restore_runtime_state(backup, restored)
        self.assertEqual(restored_result["sqlite_integrity"], "ok")
        self.assertEqual(inspect_run(restored, "BackupRun")["step_outcomes"]["completed"], 4)
        self.assertEqual(
            (hashlib.sha256(source.read_bytes()).hexdigest(), source.stat().st_size,
             source.stat().st_mtime_ns), source_before,
        )

        protected = output_root / "protected.sqlite"
        protected.write_bytes(b"DO-NOT-OVERWRITE")
        protected_before = protected.read_bytes()
        with self.assertRaises(StateBackupError):
            backup_runtime_state(source, protected)
        with self.assertRaises(StateBackupError):
            restore_runtime_state(backup, protected)
        self.assertEqual(protected.read_bytes(), protected_before)

        wrong = self.root / "not-a-ledger.sqlite"
        with closing(sqlite3.connect(wrong)) as con:
            con.execute("CREATE TABLE unrelated(value TEXT)")
        rejected = output_root / "must-not-exist.sqlite"
        with self.assertRaises(StateBackupError):
            backup_runtime_state(wrong, rejected)
        self.assertFalse(rejected.exists())

        corrupt = self.root / "corrupt-backup.sqlite"
        corrupt.write_bytes(b"not-a-sqlite-ledger")
        corrupt_restore = output_root / "corrupt-restore.sqlite"
        with self.assertRaises(StateBackupError):
            restore_runtime_state(corrupt, corrupt_restore)
        self.assertFalse(corrupt_restore.exists())
        self.assertEqual(list(self.root.glob(".axflow-state-*.part")), [])

    def test_cli_runtime_backup_restore_requires_synthetic_and_preserves_state(self):
        self.engine.execute(self.plan, "CliBackupRun", approve_writes=True)
        source = self.root / "state.db"
        workspace_temp = Path(__file__).resolve().parents[3] / ".verification-temp"
        workspace_temp.mkdir(exist_ok=True)
        destinations = tempfile.TemporaryDirectory(prefix="p42-cli-backup-", dir=workspace_temp)
        self.addCleanup(destinations.cleanup)
        output_root = Path(destinations.name)
        backup = output_root / "cli-backup.sqlite"
        restored = output_root / "cli-restored.sqlite"
        source_before = (hashlib.sha256(source.read_bytes()).hexdigest(), source.stat().st_size,
                         source.stat().st_mtime_ns)
        command = [sys.executable, "-m", "axflow"]

        missing_guard = subprocess.run(
            [*command, "backup", "--state", str(source), "--output", str(backup)],
            capture_output=True, text=True,
        )
        self.assertEqual(missing_guard.returncode, 2)
        self.assertFalse(backup.exists())
        created = subprocess.run(
            [*command, "backup", "--state", str(source), "--output", str(backup), "--synthetic"],
            capture_output=True, text=True,
        )
        self.assertEqual(created.returncode, 0, created.stderr)
        self.assertNotIn(str(self.root), created.stdout)
        restored_run = subprocess.run(
            [*command, "restore", "--backup", str(backup), "--state", str(restored), "--synthetic"],
            capture_output=True, text=True,
        )
        self.assertEqual(restored_run.returncode, 0, restored_run.stderr)
        status = subprocess.run(
            [*command, "status", "--state", str(restored), "--run-id", "CliBackupRun", "--synthetic"],
            capture_output=True, text=True,
        )
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertEqual(json.loads(status.stdout)["status"], "completed")
        self.assertEqual(
            (hashlib.sha256(source.read_bytes()).hexdigest(), source.stat().st_size,
             source.stat().st_mtime_ns), source_before,
        )
        protected = output_root / "existing-target.sqlite"
        protected.write_bytes(b"existing-target-marker")
        refused = subprocess.run(
            [*command, "restore", "--backup", str(backup), "--state", str(protected), "--synthetic"],
            capture_output=True, text=True,
        )
        self.assertEqual(refused.returncode, 2)
        self.assertEqual(protected.read_bytes(), b"existing-target-marker")

    def test_map_conditions_guards_and_if_else_are_durable(self):
        def plan_for(age):
            return {"version": "axflow.ir.v0", "steps": [
                {"id": "source", "op": "literal", "value": {"name": "  ALICE ", "age": str(age)}},
                {"id": "mapped", "op": "map", "from": "source", "fields": {
                    "name": {"field": "name", "transform": "trim"},
                    "normalized_name": {"field": "name", "transform": "lower"},
                    "age": {"field": "age", "transform": "number"},
                }},
                {"id": "adult", "op": "condition", "from": "mapped", "field": "age",
                 "operator": "gte", "value": 18},
                {"id": "adult_store", "op": "sqlite_put", "from": "mapped",
                 "when": {"condition": "adult", "equals": True}},
                {"id": "minor_store", "op": "sqlite_put", "from": "source",
                 "when": {"condition": "adult", "equals": False}},
                {"id": "route", "op": "branch", "condition": "adult",
                 "then": "adult_store", "else": "minor_store"},
            ]}

        adult_output = self.engine.execute(plan_for(21), "AdultRun", approve_writes=True)
        minor_output = self.engine.execute(plan_for(17), "MinorRun", approve_writes=True)
        self.assertEqual(adult_output, {"stored_by": "adult_store"})
        self.assertEqual(minor_output, {"stored_by": "minor_store"})
        for run_id, store_step, expected in (
                ("AdultRun", "adult_store", {"age": 21, "name": "ALICE", "normalized_name": "  alice "}),
                ("MinorRun", "minor_store", {"age": "17", "name": "  ALICE "})):
            with closing(sqlite3.connect(self.root / "business.db")) as con:
                payload = con.execute(
                    "SELECT payload_json FROM records WHERE run_id=? AND step_id=?", (run_id, store_step)
                ).fetchone()[0]
            self.assertEqual(json.loads(payload), expected)
            status = inspect_run(self.root / "state.db", run_id)
            self.assertEqual(status["step_outcomes"], {"completed": 5, "failed": 0, "running": 0, "skipped": 1})

    def test_contains_operator_and_safe_transform_validation(self):
        contains = {"version": "axflow.ir.v0", "steps": [
            {"id": "source", "op": "literal", "value": {"tags": ["approved", "local"]}},
            {"id": "has_tag", "op": "condition", "from": "source", "field": "tags",
             "operator": "contains", "value": "approved"},
        ]}
        self.assertIs(self.engine.execute(contains, "ContainsRun"), True)
        invalid_transform = {"version": "axflow.ir.v0", "steps": [
            {"id": "source", "op": "literal", "value": {"name": "x"}},
            {"id": "mapped", "op": "map", "from": "source", "fields": {
                "name": {"field": "name", "transform": "eval"}}},
        ]}
        invalid_operator = {"version": "axflow.ir.v0", "steps": [
            {"id": "source", "op": "literal", "value": {"x": 1}},
            {"id": "check", "op": "condition", "from": "source", "field": "x",
             "operator": "exec", "value": 1},
        ]}
        invalid_branch = {"version": "axflow.ir.v0", "steps": [
            {"id": "source", "op": "literal", "value": {}},
            {"id": "check", "op": "literal", "value": True},
            {"id": "route", "op": "branch", "condition": "check", "then": "source", "else": "source"},
        ]}
        for bad in (invalid_transform, invalid_operator, invalid_branch):
            with self.assertRaises(PlanError):
                validate(bad)

    def test_sqlite_retry_cap_and_timeout_are_bounded_and_resume_succeeds(self):
        def plan_with_budget(timeout_ms):
            return {"version": "axflow.ir.v0", "steps": [
                {"id": "source", "op": "literal", "value": {"value": "fixture"}},
                {"id": "save", "op": "sqlite_put", "from": "source",
                 "max_attempts": 3, "timeout_ms": timeout_ms},
                {"id": "read", "op": "sqlite_get", "from": "save",
                 "max_attempts": 2, "timeout_ms": timeout_ms},
            ]}

        retry_plan, timeout_plan = plan_with_budget(1000), plan_with_budget(1)
        validate(retry_plan)
        validate(timeout_plan)
        blocker = sqlite3.connect(self.root / "business.db", timeout=1)
        blocker.execute("BEGIN EXCLUSIVE")
        started = time.monotonic()
        try:
            with self.assertRaises(StepRetryExhausted):
                self.engine.execute(retry_plan, "RetryCapRun", approve_writes=True)
            self.assertLess(time.monotonic() - started, 2)
            status = inspect_run(self.root / "state.db", "RetryCapRun")
            self.assertEqual(status["status"], "failed")
            self.assertEqual(status["error_type"], "StepRetryExhausted")
            with closing(sqlite3.connect(self.root / "state.db")) as state:
                step = state.execute(
                    "SELECT status,attempt_count,error_type FROM steps WHERE run_id='RetryCapRun' AND step_id='save'"
                ).fetchone()
            self.assertEqual(step, ("failed", 3, "StepRetryExhausted"))
            with self.assertRaises(StepTimeout):
                self.engine.execute(timeout_plan, "TimeoutRun", approve_writes=True)
            timeout_status = inspect_run(self.root / "state.db", "TimeoutRun")
            self.assertEqual(timeout_status["error_type"], "StepTimeout")
        finally:
            blocker.rollback()
            blocker.close()

        self.assertEqual(self.engine.execute(retry_plan, "RetryCapRun", approve_writes=True), {"value": "fixture"})
        status = inspect_run(self.root / "state.db", "RetryCapRun")
        self.assertEqual(status["status"], "completed")
        with closing(sqlite3.connect(self.root / "business.db")) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM records WHERE run_id='RetryCapRun'").fetchone()[0], 1)

    def test_retry_and_timeout_limits_are_strict(self):
        base = {"version": "axflow.ir.v0", "steps": [
            {"id": "source", "op": "literal", "value": {}},
            {"id": "save", "op": "sqlite_put", "from": "source"},
        ]}
        for patch in ({"max_attempts": 0}, {"max_attempts": 4}, {"max_attempts": True},
                      {"timeout_ms": 0}, {"timeout_ms": 5001}, {"timeout_ms": False}):
            bad = json.loads(json.dumps(base))
            bad["steps"][1].update(patch)
            with self.assertRaises(PlanError):
                validate(bad)
        pure_with_retry = {"version": "axflow.ir.v0", "steps": [
            {"id": "source", "op": "literal", "value": {}},
            {"id": "mapped", "op": "map", "from": "source", "max_attempts": 2,
             "fields": {"x": {"field": "x"}}},
        ]}
        with self.assertRaises(PlanError):
            validate(pure_with_retry)

    def test_csv_import_is_bounded_local_and_resumes_without_payload_duplication(self):
        input_root = self.root / "csv-input"
        input_root.mkdir()
        csv_path = input_root / "rows.csv"
        original = b"id,name\r\n001,Alice\r\n002,Bob\r\n"
        csv_path.write_bytes(original)
        plan = {"version": "axflow.ir.v0", "steps": [
            {"id": "input", "op": "csv_read", "path": "rows.csv"},
            {"id": "imported", "op": "sqlite_import_csv", "from": "input",
             "max_attempts": 3, "timeout_ms": 1000},
        ]}
        engine = Engine(self.root / "csv-state.db", self.root / "csv-business.db", input_root=input_root)
        with self.assertRaises(InjectedStop):
            engine.execute(plan, "CsvReplay", approve_writes=True, inject_stop_after_business=True)
        with closing(sqlite3.connect(self.root / "csv-state.db")) as state:
            receipt = state.execute(
                "SELECT output_json,status FROM steps WHERE run_id='CsvReplay' AND step_id='input'"
            ).fetchone()
        self.assertEqual(receipt[1], "completed")
        self.assertNotIn("Alice", receipt[0])
        with closing(sqlite3.connect(self.root / "csv-business.db")) as business:
            stored = business.execute(
                "SELECT row_number,payload_json FROM csv_records WHERE run_id='CsvReplay' ORDER BY row_number"
            ).fetchall()
        self.assertEqual(stored, [(1, '{"id":"001","name":"Alice"}'),
                                  (2, '{"id":"002","name":"Bob"}')])

        csv_path.write_bytes(b"id,name\r\n003,Changed\r\n")
        with self.assertRaises(PlanError):
            engine.execute(plan, "CsvReplay", approve_writes=True)
        self.assertEqual(inspect_run(self.root / "csv-state.db", "CsvReplay")["status"], "failed")
        csv_path.write_bytes(original)
        result = engine.execute(plan, "CsvReplay", approve_writes=True)
        self.assertEqual(result, {
            "imported_rows": 2, "duplicate_count": 0, "duplicate_row_numbers": [],
            "source_sha256": hashlib.sha256(original).hexdigest(),
        })
        self.assertEqual(inspect_run(self.root / "csv-state.db", "CsvReplay")["status"], "completed")
        with closing(sqlite3.connect(self.root / "csv-business.db")) as business:
            self.assertEqual(business.execute(
                "SELECT COUNT(*) FROM csv_records WHERE run_id='CsvReplay'"
            ).fetchone()[0], 2)
        metadata = engine.execute({"version": "axflow.ir.v0", "steps": [
            {"id": "input", "op": "csv_read", "path": "rows.csv"},
        ]}, "CsvMetadata")
        self.assertEqual(metadata["row_count"], 2)
        self.assertNotIn("rows", metadata)
        with closing(sqlite3.connect(self.root / "csv-state.db")) as state:
            output_json = state.execute(
                "SELECT output_json FROM runs WHERE run_id='CsvMetadata'"
            ).fetchone()[0]
        self.assertNotIn("Alice", output_json)

    def test_csv_input_limits_and_path_allowlist_fail_before_business_writes(self):
        input_root = self.root / "invalid-csv"
        input_root.mkdir()
        fixtures = {
            "duplicate.csv": b"id,ID\n1,2\n",
            "ragged.csv": b"id,name\n1,Alice,extra\n",
            "malformed.csv": b'id,name\n1,"unfinished\n',
            "invalid-utf8.csv": b"\xff\xfe\xfd",
            "oversized.csv": b"id\n" + b"x" * (262144 + 1),
            "too-many.csv": ("id\n" + "".join(f"{i}\n" for i in range(1001))).encode("utf-8"),
            "too-many-columns.csv": (",".join(f"c{i}" for i in range(65)) + "\n").encode("utf-8"),
            "long-cell.csv": ("id\n" + "x" * 4097 + "\n").encode("utf-8"),
        }
        for name, content in fixtures.items():
            (input_root / name).write_bytes(content)
        engine = Engine(self.root / "invalid-state.db", self.root / "invalid-business.db", input_root=input_root)
        for index, name in enumerate([*fixtures, "missing.csv"], start=1):
            plan = {"version": "axflow.ir.v0", "steps": [
                {"id": "input", "op": "csv_read", "path": name},
                {"id": "imported", "op": "sqlite_import_csv", "from": "input"},
            ]}
            with self.subTest(name=name), self.assertRaises(PlanError):
                engine.execute(plan, f"BadCsv{index}", approve_writes=True)
        for bad_path in ("../escape.csv", "C:/escape.csv", "/absolute.csv", "dir\\rows.csv", "rows.txt", "\x00bad.csv"):
            with self.assertRaises(PlanError):
                validate({"version": "axflow.ir.v0", "steps": [
                    {"id": "input", "op": "csv_read", "path": bad_path},
                ]})
        with self.assertRaises(PlanError):
            validate({"version": "axflow.ir.v0", "steps": [
                {"id": "input", "op": "csv_read", "path": "duplicate.csv"},
                {"id": "saved", "op": "sqlite_put", "from": "input"},
            ]})
        good_plan = {"version": "axflow.ir.v0", "steps": [
            {"id": "input", "op": "csv_read", "path": "duplicate.csv"},
            {"id": "imported", "op": "sqlite_import_csv", "from": "input"},
        ]}
        with self.assertRaises(ApprovalRequired):
            engine.execute(good_plan, "NoApproval")
        with self.assertRaises(PlanError):
            Engine(self.root / "no-root-state.db", self.root / "no-root-data.db").execute(
                good_plan, "NoRoot", approve_writes=True
            )
        with closing(sqlite3.connect(self.root / "invalid-business.db")) as business:
            self.assertEqual(business.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0], 0)

    def test_cli_csv_to_sqlite_vertical_path(self):
        input_root = self.root / "cli-csv"
        input_root.mkdir()
        (input_root / "contacts.csv").write_text("id,name\n1,Alice\n", encoding="utf-8")
        plan_path = self.root / "csv-plan.json"
        plan_path.write_text(json.dumps({"version": "axflow.ir.v0", "steps": [
            {"id": "input", "op": "csv_read", "path": "contacts.csv"},
            {"id": "imported", "op": "sqlite_import_csv", "from": "input"},
        ]}), encoding="utf-8")
        result = subprocess.run([
            sys.executable, "-m", "axflow", "run", str(plan_path),
            "--state", str(self.root / "cli-csv-state.db"),
            "--data", str(self.root / "cli-csv-business.db"),
            "--input-root", str(input_root), "--run-id", "CliCsvRun",
            "--synthetic", "--approve-writes",
        ], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["result"]["imported_rows"], 1)
        with closing(sqlite3.connect(self.root / "cli-csv-business.db")) as business:
            self.assertEqual(business.execute(
                "SELECT payload_json FROM csv_records WHERE run_id='CliCsvRun' AND row_number=1"
            ).fetchone()[0], '{"id":"1","name":"Alice"}')

    def test_csv_to_sqlite_template_generates_valid_ir_and_runs_from_cli(self):
        input_root = self.root / "template-input"
        input_root.mkdir()
        (input_root / "fixtures/contacts.csv").parent.mkdir()
        (input_root / "fixtures/contacts.csv").write_text("id,name\n7,Synthetic\n", encoding="utf-8")

        direct = build_template("csv_to_sqlite", csv_path="fixtures/contacts.csv")
        self.assertEqual(direct, {"version": "axflow.ir.v0", "steps": [
            {"id": "input", "op": "csv_read", "path": "fixtures/contacts.csv"},
            {"id": "imported", "op": "sqlite_import_csv", "from": "input"},
        ]})
        validate(direct)
        for name, params in (("unknown", {"csv_path": "contacts.csv"}),
                             ("csv_to_sqlite", {}),
                             ("csv_to_sqlite", {"csv_path": "../escape.csv"}),
                             ("csv_to_sqlite", {"csv_path": "contacts.csv", "destination": "remote"})):
            with self.subTest(name=name, params=params), self.assertRaises(PlanError):
                build_template(name, **params)

        generated = subprocess.run([
            sys.executable, "-m", "axflow", "template", "--name", "csv_to_sqlite",
            "--csv", "fixtures/contacts.csv", "--synthetic",
        ], capture_output=True, text=True)
        self.assertEqual(generated.returncode, 0, generated.stderr)
        plan = json.loads(generated.stdout)
        validate(plan)
        plan_path = self.root / "generated-template.json"
        plan_path.write_text(generated.stdout, encoding="utf-8")

        checked = subprocess.run([
            sys.executable, "-m", "axflow", "validate", str(plan_path), "--synthetic",
        ], capture_output=True, text=True)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        executed = subprocess.run([
            sys.executable, "-m", "axflow", "run", str(plan_path),
            "--state", str(self.root / "template-state.db"),
            "--data", str(self.root / "template-business.db"),
            "--input-root", str(input_root), "--run-id", "TemplateRun",
            "--synthetic", "--approve-writes",
        ], capture_output=True, text=True)
        self.assertEqual(executed.returncode, 0, executed.stderr)
        self.assertEqual(json.loads(executed.stdout)["result"]["imported_rows"], 1)
        with closing(sqlite3.connect(self.root / "template-business.db")) as business:
            self.assertEqual(business.execute(
                "SELECT payload_json FROM csv_records WHERE run_id='TemplateRun' AND row_number=1"
            ).fetchone()[0], '{"id":"7","name":"Synthetic"}')

    def test_csv_normalization_reports_duplicates_preserves_rows_and_replays_safely(self):
        input_root = self.root / "normalized-input"
        input_root.mkdir()
        csv_path = input_root / "contacts.csv"
        original = (
            "id,email,name\n"
            "1,EXAMPLE-SECRET-MARKER@EXAMPLE.COM,Alice  \n"
            "1,example-secret-marker@example.com, Alice\n"
            "2,other@example.com,Bob\n"
        ).encode("utf-8")
        csv_path.write_bytes(original)
        plan = {"version": "axflow.ir.v0", "steps": [
            {"id": "input", "op": "csv_read", "path": "contacts.csv"},
            {"id": "normalized", "op": "csv_normalize", "from": "input", "transforms": {
                "email": "lower", "name": "trim",
            }},
            {"id": "imported", "op": "sqlite_import_csv", "from": "normalized"},
        ]}
        validate(plan)
        engine = Engine(self.root / "normal-state.db", self.root / "normal-business.db", input_root)
        with self.assertRaises(InjectedStop):
            engine.execute(plan, "NormalizedRun", approve_writes=True, inject_stop_after_business=True)
        result = Engine(self.root / "normal-state.db", self.root / "normal-business.db", input_root).execute(
            plan, "NormalizedRun", approve_writes=True
        )
        self.assertEqual(result["imported_rows"], 3)
        self.assertEqual(result["duplicate_count"], 1)
        self.assertEqual(result["duplicate_row_numbers"], [2])
        self.assertEqual(csv_path.read_bytes(), original)

        with closing(sqlite3.connect(self.root / "normal-business.db")) as business:
            rows = business.execute(
                "SELECT row_number,payload_json FROM csv_records WHERE run_id=? ORDER BY row_number",
                ("NormalizedRun",),
            ).fetchall()
            self.assertEqual([row[0] for row in rows], [1, 2, 3])
            self.assertEqual(json.loads(rows[0][1]), {
                "email": "example-secret-marker@example.com", "id": "1", "name": "Alice",
            })
            self.assertEqual(rows[0][1], rows[1][1])
            self.assertEqual(business.execute(
                "SELECT COUNT(*) FROM csv_records WHERE run_id=?", ("NormalizedRun",)
            ).fetchone()[0], 3)
        self.assertNotIn("EXAMPLE-SECRET-MARKER", (self.root / "normal-state.db").read_bytes().decode("latin1"))
        status = inspect_run(self.root / "normal-state.db", "NormalizedRun")
        self.assertEqual(status["status"], "completed")
        self.assertIsNone(status["error_type"])

    def test_csv_normalization_failure_happens_before_business_write(self):
        input_root = self.root / "invalid-normal-input"
        input_root.mkdir()
        csv_path = input_root / "amounts.csv"
        plan = {"version": "axflow.ir.v0", "steps": [
            {"id": "input", "op": "csv_read", "path": "amounts.csv"},
            {"id": "normalized", "op": "csv_normalize", "from": "input", "transforms": {"amount": "number"}},
            {"id": "imported", "op": "sqlite_import_csv", "from": "normalized"},
        ]}
        invalid_values = (
            "not-a-number", "", "   ", "NaN", "Infinity", "-inf", "1e9999", "1e-9999",
            "$12.50", "1_000", "9007199254740993", "0.10000000000000001",
        )
        engine = Engine(self.root / "invalid-normal-state.db", self.root / "invalid-normal-business.db", input_root)
        for index, value in enumerate(invalid_values):
            with self.subTest(value=value):
                original = f'amount\n"{value}"\n'.encode("utf-8")
                csv_path.write_bytes(original)
                run_id = f"InvalidNormalize{index}"
                with self.assertRaises(PlanError):
                    engine.execute(plan, run_id, approve_writes=True)
                self.assertEqual(csv_path.read_bytes(), original)
                status = inspect_run(self.root / "invalid-normal-state.db", run_id)
                self.assertEqual(status["status"], "failed")
                self.assertEqual(status["step_outcomes"]["failed"], 1)
        with closing(sqlite3.connect(self.root / "invalid-normal-business.db")) as business:
            self.assertEqual(business.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0], 0)

    def test_number_transform_boundary_matrix(self):
        for raw, expected in (
            ("42", 42), ("-0", 0), ("3.75", 3.75), (" 8.5 ", 8.5),
            ("1.25e2", 125), ("1e-7", 1e-7),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(Engine._transform(raw, "number"), expected)
        for raw in (
            "", "   ", "NaN", "Infinity", "-inf", "1e9999", "1e-9999", "$12.50",
            "1_000", "9007199254740993", "0.10000000000000001",
        ):
            with self.subTest(raw=raw), self.assertRaises(PlanError):
                Engine._transform(raw, "number")

    def test_csv_normalize_filter_import_retains_original_row_numbers(self):
        input_root = self.root / "filtered-normal-input"
        input_root.mkdir()
        (input_root / "contacts.csv").write_text(
            "id,name,active\n1, Alice ,yes\n1,Alice,yes\n2,Bob,no\n", encoding="utf-8"
        )
        plan = {"version": "axflow.ir.v0", "steps": [
            {"id": "input", "op": "csv_read", "path": "contacts.csv"},
            {"id": "normalized", "op": "csv_normalize", "from": "input", "transforms": {"name": "trim"}},
            {"id": "filtered", "op": "csv_filter", "from": "normalized", "field": "active",
             "operator": "eq", "value": "yes"},
            {"id": "imported", "op": "sqlite_import_csv", "from": "filtered"},
        ]}
        engine = Engine(self.root / "filtered-normal-state.db", self.root / "filtered-normal-business.db", input_root)
        result = engine.execute(plan, "FilteredNormalize", approve_writes=True)
        self.assertEqual(result["imported_rows"], 2)
        self.assertEqual(result["duplicate_count"], 1)
        self.assertEqual(result["duplicate_row_numbers"], [2])
        with closing(sqlite3.connect(self.root / "filtered-normal-business.db")) as business:
            rows = business.execute(
                "SELECT row_number,payload_json FROM csv_records WHERE run_id=? ORDER BY row_number",
                ("FilteredNormalize",),
            ).fetchall()
        self.assertEqual([row[0] for row in rows], [1, 2])
        self.assertEqual(json.loads(rows[1][1])["name"], "Alice")

    def test_template_cli_keeps_synthetic_guard_and_rejects_unknown_names(self):
        without_guard = subprocess.run([
            sys.executable, "-m", "axflow", "template", "--name", "csv_to_sqlite",
            "--csv", "contacts.csv",
        ], capture_output=True, text=True)
        self.assertEqual(without_guard.returncode, 2)
        unknown = subprocess.run([
            sys.executable, "-m", "axflow", "template", "--name", "arbitrary",
            "--csv", "contacts.csv", "--synthetic",
        ], capture_output=True, text=True)
        self.assertEqual(unknown.returncode, 2)
        self.assertIn("unsupported template", unknown.stderr)
        unused_option = subprocess.run([
            sys.executable, "-m", "axflow", "template", "ignored-plan.json",
            "--name", "csv_to_sqlite", "--csv", "contacts.csv", "--input-root", str(self.root),
            "--synthetic",
        ], capture_output=True, text=True)
        self.assertEqual(unused_option.returncode, 2)
        self.assertIn("template accepts only", unused_option.stderr)

    def test_serve_cli_requires_explicit_local_paths_and_valid_port(self):
        base = [sys.executable, "-m", "axflow", "serve", "--synthetic"]
        missing = subprocess.run(base, capture_output=True, text=True)
        self.assertEqual(missing.returncode, 2)
        self.assertIn("serve requires", missing.stderr)
        invalid_port = subprocess.run(
            base + ["--input-root", str(self.root), "--state", str(self.root / "state.db"),
                    "--data", str(self.root / "business.db"), "--port", "0"],
            capture_output=True, text=True,
        )
        self.assertEqual(invalid_port.returncode, 2)
        self.assertIn("serve requires", invalid_port.stderr)

    def test_step_failure_is_recorded_and_legacy_receipts_migrate(self):
        broken = {"version": "axflow.ir.v0", "steps": [
            {"id": "source", "op": "literal", "value": {"name": "ok"}},
            {"id": "mapped", "op": "map", "from": "source", "fields": {
                "missing": {"field": "absent", "transform": "trim"}}},
        ]}
        with self.assertRaises(PlanError):
            self.engine.execute(broken, "BrokenRun")
        status = inspect_run(self.root / "state.db", "BrokenRun")
        self.assertEqual(status["step_outcomes"], {"completed": 1, "failed": 1, "running": 0, "skipped": 0})

        state, business = self.root / "legacy.db", self.root / "legacy-business.db"
        with closing(sqlite3.connect(state)) as con:
            con.execute("CREATE TABLE runs (run_id TEXT PRIMARY KEY,plan_hash TEXT NOT NULL,status TEXT NOT NULL,output_json TEXT,error_type TEXT)")
            con.execute("CREATE TABLE steps (run_id TEXT NOT NULL,step_id TEXT NOT NULL,output_json TEXT NOT NULL,PRIMARY KEY(run_id,step_id))")
            con.execute("INSERT INTO runs VALUES ('OldRun','legacy-hash','running',NULL,NULL)")
            con.execute("INSERT INTO steps VALUES ('OldRun','old_step','1')")
            con.commit()
        Engine(state, business)
        migrated = inspect_run(state, "OldRun")
        self.assertEqual(migrated["step_outcomes"], {"completed": 1, "failed": 0, "running": 0, "skipped": 0})
        with closing(sqlite3.connect(state)) as con:
            self.assertEqual(con.execute(
                "SELECT status,attempt_count FROM steps WHERE run_id='OldRun' AND step_id='old_step'"
            ).fetchone(), ("completed", 1))

    def test_restart_after_committed_write_does_not_duplicate(self):
        with self.assertRaises(InjectedStop):
            self.engine.execute(self.plan, "Crash", approve_writes=True, inject_stop_after_business=True)
        failed = inspect_run(self.root / "state.db", "Crash")
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["error_type"], "InjectedStop")
        self.assertEqual(failed["steps_recorded"], 3)
        self.assertEqual(failed["step_outcomes"], {"completed": 2, "failed": 1, "running": 0, "skipped": 0})
        restarted = Engine(self.root / "state.db", self.root / "business.db")
        self.assertEqual(restarted.execute(self.plan, "Crash", approve_writes=True)["name"], "fixture")
        completed = inspect_run(self.root / "state.db", "Crash")
        self.assertEqual(completed["status"], "completed")
        self.assertIsNone(completed["error_type"])
        with closing(sqlite3.connect(self.root / "business.db")) as c:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM records WHERE run_id='Crash'").fetchone()[0], 1)

    def test_concurrent_independent_runs_and_same_run_replay_are_idempotent(self):
        barrier = threading.Barrier(2)

        def execute(run_id):
            barrier.wait(timeout=5)
            return self.engine.execute(self.plan, run_id, approve_writes=True)

        with ThreadPoolExecutor(max_workers=2) as pool:
            outputs = list(pool.map(execute, ("ParallelA", "ParallelB")))
        self.assertEqual(outputs, [{"count": 2, "name": "fixture"}] * 2)

        duplicate_barrier = threading.Barrier(2)

        def duplicate():
            duplicate_barrier.wait(timeout=5)
            return self.engine.execute(self.plan, "SharedRun", approve_writes=True)

        with ThreadPoolExecutor(max_workers=2) as pool:
            duplicate_outputs = list(pool.map(lambda _: duplicate(), range(2)))
        self.assertEqual(duplicate_outputs, [{"count": 2, "name": "fixture"}] * 2)
        with closing(sqlite3.connect(self.root / "business.db")) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM records").fetchone()[0], 3)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM records WHERE run_id='SharedRun'").fetchone()[0], 1)
        with closing(sqlite3.connect(self.root / "state.db")) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM runs WHERE run_id='SharedRun'").fetchone()[0], 1)

    def test_concurrent_same_run_id_with_different_plan_is_rejected(self):
        changed = json.loads(json.dumps(self.plan))
        changed["steps"][0]["value"]["count"] = 9
        barrier = threading.Barrier(2)

        def attempt(plan):
            barrier.wait(timeout=5)
            try:
                return ("completed", self.engine.execute(plan, "Collision", approve_writes=True))
            except PlanError as exc:
                return ("rejected", str(exc))

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, (self.plan, changed)))
        self.assertCountEqual([item[0] for item in outcomes], ["completed", "rejected"])
        self.assertIn("same run id", next(item[1] for item in outcomes if item[0] == "rejected"))
        with closing(sqlite3.connect(self.root / "business.db")) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM records WHERE run_id='Collision'").fetchone()[0], 1)

    def test_rejects_invalid_specs_and_plan_reuse(self):
        for bad in ({"version": "n8n", "steps": []}, {"version": "axflow.ir.v0", "steps": [{"id": "ok", "op": "shell", "cmd": "rm -rf /"}]},
                    {"version": "axflow.ir.v0", "steps": [{"id": "one", "op": "field", "from": "two", "field": "x"}]}):
            with self.assertRaises(PlanError):
                validate(bad)
        self.engine.execute(self.plan, "Stable", approve_writes=True)
        changed = json.loads(json.dumps(self.plan));changed["steps"][0]["value"]["count"] = 3
        with self.assertRaises(PlanError):
            self.engine.execute(changed, "Stable", approve_writes=True)

    def test_cli_status_and_resume(self):
        path = self.root / "plan.json"
        path.write_text(json.dumps(self.plan), encoding="utf-8")
        base = [sys.executable, "-m", "axflow"]
        run_args = [str(path), "--state", str(self.root / "state.db"),
                    "--data", str(self.root / "business.db"), "--run-id", "ResumeCase",
                    "--synthetic", "--approve-writes"]
        first = subprocess.run(base + ["run"] + run_args, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        status = subprocess.run(base + ["status", "--state", str(self.root / "state.db"),
                                         "--run-id", "ResumeCase", "--synthetic"],
                                capture_output=True, text=True)
        self.assertEqual(status.returncode, 0, status.stderr)
        report = json.loads(status.stdout)
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["steps_recorded"], 4)
        self.assertNotIn("fixture", str(report))
        restarted = subprocess.run(base + ["resume"] + run_args, capture_output=True, text=True)
        self.assertEqual(restarted.returncode, 0, restarted.stderr)
        with closing(sqlite3.connect(self.root / "business.db")) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM records WHERE run_id='ResumeCase'").fetchone()[0], 1)

    def test_cli_validate_requires_synthetic_flag(self):
        path = self.root / "plan.json"
        path.write_text(json.dumps(self.plan), encoding="utf-8")
        fail = subprocess.run([sys.executable, "-m", "axflow", "validate", str(path)], capture_output=True, text=True)
        self.assertEqual(fail.returncode, 2)
        ok = subprocess.run([sys.executable, "-m", "axflow", "validate", str(path), "--synthetic"], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)

    def test_cli_rejects_malformed_or_ambiguous_json_and_missing_paths(self):
        base = [sys.executable, "-m", "axflow", "validate"]
        malformed = self.root / "malformed.json"
        malformed.write_text('{"version":"axflow.ir.v0","version":"axflow.ir.v0","steps":[]}', encoding="utf-8")
        rejected = subprocess.run(base + [str(malformed), "--synthetic"], capture_output=True, text=True)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("duplicate JSON key", rejected.stderr)
        missing = subprocess.run(base + [str(self.root / "missing.json"), "--synthetic"], capture_output=True, text=True)
        self.assertEqual(missing.returncode, 2)
        self.assertIn("AX FLOW stopped safely", missing.stderr)

    def test_csv_filter_import_is_numeric_bounded_idempotent_and_redacted(self):
        inputs = self.root / "inputs"
        inputs.mkdir()
        (inputs / "sales.csv").write_text(
            "amount,id\n125,A\n20,B\n125,C\n", encoding="utf-8"
        )
        plan = plan_request(
            "이 CSV에서 amount가 100 이상인 행만 로컬 SQLite에 저장해줘", "sales.csv"
        )
        self.assertTrue(requires_write_approval(plan))
        engine = Engine(self.root / "filter-state.db", self.root / "filter-business.db", input_root=inputs)
        first = engine.execute(plan, "FilteredRun", approve_writes=True)
        replay = engine.execute(plan, "FilteredRun", approve_writes=True)
        self.assertEqual(first, replay)
        self.assertEqual(first["imported_rows"], 2)
        with self.assertRaises(InjectedStop):
            engine.execute(plan, "FilteredRecovery", approve_writes=True, inject_stop_after_business=True)
        self.assertEqual(engine.execute(plan, "FilteredRecovery", approve_writes=True)["imported_rows"], 2)

        with closing(sqlite3.connect(self.root / "filter-business.db")) as con:
            rows = con.execute(
                "SELECT row_number,payload_json FROM csv_records WHERE run_id=? ORDER BY row_number",
                ("FilteredRun",),
            ).fetchall()
        self.assertEqual([row[0] for row in rows], [1, 3])
        self.assertEqual([json.loads(row[1])["id"] for row in rows], ["A", "C"])

        with closing(sqlite3.connect(self.root / "filter-state.db")) as con:
            receipt = con.execute(
                "SELECT output_json FROM steps WHERE run_id=? AND step_id='filtered'", ("FilteredRun",)
            ).fetchone()[0]
        self.assertEqual(json.loads(receipt)["matched_row_numbers"], [1, 3])
        self.assertNotIn('"125"', receipt)
        self.assertNotIn('"matches"', receipt)
        with closing(sqlite3.connect(self.root / "filter-business.db")) as con:
            self.assertEqual(
                con.execute(
                    "SELECT COUNT(*) FROM csv_records WHERE run_id='FilteredRecovery'"
                ).fetchone()[0],
                2,
            )

    def test_csv_lookup_is_read_only_and_persists_only_match_metadata(self):
        inputs = self.root / "lookup-input"
        inputs.mkdir()
        (inputs / "people.csv").write_text(
            "id,name\n11,PrivateMarker\n12,OtherFixture\n", encoding="utf-8"
        )
        plan = plan_request("이 CSV에서 id가 11인 행을 찾아줘", "people.csv")
        self.assertFalse(requires_write_approval(plan))
        business = self.root / "lookup-business.db"
        state = self.root / "lookup-state.db"
        result = Engine(state, business, input_root=inputs).execute(plan, "LookupRun")
        self.assertEqual(result["matched_count"], 1)
        self.assertEqual(result["matched_row_numbers"], [1])
        with closing(sqlite3.connect(business)) as con:
            self.assertEqual(con.execute("SELECT COUNT(*) FROM csv_records").fetchone()[0], 0)
        with closing(sqlite3.connect(state)) as con:
            stored = con.execute(
                "SELECT output_json FROM runs WHERE run_id='LookupRun'"
            ).fetchone()[0]
        self.assertNotIn("PrivateMarker", stored)
        self.assertIn('"matched_count":1', stored)

    def test_conditional_csv_import_writes_only_when_filter_matches(self):
        inputs = self.root / "conditional-input"
        inputs.mkdir()
        (inputs / "sales.csv").write_text(
            "amount,id\n125,A\n20,B\n125,C\n", encoding="utf-8"
        )
        engine = Engine(
            self.root / "conditional-state.db", self.root / "conditional-business.db", input_root=inputs
        )
        matching = plan_request(
            "이 CSV에서 amount가 100 이상일 때만 로컬 SQLite에 저장해줘", "sales.csv"
        )
        skipped = plan_request(
            "이 CSV에서 amount가 500 이상일 때만 로컬 SQLite에 저장해줘", "sales.csv"
        )
        self.assertEqual(engine.execute(matching, "ConditionalMatch", approve_writes=True)["imported_rows"], 2)
        self.assertEqual(engine.execute(skipped, "ConditionalEmpty", approve_writes=True)["imported_rows"], 0)
        with closing(sqlite3.connect(self.root / "conditional-business.db")) as con:
            self.assertEqual(
                con.execute("SELECT COUNT(*) FROM csv_records WHERE run_id='ConditionalMatch'").fetchone()[0], 2
            )
            self.assertEqual(
                con.execute("SELECT COUNT(*) FROM csv_records WHERE run_id='ConditionalEmpty'").fetchone()[0], 0
            )
        self.assertEqual(inspect_run(self.root / "conditional-state.db", "ConditionalEmpty")["status"], "completed")

    def test_csv_filter_rejects_unbounded_or_compound_requests(self):
        invalid = {"version": "axflow.ir.v0", "steps": [
            {"id": "input", "op": "csv_read", "path": "sales.csv"},
            {"id": "filter", "op": "csv_filter", "from": "input", "field": "amount",
             "operator": "contains", "value": 100, "transform": "number"},
        ]}
        with self.assertRaises(PlanError):
            validate(invalid)
        with self.assertRaises(PlanError):
            plan_request(
                "Find rows in this CSV where amount >= 100 and id = A", "sales.csv"
            )

    def test_hard_process_exit_after_csv_commit_resumes_without_duplicate(self):
        inputs = self.root / "crash-input"
        inputs.mkdir()
        (inputs / "contacts.csv").write_text("id,name\n1,First\n2,Second\n", encoding="utf-8")
        plan = build_template("csv_to_sqlite", csv_path="contacts.csv")
        plan_file = self.root / "crash-plan.json"
        plan_file.write_text(json.dumps(plan), encoding="utf-8")
        state = self.root / "crash-state.db"
        business = self.root / "crash-business.db"
        helper = self.root / "crash_after_import.py"
        helper.write_text(
            "import json, os, sys\n"
            "from pathlib import Path\n"
            "sys.path.insert(0, str(Path.cwd()))\n"
            "from axflow.engine import Engine\n"
            "class CrashEngine(Engine):\n"
            " def _evaluate_step(self, step, results, outcomes, run_id, inject_stop_after_business, **kwargs):\n"
            "  value = super()._evaluate_step(step, results, outcomes, run_id, False, **kwargs)\n"
            "  if step['op'] == 'sqlite_import_csv': os._exit(73)\n"
            "  return value\n"
            "state,business,root,run_id,plan_path=sys.argv[1:]\n"
            "plan=json.loads(Path(plan_path).read_text(encoding='utf-8'))\n"
            "CrashEngine(state,business,input_root=Path(root)).execute(plan,run_id,approve_writes=True)\n",
            encoding="utf-8",
        )
        cwd = Path(__file__).resolve().parents[1]
        crashed = subprocess.run(
            [sys.executable, str(helper), str(state), str(business), str(inputs), "HardCrashRun", str(plan_file)],
            cwd=cwd, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(crashed.returncode, 73, crashed.stderr)
        self.assertEqual(inspect_run(state, "HardCrashRun")["status"], "running")
        with closing(sqlite3.connect(business)) as con:
            self.assertEqual(
                con.execute("SELECT COUNT(*) FROM csv_records WHERE run_id='HardCrashRun'").fetchone()[0], 2
            )

        resumed = Engine(state, business, input_root=inputs).execute(
            plan, "HardCrashRun", approve_writes=True
        )
        self.assertEqual(resumed["imported_rows"], 2)
        self.assertEqual(inspect_run(state, "HardCrashRun")["status"], "completed")
        with closing(sqlite3.connect(business)) as con:
            rows = con.execute(
                "SELECT row_number,payload_json FROM csv_records WHERE run_id='HardCrashRun' ORDER BY row_number"
            ).fetchall()
        self.assertEqual([row[0] for row in rows], [1, 2])
        self.assertEqual([json.loads(row[1])["id"] for row in rows], ["1", "2"])

    def test_cross_process_same_run_replay_is_idempotent(self):
        # This test deliberately creates same-run overlap, so opt into the bounded
        # busy/locked retry budget instead of relying on the one-attempt default.
        concurrent_plan = json.loads(json.dumps(self.plan))
        for step in concurrent_plan["steps"]:
            if step["op"] in {"sqlite_put", "sqlite_get"}:
                step.update(max_attempts=3, timeout_ms=5000)
        plan_file = self.root / "process-plan.json"
        plan_file.write_text(json.dumps(concurrent_plan), encoding="utf-8")
        command = [
            sys.executable, "-m", "axflow", "run", str(plan_file),
            "--state", str(self.root / "state.db"), "--data", str(self.root / "business.db"),
            "--run-id", "SharedProcessRun", "--synthetic", "--approve-writes",
        ]
        blocker = sqlite3.connect(self.root / "state.db", timeout=1, isolation_level=None)
        blocker.execute("BEGIN EXCLUSIVE")
        processes = []
        try:
            cwd = Path(__file__).resolve().parents[1]
            processes = [
                subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True),
                subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True),
            ]
            time.sleep(0.15)
        finally:
            blocker.rollback()
            blocker.close()

        completed = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 0, stderr)
            completed.append(json.loads(stdout))
        self.assertEqual([item["result"] for item in completed], [
            {"count": 2, "name": "fixture"}, {"count": 2, "name": "fixture"},
        ])
        with closing(sqlite3.connect(self.root / "business.db")) as con:
            self.assertEqual(
                con.execute(
                    "SELECT COUNT(*) FROM records WHERE run_id='SharedProcessRun' AND step_id='save'"
                ).fetchone()[0],
                1,
            )
        self.assertEqual(inspect_run(self.root / "state.db", "SharedProcessRun")["status"], "completed")

    def test_engine_rejects_path_like_run_ids_and_unsafe_database_paths(self):
        with self.assertRaises(PlanError):
            self.engine.execute(self.plan, "../escape", approve_writes=True)
        same = self.root / "same.db"
        with self.assertRaises(PlanError):
            Engine(same, same)
        missing_parent = self.root / "missing" / "state.db"
        with self.assertRaises(PlanError):
            Engine(missing_parent, self.root / "business.db")
        self.assertFalse(same.exists())
        self.assertFalse(missing_parent.parent.exists())


if __name__ == "__main__":
    unittest.main()
