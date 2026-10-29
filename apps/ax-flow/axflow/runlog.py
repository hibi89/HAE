"""Read-only inspection of synthetic AX FLOW runtime state."""
from __future__ import annotations

import json
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
            output_column = "output_json" if "output_json" in columns else "NULL"
            row = con.execute(
                f"SELECT status, plan_hash, {error_column}, {output_column} FROM runs WHERE run_id=?", (run_id,)
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
    result_summary = _safe_result_summary(row[3])
    return {
        "run_id": run_id,
        "status": row[0],
        "steps_recorded": step_count,
        "step_outcomes": outcome_counts,
        "plan_sha256": row[1],
        "error_type": row[2],
        "result_summary": result_summary,
    }


def _safe_result_summary(serialized: object) -> dict[str, object] | None:
    """Expose only bounded counts from the final receipt, never its payload."""
    if not isinstance(serialized, str) or len(serialized) > 65536:
        return None
    try:
        value = json.loads(serialized)
    except (json.JSONDecodeError, RecursionError, ValueError):
        return None
    if not isinstance(value, dict):
        return None

    from .engine import MAX_CSV_ROWS

    fields = ("imported_rows", "matched_count", "normalized_count", "row_count", "duplicate_count")
    counts = {
        key: value[key]
        for key in fields
        if type(value.get(key)) is int and 0 <= value[key] <= MAX_CSV_ROWS
    }
    if "imported_rows" in counts:
        return {"kind": "saved", "count": counts["imported_rows"],
                "duplicate_count": counts.get("duplicate_count", 0)}
    if "matched_count" in counts:
        return {"kind": "matched", "count": counts["matched_count"]}
    if "normalized_count" in counts:
        return {"kind": "normalized", "count": counts["normalized_count"],
                "duplicate_count": counts.get("duplicate_count", 0)}
    if "row_count" in counts:
        return {"kind": "processed", "count": counts["row_count"]}
    return None

