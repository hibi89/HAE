"""Typed workflow subset and independent SQLite-backed execution (synthetic MVP)."""
from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

VERSION = "axflow.ir.v0"
IDENTIFIER = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{0,31}$")
MAX_STEPS = 32
MAX_SPEC_BYTES = 65536


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
    if not isinstance(plan, dict) or set(plan) != {"version", "steps"} or plan["version"] != VERSION:
        raise PlanError("expected versioned AX FLOW IR with only version and steps")
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
            "sqlite_put": {"id", "op", "from"},
            "sqlite_get": {"id", "op", "from"},
        }
        optional = {
            "field": {"when"},
            "map": {"when"},
            "sqlite_put": {"when", "max_attempts", "timeout_ms"},
            "sqlite_get": {"when", "max_attempts", "timeout_ms"},
        }
        allowed = fields.get(op)
        if allowed is None or not allowed <= set(step) or set(step) - allowed - optional.get(op, set()):
            raise PlanError(f"unknown operation or invalid fields for {ident}")
        if op in {"field", "map", "condition", "sqlite_put", "sqlite_get"} and (
                not isinstance(step["from"], str) or step["from"] not in seen):
            raise PlanError("step source must reference an earlier step")
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
        if op == "branch":
            condition = step["condition"]
            then_step, else_step = step["then"], step["else"]
            if (not isinstance(condition, str) or condition not in seen or
                    step_ops.get(condition) != "condition"):
                raise PlanError("branch condition must reference an earlier condition step")
            if (not isinstance(then_step, str) or then_step not in seen or
                    not isinstance(else_step, str) or else_step not in seen):
                raise PlanError("branch outputs must reference earlier steps")
        if op in {"sqlite_put", "sqlite_get"}:
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

    def __init__(self, state_path: Path, business_path: Path):
        self.state_path = Path(state_path).expanduser().resolve()
        self.business_path = Path(business_path).expanduser().resolve()
        if self.state_path == self.business_path:
            raise PlanError("runtime and business SQLite files must be distinct")
        if not self.state_path.parent.is_dir() or not self.business_path.parent.is_dir():
            raise PlanError("both database parent directories must already exist")
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
                inject_stop_after_business: bool = False) -> object:
        validate(plan)
        if not isinstance(run_id, str) or not IDENTIFIER.fullmatch(run_id):
            raise PlanError("run_id must be a safe identifier")
        if any(s["op"] == "sqlite_put" for s in plan["steps"]) and not approve_writes:
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
                results[sid] = json.loads(saved[0])
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
                with self._state() as con:
                    con.execute(
                        "UPDATE steps SET output_json=?,status=?,error_type=NULL WHERE run_id=? AND step_id=?",
                        (canonical_json(value), status, run_id, sid),
                    )
                results[sid], outcomes[sid] = value, status
            except Exception as exc:
                with self._state() as con:
                    con.execute(
                        "UPDATE steps SET status='failed',error_type=? WHERE run_id=? AND step_id=?",
                        (type(exc).__name__, run_id, sid),
                    )
                raise

        output = results[plan["steps"][-1]["id"]]
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
