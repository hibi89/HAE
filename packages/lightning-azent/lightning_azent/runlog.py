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
