"""Read-only inspection of synthetic AX FLOW runtime state."""
from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.parse import quote


class RunLogError(ValueError):
    """Missing or incompatible runtime ledger."""


def inspect_run(state_path: Path, run_id: str) -> dict[str, object]:
    """Return run status without exposing step payloads or modifying SQLite."""
    from .engine import IDENTIFIER

    if not isinstance(run_id, str) or not IDENTIFIER.fullmatch(run_id):
        raise RunLogError("run_id must be a safe identifier")
    db = Path(state_path).expanduser().resolve(strict=False)
    if not db.is_file():
        raise RunLogError("runtime ledger does not exist")
    uri = "file:" + quote(db.as_posix(), safe="/:") + "?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=2)) as con:
            columns = {row[1] for row in con.execute("PRAGMA table_info(runs)")}
            error_column = "error_type" if "error_type" in columns else "NULL"
            row = con.execute(
                f"SELECT status, plan_hash, {error_column} FROM runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if row is None:
                raise RunLogError("run_id not found")
            step_columns = {row[1] for row in con.execute("PRAGMA table_info(steps)")}
            if "status" in step_columns:
                step_rows = con.execute(
                    "SELECT status,COUNT(*) FROM steps WHERE run_id=? GROUP BY status", (run_id,)
                ).fetchall()
                outcome_counts = {name: 0 for name in ("completed", "failed", "running", "skipped")}
                for status, count in step_rows:
                    if status in outcome_counts:
                        outcome_counts[status] = count
                step_count = sum(count for _, count in step_rows)
            else:
                step_count = con.execute(
                    "SELECT COUNT(*) FROM steps WHERE run_id=?", (run_id,)
                ).fetchone()[0]
                outcome_counts = {"completed": step_count, "failed": 0, "running": 0, "skipped": 0}
    except sqlite3.DatabaseError as exc:
        raise RunLogError("invalid or unreadable runtime ledger") from exc
    return {
        "run_id": run_id,
        "status": row[0],
        "steps_recorded": step_count,
        "step_outcomes": outcome_counts,
        "plan_sha256": row[1],
        "error_type": row[2],
    }


def inspect_audit(state_path: Path, run_id: str) -> dict[str, object]:
    """Return metadata-only, append-only execution events for one existing run."""
    from .engine import IDENTIFIER
    import json

    if not isinstance(run_id, str) or not IDENTIFIER.fullmatch(run_id):
        raise RunLogError("run_id must be a safe identifier")
    db = Path(state_path).expanduser().resolve(strict=False)
    if not db.is_file():
        raise RunLogError("runtime ledger does not exist")
    uri = "file:" + quote(db.as_posix(), safe="/:") + "?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=2)) as con:
            run = con.execute("SELECT plan_hash FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if run is None:
                raise RunLogError("run_id not found")
            integrity = con.execute("PRAGMA quick_check(1)").fetchone()
            if not integrity or integrity[0] != "ok":
                raise RunLogError("runtime audit ledger integrity check failed")
            rows = con.execute(
                "SELECT plan_hash,event_type,occurred_at,details_json FROM audit_events "
                "WHERE run_id=? ORDER BY event_id", (run_id,)
            ).fetchall()
            approvals = con.execute(
                "SELECT plan_hash,scope_json,approved_at,method FROM approval_receipts "
                "WHERE run_id=? ORDER BY approval_id", (run_id,)
            ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise RunLogError("invalid or unreadable runtime audit ledger") from exc
    events = []
    for plan_hash, event_type, occurred_at, details_json in rows:
        if plan_hash != run[0]:
            raise RunLogError("audit event plan does not match its run")
        try:
            details = json.loads(details_json)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RunLogError("malformed audit event") from exc
        if not isinstance(details, dict):
            raise RunLogError("malformed audit event")
        events.append({"event_type": event_type, "occurred_at": occurred_at, "details": details})
    approval_receipts = []
    for plan_hash, scope_json, approved_at, method in approvals:
        if plan_hash != run[0]:
            raise RunLogError("approval receipt plan does not match its run")
        try:
            scope = json.loads(scope_json)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise RunLogError("malformed approval receipt") from exc
        if not isinstance(scope, dict) or scope.get("plan_sha256") != run[0]:
            raise RunLogError("malformed approval receipt")
        approval_receipts.append({"scope": scope, "approved_at": approved_at, "method": method})
    return {"run_id": run_id, "plan_sha256": run[0], "events": events,
            "approval_receipts": approval_receipts}


def inspect_business_ledger(business_path: Path) -> None:
    """Verify an existing local SQLite business ledger without creating or repairing it.

    Every supported v0 Engine initializes both tables. A truncated/replaced DB
    must fail closed on resume rather than be silently reinitialized.
    """
    db = Path(business_path).expanduser().resolve(strict=False)
    if not db.is_file():
        raise RunLogError("business SQLite ledger is missing")
    uri = "file:" + quote(db.as_posix(), safe="/:") + "?mode=ro"
    required = {
        "records": {"run_id", "step_id", "payload_json"},
        "csv_records": {"run_id", "import_step_id", "source_sha256", "row_number", "payload_json"},
    }
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=2)) as con:
            for table, columns in required.items():
                found = {row[1] for row in con.execute(f"PRAGMA table_info({table})")}
                if not columns.issubset(found):
                    raise RunLogError("business SQLite ledger schema is missing or incompatible")
            result = con.execute("PRAGMA quick_check(1)").fetchone()
            if not result or result[0] != "ok":
                raise RunLogError("business SQLite ledger integrity check failed")
    except sqlite3.DatabaseError as exc:
        raise RunLogError("invalid or unreadable business SQLite ledger") from exc


def inspect_completed_business_receipts(
    state_path: Path, business_path: Path, run_id: str, plan: dict
) -> None:
    """Fail closed when a completed write checkpoint lost its business receipt.

    Reads both existing SQLite databases in read-only mode. Incomplete writes
    may legitimately have no receipt and are left to Engine's idempotent retry.
    """
    from .engine import IDENTIFIER
    import json

    if not isinstance(run_id, str) or not IDENTIFIER.fullmatch(run_id):
        raise RunLogError("run_id must be a safe identifier")
    state = Path(state_path).expanduser().resolve(strict=False)
    business = Path(business_path).expanduser().resolve(strict=False)
    if not state.is_file() or not business.is_file():
        raise RunLogError("required SQLite ledger is missing")
    s_uri = "file:" + quote(state.as_posix(), safe="/:") + "?mode=ro"
    b_uri = "file:" + quote(business.as_posix(), safe="/:") + "?mode=ro"
    try:
        with closing(sqlite3.connect(s_uri, uri=True, timeout=2)) as s, closing(
            sqlite3.connect(b_uri, uri=True, timeout=2)
        ) as b:
            for step in plan["steps"]:
                op = step["op"]
                if op not in {"sqlite_put", "sqlite_import_csv"}:
                    continue
                receipt = s.execute(
                    "SELECT status,output_json FROM steps WHERE run_id=? AND step_id=?",
                    (run_id, step["id"]),
                ).fetchone()
                if receipt is None or receipt[0] != "completed":
                    continue
                if op == "sqlite_put":
                    found = b.execute(
                        "SELECT 1 FROM records WHERE run_id=? AND step_id=?",
                        (run_id, step["id"]),
                    ).fetchone()
                    if found is None:
                        raise RunLogError("completed SQLite write receipt is missing")
                else:
                    output = json.loads(receipt[1])
                    expected = output.get("imported_rows") if isinstance(output, dict) else None
                    if type(expected) is not int or not 0 <= expected <= 1000:
                        raise RunLogError("completed CSV import receipt is invalid")
                    actual = b.execute(
                        "SELECT COUNT(*) FROM csv_records WHERE run_id=? AND import_step_id=?",
                        (run_id, step["id"]),
                    ).fetchone()[0]
                    if actual != expected:
                        raise RunLogError("completed CSV import row receipts are missing or inconsistent")
    except sqlite3.DatabaseError as exc:
        raise RunLogError("invalid or unreadable completed write receipts") from exc
    except (ValueError, TypeError) as exc:
        if isinstance(exc, RunLogError):
            raise
        raise RunLogError("malformed completed write receipt") from exc
