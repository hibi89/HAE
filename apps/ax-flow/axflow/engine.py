"""Typed workflow subset and independent SQLite-backed execution (synthetic MVP)."""
from __future__ import annotations

import hashlib
import csv
import io
import json
import math
import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

VERSION = "axflow.ir.v0"
IDENTIFIER = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{0,31}$")
MAX_STEPS = 32
MAX_SPEC_BYTES = 65536
MAX_CSV_BYTES = 262144
MAX_CSV_ROWS = 1000
MAX_CSV_COLUMNS = 64
MAX_CSV_CELL_CHARS = 4096


class PlanError(ValueError):
    """Invalid workflow specification or unsupported operation."""


class ApprovalRequired(RuntimeError):
    """An explicit write approval is required."""


class InjectedStop(RuntimeError):
    """Synthetic fault injected after a business DB commit."""


class StepTimeout(TimeoutError):
    """A SQLite step exhausted its bounded lock-wait budget."""


class StepRetryExhausted(RuntimeError):
    """A SQLite step reached its configured transient-error attempt cap."""


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def validate(plan: object) -> dict:
    if (not isinstance(plan, dict) or set(plan) not in ({"version", "steps"}, {"version", "trigger", "steps"})
            or plan["version"] != VERSION):
        raise PlanError("expected versioned AX FLOW IR with version, optional trigger and steps")
    trigger = plan.get("trigger", {"type": "manual"})
    if not isinstance(trigger, dict) or not isinstance(trigger.get("type"), str):
        raise PlanError("trigger must be manual or interval")
    if trigger["type"] == "manual":
        if set(trigger) != {"type"}:
            raise PlanError("manual trigger accepts only its type")
    elif trigger["type"] == "interval":
        seconds = trigger.get("every_seconds")
        if (set(trigger) != {"type", "every_seconds"} or isinstance(seconds, bool) or
                not isinstance(seconds, int) or not 1 <= seconds <= 86400):
            raise PlanError("interval trigger requires every_seconds from 1 to 86400")
    else:
        raise PlanError("unsupported trigger type")
    steps = plan["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise PlanError("steps must be a list with 1–32 entries")
    seen = set()
    step_ops = {}
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get("id"), str) or not IDENTIFIER.fullmatch(step["id"]):
            raise PlanError("step id must be a safe identifier")
        ident, op = step["id"], step.get("op")
        if ident in seen:
            raise PlanError("duplicate step id")
        if not isinstance(op, str):
            raise PlanError(f"unknown operation or invalid fields for {ident}")
        fields = {
            "literal": {"id", "op", "value"},
            "field": {"id", "op", "from", "field"},
            "map": {"id", "op", "from", "fields"},
            "condition": {"id", "op", "from", "field", "operator", "value"},
            "branch": {"id", "op", "condition", "then", "else"},
            "csv_read": {"id", "op", "path"},
            "csv_filter": {"id", "op", "from", "field", "operator", "value"},
            "sqlite_put": {"id", "op", "from"},
            "sqlite_import_csv": {"id", "op", "from"},
            "sqlite_get": {"id", "op", "from"},
        }
        optional = {
            "field": {"when"},
            "map": {"when"},
            "sqlite_put": {"when", "max_attempts", "timeout_ms"},
            "sqlite_import_csv": {"when", "max_attempts", "timeout_ms"},
            "sqlite_get": {"when", "max_attempts", "timeout_ms"},
            "literal": {"when"},
            "csv_filter": {"transform"},
        }
        allowed = fields.get(op)
        if allowed is None or not allowed <= set(step) or set(step) - allowed - optional.get(op, set()):
            raise PlanError(f"unknown operation or invalid fields for {ident}")
        if op in {"field", "map", "condition", "csv_filter", "sqlite_put", "sqlite_import_csv", "sqlite_get"} and (
                not isinstance(step["from"], str) or step["from"] not in seen):
            raise PlanError("step source must reference an earlier step")
        if (op in {"field", "map", "condition", "sqlite_put", "sqlite_get"} and
                step_ops.get(step["from"]) == "csv_read"):
            raise PlanError("CSV rows may only flow into sqlite_import_csv")
        if op == "csv_read":
            source_path = step["path"]
            parts = source_path.split("/") if isinstance(source_path, str) else []
            relative = PurePosixPath(source_path) if isinstance(source_path, str) else None
            if (not isinstance(source_path, str) or not source_path or len(source_path) > 512 or
                    "\\" in source_path or ":" in source_path or relative.is_absolute() or
                    "\x00" in source_path or
                    any(part in {"", ".", ".."} for part in parts) or
                    relative.suffix.lower() != ".csv"):
                raise PlanError("csv_read path must be a relative .csv path under --input-root")
        if op == "field" and (not isinstance(step["field"], str) or not IDENTIFIER.fullmatch(step["field"])):
            raise PlanError("field name must be a safe identifier")
        if op == "map":
            mapping = step["fields"]
            if not isinstance(mapping, dict) or not 1 <= len(mapping) <= MAX_STEPS:
                raise PlanError("map fields must contain 1–32 output mappings")
            for target, spec in mapping.items():
                if not isinstance(target, str) or not IDENTIFIER.fullmatch(target):
                    raise PlanError("map output names must be safe identifiers")
                if (not isinstance(spec, dict) or set(spec) - {"field", "transform"} or
                        "field" not in spec or not isinstance(spec["field"], str) or
                        not IDENTIFIER.fullmatch(spec["field"])):
                    raise PlanError("each map field needs a safe source field and optional transform")
                transform = spec.get("transform", "identity")
                if not isinstance(transform, str) or transform not in {
                        "identity", "trim", "lower", "upper", "number", "string"}:
                    raise PlanError("unsupported map transform")
        if op == "condition":
            if not isinstance(step["field"], str) or not IDENTIFIER.fullmatch(step["field"]):
                raise PlanError("condition field must be a safe identifier")
            if not isinstance(step["operator"], str) or step["operator"] not in {"eq", "ne", "gt", "gte", "lt", "lte", "contains"}:
                raise PlanError("unsupported condition operator")
        if op == "csv_filter":
            if step_ops.get(step["from"]) != "csv_read":
                raise PlanError("csv_filter source must be a csv_read step")
            if not isinstance(step["field"], str) or not IDENTIFIER.fullmatch(step["field"]):
                raise PlanError("CSV filter field must be a safe identifier")
            operator = step["operator"]
            if not isinstance(operator, str) or operator not in {"eq", "ne", "gt", "gte", "lt", "lte", "contains"}:
                raise PlanError("unsupported CSV filter operator")
            value = step["value"]
            if isinstance(value, bool) or not isinstance(value, (int, float, str)):
                raise PlanError("CSV filter value must be a string or finite number")
            transform = step.get("transform", "identity")
            if not isinstance(transform, str) or transform not in {"identity", "trim", "lower", "upper", "number"}:
                raise PlanError("unsupported CSV filter transform")
            if transform == "number":
                if isinstance(value, str) or isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise PlanError("numeric CSV filter requires a numeric comparison value")
            elif not isinstance(value, str):
                raise PlanError("text CSV filter requires a string comparison value")
            if operator == "contains" and transform == "number":
                raise PlanError("contains cannot use a numeric CSV filter")
        if op == "condition" and step_ops.get(step["from"]) == "csv_filter" and step["field"] != "matched_count":
            raise PlanError("CSV filter conditions may inspect only matched_count")
        if op in {"field", "map", "sqlite_put", "sqlite_get"} and step_ops.get(step.get("from")) == "csv_filter":
            raise PlanError("CSV filter row data may not flow into generic value operations")
        if op == "branch":
            condition = step["condition"]
            then_step, else_step = step["then"], step["else"]
            if (not isinstance(condition, str) or condition not in seen or
                    step_ops.get(condition) != "condition"):
                raise PlanError("branch condition must reference an earlier condition step")
            if (not isinstance(then_step, str) or then_step not in seen or
                    not isinstance(else_step, str) or else_step not in seen):
                raise PlanError("branch outputs must reference earlier steps")
            if {step_ops.get(then_step), step_ops.get(else_step)} & {"csv_read", "csv_filter"}:
                raise PlanError("CSV row data may not be exposed as a branch output")
        if op in {"sqlite_put", "sqlite_import_csv", "sqlite_get"}:
            attempts = step.get("max_attempts", 1)
            timeout_ms = step.get("timeout_ms", 5000)
            if isinstance(attempts, bool) or not isinstance(attempts, int) or not 1 <= attempts <= 3:
                raise PlanError("max_attempts must be an integer from 1 to 3")
            if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or not 1 <= timeout_ms <= 5000:
                raise PlanError("timeout_ms must be an integer from 1 to 5000")
        if "when" in step:
            guard = step["when"]
            if (not isinstance(guard, dict) or set(guard) != {"condition", "equals"} or
                    not isinstance(guard["condition"], str) or guard["condition"] not in seen or
                    step_ops.get(guard["condition"]) != "condition" or
                    not isinstance(guard["equals"], bool)):
                raise PlanError("when must reference an earlier condition and a boolean equals value")
        if op == "sqlite_get" and step_ops.get(step["from"]) != "sqlite_put":
            raise PlanError("sqlite_get source must be a sqlite_put step")
        if op == "sqlite_import_csv" and step_ops.get(step["from"]) not in {"csv_read", "csv_filter"}:
            raise PlanError("sqlite_import_csv source must be a csv_read or csv_filter step")
        seen.add(ident)
        step_ops[ident] = op
    try:
        if len(canonical_json(plan).encode("utf-8")) > MAX_SPEC_BYTES:
            raise PlanError("workflow specification is too large")
    except (TypeError, ValueError, OverflowError) as exc:
        raise PlanError("workflow contains invalid JSON value") from exc
    return plan


class Engine:
    """Do not use on customer data: this early engine persists synthetic step outputs."""

    def __init__(self, state_path: Path, business_path: Path, input_root: Path | None = None):
        self.state_path = Path(state_path).expanduser().resolve()
        self.business_path = Path(business_path).expanduser().resolve()
        self.input_root = Path(input_root).expanduser().resolve() if input_root is not None else None
        if self.state_path == self.business_path:
            raise PlanError("runtime and business SQLite files must be distinct")
        if not self.state_path.parent.is_dir() or not self.business_path.parent.is_dir():
            raise PlanError("both database parent directories must already exist")
        if self.input_root is not None and not self.input_root.is_dir():
            raise PlanError("CSV input root must be an existing directory")
        with self._state() as con:
            con.execute("CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, plan_hash TEXT NOT NULL, status TEXT NOT NULL, output_json TEXT, error_type TEXT)")
            columns = {row[1] for row in con.execute("PRAGMA table_info(runs)")}
            if "error_type" not in columns:
                con.execute("ALTER TABLE runs ADD COLUMN error_type TEXT")
            con.execute("CREATE TABLE IF NOT EXISTS steps (run_id TEXT NOT NULL, step_id TEXT NOT NULL, output_json TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'completed', error_type TEXT, PRIMARY KEY(run_id,step_id))")
            step_columns = {row[1] for row in con.execute("PRAGMA table_info(steps)")}
            if "status" not in step_columns:
                con.execute("ALTER TABLE steps ADD COLUMN status TEXT NOT NULL DEFAULT 'completed'")
            if "error_type" not in step_columns:
                con.execute("ALTER TABLE steps ADD COLUMN error_type TEXT")
            if "attempt_count" not in step_columns:
                con.execute("ALTER TABLE steps ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 1")
        with self._business() as con:
            con.execute("CREATE TABLE IF NOT EXISTS records (run_id TEXT NOT NULL, step_id TEXT NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY(run_id,step_id))")
            con.execute(
                "CREATE TABLE IF NOT EXISTS csv_records (run_id TEXT NOT NULL, import_step_id TEXT NOT NULL, "
                "source_sha256 TEXT NOT NULL, row_number INTEGER NOT NULL CHECK(row_number > 0), "
                "payload_json TEXT NOT NULL, PRIMARY KEY(run_id,import_step_id,row_number))"
            )

    @contextmanager
    def _state(self):
        con = sqlite3.connect(self.state_path, timeout=5)
        try:
            with con:
                yield con
        finally:
            con.close()

    @contextmanager
    def _business(self, timeout: float = 5):
        con = sqlite3.connect(self.business_path, timeout=timeout)
        try:
            with con:
                yield con
        finally:
            con.close()

    def execute(self, plan: object, run_id: str, *, approve_writes: bool = False,
                inject_stop_after_business: bool = False, interval_tick: bool = False) -> object:
        validate(plan)
        trigger = plan.get("trigger", {"type": "manual"})
        if trigger["type"] == "interval" and not interval_tick:
            raise PlanError("interval-triggered workflows must be started with the schedule command")
        if interval_tick and trigger["type"] != "interval":
            raise PlanError("schedule command requires an interval trigger")
        if not isinstance(run_id, str) or not IDENTIFIER.fullmatch(run_id):
            raise PlanError("run_id must be a safe identifier")
        if any(s["op"] == "csv_read" for s in plan["steps"]) and self.input_root is None:
            raise PlanError("CSV workflows require an explicit --input-root")
        if any(s["op"] in {"sqlite_put", "sqlite_import_csv"} for s in plan["steps"]) and not approve_writes:
            raise ApprovalRequired("explicit --approve-writes required for local SQLite writes")
        digest = hashlib.sha256(canonical_json(plan).encode("utf-8")).hexdigest()
        with self._state() as con:
            # Reserve the claim transaction before reading so simultaneous processes
            # cannot both create a fresh run row for the same run_id.
            con.execute("BEGIN IMMEDIATE")
            existing = con.execute("SELECT plan_hash,status,output_json FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if existing is None:
                con.execute(
                    "INSERT INTO runs (run_id,plan_hash,status,output_json,error_type) VALUES (?,?,?,NULL,NULL)",
                    (run_id, digest, "running"),
                )
            elif existing[0] != digest:
                raise PlanError("same run id cannot be reused with a different plan")
            elif existing[1] == "completed":
                return json.loads(existing[2])
            else:
                con.execute("UPDATE runs SET status='running',error_type=NULL WHERE run_id=?", (run_id,))
        try:
            return self._execute_steps(plan, run_id, inject_stop_after_business)
        except Exception as exc:
            with self._state() as con:
                con.execute(
                    "UPDATE runs SET status='failed',error_type=? WHERE run_id=? AND status='running'",
                    (type(exc).__name__, run_id),
                )
            raise

    def _execute_steps(self, plan: dict, run_id: str, inject_stop_after_business: bool) -> object:
        results = {}
        outcomes = {}
        for step in plan["steps"]:
            sid, op = step["id"], step["op"]
            with self._state() as con:
                saved = con.execute(
                    "SELECT output_json,status FROM steps WHERE run_id=? AND step_id=?", (run_id, sid)
                ).fetchone()
            if saved is not None and saved[1] in {"completed", "skipped"}:
                persisted = json.loads(saved[0])
                if op == "csv_read" and saved[1] == "completed":
                    try:
                        current = self._read_csv(step["path"])
                        if current["source_sha256"] != persisted.get("source_sha256"):
                            raise PlanError("CSV content changed since this run was checkpointed")
                        results[sid] = current
                    except Exception as exc:
                        with self._state() as con:
                            con.execute(
                                "UPDATE steps SET status='failed',error_type=? WHERE run_id=? AND step_id=?",
                                (type(exc).__name__, run_id, sid),
                            )
                        raise
                elif op == "csv_filter" and saved[1] == "completed":
                    # Filter rows stay in memory; deterministically rebuild them from
                    # the hash-checked csv_read result when resuming a run.
                    current = self._evaluate_step(step, results, outcomes, run_id, False)
                    if self._step_receipt(op, current) != persisted:
                        raise PlanError("CSV filter result changed since this run was checkpointed")
                    results[sid] = current
                else:
                    results[sid] = persisted
                outcomes[sid] = saved[1]
                continue

            with self._state() as con:
                if saved is None:
                    con.execute(
                        "INSERT OR IGNORE INTO steps(run_id,step_id,output_json,status,error_type,attempt_count) VALUES (?,?,?,'running',NULL,0)",
                        (run_id, sid, "null"),
                    )
                else:
                    con.execute(
                        "UPDATE steps SET status='running',error_type=NULL WHERE run_id=? AND step_id=?",
                        (run_id, sid),
                    )
            try:
                guard = step.get("when")
                if guard is not None and results[guard["condition"]] is not guard["equals"]:
                    value = None
                    status = "skipped"
                else:
                    max_attempts = step.get("max_attempts", 1)
                    timeout_seconds = step.get("timeout_ms", 5000) / 1000
                    deadline = time.monotonic() + timeout_seconds
                    for attempt in range(1, max_attempts + 1):
                        with self._state() as con:
                            con.execute(
                                "UPDATE steps SET attempt_count=? WHERE run_id=? AND step_id=?",
                                (attempt, run_id, sid),
                            )
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise StepTimeout("SQLite step exceeded its lock-wait budget")
                        try:
                            value = self._evaluate_step(
                                step, results, outcomes, run_id, inject_stop_after_business,
                                # Let the explicit retry loop own lock waiting so each
                                # attempt cannot silently exceed the total deadline.
                                sqlite_timeout=0,
                            )
                        except sqlite3.OperationalError as exc:
                            transient = "locked" in str(exc).lower() or "busy" in str(exc).lower()
                            remaining = deadline - time.monotonic()
                            if not transient:
                                raise
                            if remaining <= 0:
                                raise StepTimeout("SQLite step exceeded its lock-wait budget") from exc
                            if attempt >= max_attempts:
                                raise StepRetryExhausted("SQLite step reached its bounded busy/locked attempt cap") from exc
                            time.sleep(min(0.01 * (2 ** (attempt - 1)), remaining))
                            continue
                        if time.monotonic() > deadline:
                            raise StepTimeout("SQLite step exceeded its lock-wait budget")
                        break
                    status = "completed"
                persisted_value = self._step_receipt(op, value)
                with self._state() as con:
                    con.execute(
                        "UPDATE steps SET output_json=?,status=?,error_type=NULL WHERE run_id=? AND step_id=?",
                        (canonical_json(persisted_value), status, run_id, sid),
                    )
                results[sid], outcomes[sid] = value, status
            except Exception as exc:
                with self._state() as con:
                    con.execute(
                        "UPDATE steps SET status='failed',error_type=? WHERE run_id=? AND step_id=?",
                        (type(exc).__name__, run_id, sid),
                    )
                raise

        last_step = plan["steps"][-1]
        output = self._step_receipt(last_step["op"], results[last_step["id"]])
        with self._state() as con:
            con.execute(
                "UPDATE runs SET status='completed',output_json=?,error_type=NULL WHERE run_id=?",
                (canonical_json(output), run_id),
            )
        return output

    def _evaluate_step(self, step: dict, results: dict, outcomes: dict, run_id: str,
                       inject_stop_after_business: bool, *, sqlite_timeout: float = 5) -> object:
        sid, op = step["id"], step["op"]
        if op == "literal":
            return step["value"]
        if op == "csv_read":
            return self._read_csv(step["path"])
        if op == "csv_filter":
            source = results[step["from"]]
            if not isinstance(source, dict) or not isinstance(source.get("rows"), list):
                raise PlanError("csv_filter requires a csv_read result")
            if step["field"] not in source.get("headers", []):
                raise PlanError(f"CSV field {step['field']} not found in {step['from']}")
            transform = step.get("transform", "identity")
            matches = []
            for row_number, row in enumerate(source["rows"], start=1):
                if not isinstance(row, dict) or step["field"] not in row:
                    raise PlanError("csv_filter received a malformed CSV row")
                candidate = self._transform(row[step["field"]], transform)
                if self._compare(candidate, step["operator"], step["value"]):
                    matches.append({"row_number": row_number, "values": row})
            return {
                "source_path": source["source_path"],
                "source_sha256": source["source_sha256"],
                "headers": source["headers"],
                "row_count": source["row_count"],
                "matches": matches,
                "matched_count": len(matches),
                "matched_row_numbers": [match["row_number"] for match in matches],
            }
        if op in {"field", "map", "condition"}:
            source = results[step["from"]]
            if not isinstance(source, dict):
                raise PlanError(f"step {sid} requires an object from {step['from']}")
            if op == "field":
                if step["field"] not in source:
                    raise PlanError(f"field {step['field']} not found in {step['from']}")
                return source[step["field"]]
            if op == "map":
                mapped = {}
                for target, spec in step["fields"].items():
                    source_field = spec["field"]
                    if source_field not in source:
                        raise PlanError(f"field {source_field} not found in {step['from']}")
                    mapped[target] = self._transform(source[source_field], spec.get("transform", "identity"))
                return mapped
            if step["field"] not in source:
                raise PlanError(f"field {step['field']} not found in {step['from']}")
            return self._compare(source[step["field"]], step["operator"], step["value"])
        if op == "branch":
            selected = step["then"] if results[step["condition"]] else step["else"]
            if outcomes.get(selected) == "skipped":
                raise PlanError("selected branch output was skipped")
            return results[selected]
        if op == "sqlite_put":
            value = {"stored_by": sid}
            payload = canonical_json(results[step["from"]])
            with self._business(timeout=sqlite_timeout) as con:
                con.execute("INSERT OR IGNORE INTO records VALUES (?,?,?)", (run_id, sid, payload))
                stored = con.execute(
                    "SELECT payload_json FROM records WHERE run_id=? AND step_id=?", (run_id, sid)
                ).fetchone()[0]
                if stored != payload:
                    raise PlanError("replayed business write does not match original payload")
            if inject_stop_after_business:
                raise InjectedStop("after durable business write, before runtime receipt")
            return value
        if op == "sqlite_import_csv":
            source = results[step["from"]]
            if not isinstance(source, dict):
                raise PlanError("sqlite_import_csv requires a CSV result")
            digest = source["source_sha256"]
            if isinstance(source.get("rows"), list):
                rows = [(row_number, row) for row_number, row in enumerate(source["rows"], start=1)]
            elif isinstance(source.get("matches"), list):
                rows = [(item["row_number"], item["values"]) for item in source["matches"]]
            else:
                raise PlanError("sqlite_import_csv requires a csv_read or csv_filter result")
            with self._business(timeout=sqlite_timeout) as con:
                for row_number, row in rows:
                    payload = canonical_json(row)
                    existing = con.execute(
                        "SELECT source_sha256,payload_json FROM csv_records "
                        "WHERE run_id=? AND import_step_id=? AND row_number=?",
                        (run_id, sid, row_number),
                    ).fetchone()
                    if existing is not None and existing != (digest, payload):
                        raise PlanError("replayed CSV row does not match its original source")
                    con.execute(
                        "INSERT OR IGNORE INTO csv_records VALUES (?,?,?,?,?)",
                        (run_id, sid, digest, row_number, payload),
                    )
                    stored = con.execute(
                        "SELECT source_sha256,payload_json FROM csv_records "
                        "WHERE run_id=? AND import_step_id=? AND row_number=?",
                        (run_id, sid, row_number),
                    ).fetchone()
                    if stored != (digest, payload):
                        raise PlanError("replayed CSV row does not match its original source")
            if inject_stop_after_business:
                raise InjectedStop("after durable CSV import, before runtime receipt")
            return {"imported_rows": len(rows), "source_sha256": digest}
        # sqlite_get
        store = step["from"]
        if outcomes.get(store) == "skipped":
            raise PlanError("sqlite_get source write was skipped")
        if not isinstance(results[store], dict) or "stored_by" not in results[store]:
            raise PlanError("sqlite_get requires preceding sqlite_put receipt")
        with self._business(timeout=sqlite_timeout) as con:
            row = con.execute(
                "SELECT payload_json FROM records WHERE run_id=? AND step_id=?",
                (run_id, results[store]["stored_by"]),
            ).fetchone()
        if row is None:
            raise PlanError("record not found")
        return json.loads(row[0])

    @staticmethod
    def _step_receipt(op: str, value: object) -> object:
        if op != "csv_read":
            if op == "csv_filter":
                return {key: value[key] for key in (
                    "source_path", "source_sha256", "row_count", "matched_count", "matched_row_numbers"
                )}
            return value
        return {key: value[key] for key in ("source_path", "source_sha256", "headers", "row_count")}

    def _read_csv(self, relative_path: str) -> dict[str, object]:
        if self.input_root is None:
            raise PlanError("CSV workflows require an explicit --input-root")
        relative = PurePosixPath(relative_path)
        candidate = self.input_root
        try:
            for part in relative.parts:
                candidate = candidate / part
                if candidate.is_symlink():
                    raise PlanError("CSV input must not traverse symbolic links")
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise PlanError("CSV input file is unavailable") from exc
        if not resolved.is_relative_to(self.input_root):
            raise PlanError("CSV input resolved outside --input-root")
        if not resolved.is_file() or resolved.suffix.lower() != ".csv":
            raise PlanError("CSV input must be a regular .csv file")
        try:
            if resolved.stat().st_size > MAX_CSV_BYTES:
                raise PlanError("CSV input exceeds 256 KiB")
            with resolved.open("rb") as stream:
                raw = stream.read(MAX_CSV_BYTES + 1)
        except OSError as exc:
            raise PlanError("CSV input could not be read") from exc
        if len(raw) > MAX_CSV_BYTES:
            raise PlanError("CSV input exceeds 256 KiB")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise PlanError("CSV input must use UTF-8 encoding") from exc
        try:
            reader = csv.reader(io.StringIO(text, newline=""), strict=True)
            headers = next(reader, None)
            if not headers or len(headers) > MAX_CSV_COLUMNS:
                raise PlanError("CSV must have between 1 and 64 header columns")
            headers = [header.strip() for header in headers]
            if any(not IDENTIFIER.fullmatch(header) for header in headers):
                raise PlanError("CSV headers must be non-empty safe identifiers")
            if len({header.casefold() for header in headers}) != len(headers):
                raise PlanError("CSV headers must be unique, ignoring case")
            rows = []
            for fields in reader:
                if not fields or len(fields) != len(headers):
                    raise PlanError("CSV row has a missing or extra column")
                if any(len(value) > MAX_CSV_CELL_CHARS or "\x00" in value for value in fields):
                    raise PlanError("CSV cell exceeds 4096 characters or contains NUL")
                if len(rows) >= MAX_CSV_ROWS:
                    raise PlanError("CSV input exceeds 1000 data rows")
                rows.append(dict(zip(headers, fields)))
        except csv.Error as exc:
            raise PlanError("CSV syntax is malformed") from exc
        return {
            "source_path": relative.as_posix(),
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "headers": headers,
            "row_count": len(rows),
            "rows": rows,
        }

    @staticmethod
    def _transform(value: object, transform: str) -> object:
        if transform == "identity":
            return value
        if transform in {"trim", "lower", "upper"}:
            if not isinstance(value, str):
                raise PlanError(f"{transform} transform requires a string")
            if transform == "trim":
                return value.strip()
            return value.lower() if transform == "lower" else value.upper()
        if transform == "string":
            if isinstance(value, (dict, list)):
                raise PlanError("string transform accepts only scalar values")
            return str(value)
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise PlanError("number transform requires a numeric scalar")
        try:
            number = float(value)
        except (ValueError, OverflowError) as exc:
            raise PlanError("number transform received an invalid number") from exc
        if not math.isfinite(number):
            raise PlanError("number transform received a non-finite number")
        return int(number) if number.is_integer() else number

    @staticmethod
    def _compare(left: object, operator: str, right: object) -> bool:
        if operator == "eq":
            return type(left) is type(right) and left == right
        if operator == "ne":
            return type(left) is not type(right) or left != right
        if operator == "contains":
            if not isinstance(left, (str, list)):
                raise PlanError("contains requires a string or list field")
            try:
                return right in left
            except (TypeError, ValueError) as exc:
                raise PlanError("contains value is incompatible with field") from exc
        numeric = (int, float)
        if (isinstance(left, bool) or isinstance(right, bool) or
                not ((isinstance(left, numeric) and isinstance(right, numeric)) or
                     (isinstance(left, str) and isinstance(right, str)))):
            raise PlanError("ordered comparison requires two strings or two numbers")
        try:
            return {"gt": left > right, "gte": left >= right,
                    "lt": left < right, "lte": left <= right}[operator]
        except (TypeError, ValueError) as exc:
            raise PlanError("condition values are not comparable") from exc
