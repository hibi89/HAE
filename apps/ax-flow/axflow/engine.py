"""Typed workflow subset and independent SQLite-backed execution (synthetic MVP)."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
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
        allowed = {"literal": {"id", "op", "value"}, "field": {"id", "op", "from", "field"},
                   "sqlite_put": {"id", "op", "from"}, "sqlite_get": {"id", "op", "from"}}
        if op not in allowed or set(step) != allowed[op]:
            raise PlanError(f"unknown operation or invalid fields for {ident}")
        if op != "literal" and (not isinstance(step["from"], str) or step["from"] not in seen):
            raise PlanError("step source must reference an earlier step")
        if op == "field" and (not isinstance(step["field"], str) or not IDENTIFIER.fullmatch(step["field"])):
            raise PlanError("field name must be a safe identifier")
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
            con.execute("CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, plan_hash TEXT NOT NULL, status TEXT NOT NULL, output_json TEXT)")
            con.execute("CREATE TABLE IF NOT EXISTS steps (run_id TEXT NOT NULL, step_id TEXT NOT NULL, output_json TEXT NOT NULL, PRIMARY KEY(run_id,step_id))")
        with self._business() as con:
            con.execute("CREATE TABLE IF NOT EXISTS records (run_id TEXT NOT NULL, step_id TEXT NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY(run_id,step_id))")

    def _state(self):
        return sqlite3.connect(self.state_path, timeout=5)

    def _business(self):
        return sqlite3.connect(self.business_path, timeout=5)

    def execute(self, plan: object, run_id: str, *, approve_writes: bool = False,
                inject_stop_after_business: bool = False) -> object:
        validate(plan)
        if not isinstance(run_id, str) or not IDENTIFIER.fullmatch(run_id):
            raise PlanError("run_id must be a safe identifier")
        if any(s["op"] == "sqlite_put" for s in plan["steps"]) and not approve_writes:
            raise ApprovalRequired("explicit --approve-writes required for local SQLite writes")
        digest = hashlib.sha256(canonical_json(plan).encode("utf-8")).hexdigest()
        with self._state() as con:
            existing = con.execute("SELECT plan_hash,status,output_json FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if existing is None:
                con.execute("INSERT INTO runs VALUES (?,?,?,NULL)", (run_id, digest, "running"))
            elif existing[0] != digest:
                raise PlanError("same run id cannot be reused with a different plan")
            elif existing[1] == "completed":
                return json.loads(existing[2])
        results = {}
        for step in plan["steps"]:
            sid, op = step["id"], step["op"]
            with self._state() as con:
                saved = con.execute("SELECT output_json FROM steps WHERE run_id=? AND step_id=?", (run_id, sid)).fetchone()
            if saved is not None:
                results[sid] = json.loads(saved[0]); continue
            if op == "literal":
                value = step["value"]
            elif op == "field":
                source = results[step["from"]]
                if not isinstance(source, dict) or step["field"] not in source:
                    raise PlanError(f"field {step['field']} not found in {step['from']}")
                value = source[step["field"]]
            elif op == "sqlite_put":
                value = {"stored_by": sid}
                payload = canonical_json(results[step["from"]])
                with self._business() as con:
                    con.execute("INSERT OR IGNORE INTO records VALUES (?,?,?)", (run_id, sid, payload))
                    stored = con.execute("SELECT payload_json FROM records WHERE run_id=? AND step_id=?", (run_id, sid)).fetchone()[0]
                    if stored != payload:
                        raise PlanError("replayed business write does not match original payload")
                if inject_stop_after_business:
                    raise InjectedStop("after durable business write, before runtime receipt")
            else:  # sqlite_get
                store = step["from"]
                if not isinstance(results[store], dict) or "stored_by" not in results[store]:
                    raise PlanError("sqlite_get requires preceding sqlite_put receipt")
                with self._business() as con:
                    row = con.execute("SELECT payload_json FROM records WHERE run_id=? AND step_id=?", (run_id, results[store]["stored_by"])).fetchone()
                if row is None:
                    raise PlanError("record not found")
                value = json.loads(row[0])
            with self._state() as con:
                con.execute("INSERT OR IGNORE INTO steps VALUES (?,?,?)", (run_id, sid, canonical_json(value)))
            results[sid] = value
        output = results[plan["steps"][-1]["id"]]
        with self._state() as con:
            con.execute("UPDATE runs SET status='completed',output_json=? WHERE run_id=?", (canonical_json(output), run_id))
        return output
