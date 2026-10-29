"""Read-only inspection of synthetic AX FLOW runtime state."""
from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from urllib.parse import quote


class RunLogError(ValueError):
    """Missing or incompatible runtime ledger."""


_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
_RUN_STATUSES = {"running", "failed", "completed"}
_UI_RUN_ID = re.compile(r"^Gui[A-Fa-f0-9]{12}$")


def list_recent_runs(state_path: Path, limit: int = 10) -> list[dict[str, object]]:
    """Read a bounded, redacted run index from the runtime ledger only."""
    from .engine import IDENTIFIER

    if type(limit) is not int or not 1 <= limit <= 20:
        raise RunLogError("limit must be an integer from 1 through 20")
    db = Path(state_path).expanduser().resolve(strict=False)
    if not db.is_file():
        return []
    uri = "file:" + quote(db.as_posix(), safe="/:") + "?mode=ro"
    try:
        with closing(sqlite3.connect(uri, uri=True, timeout=2)) as con:
            columns = {row[1] for row in con.execute("PRAGMA table_info(runs)")}
            if not columns:
                raise RunLogError("runtime ledger has no run table")
            if "created_at" not in columns:
                return []
            rows = con.execute(
                "SELECT run_id,status,created_at FROM runs "
                "WHERE created_at GLOB ? AND run_id GLOB ? "
                "ORDER BY created_at DESC,run_id DESC LIMIT ?",
                ("[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9][0-9][0-9]Z",
                 "Gui[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]", limit),
            ).fetchall()
            step_columns = {row[1] for row in con.execute("PRAGMA table_info(steps)")}
            if not step_columns:
                raise RunLogError("runtime ledger has no step table")
            has_status = "status" in step_columns
            result = []
            for run_id, status, created_at in rows:
                if not isinstance(run_id, str) or not _UI_RUN_ID.fullmatch(run_id):
                    continue
                outcomes = {name: 0 for name in ("completed", "failed", "running", "skipped")}
                if has_status:
                    for name, count in con.execute(
                        "SELECT status,COUNT(*) FROM steps WHERE run_id=? GROUP BY status", (run_id,)
                    ):
                        if name in outcomes and type(count) is int and 0 <= count <= 32:
                            outcomes[name] = count
                else:
                    count = con.execute("SELECT COUNT(*) FROM steps WHERE run_id=?", (run_id,)).fetchone()[0]
                    if type(count) is int and 0 <= count <= 32:
                        outcomes["completed"] = count
                timestamp = created_at if isinstance(created_at, str) and len(created_at) == 24 \
                    and _TIMESTAMP.fullmatch(created_at) else None
                if timestamp is None:
                    continue
                try:
                    datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
                except ValueError:
                    continue
                result.append({
                    "run_id": run_id,
                    "status": status if status in _RUN_STATUSES else "unknown",
                    "created_at": timestamp,
                    "steps_recorded": sum(outcomes.values()),
                    "step_outcomes": outcomes,
                })
            return result
    except sqlite3.DatabaseError as exc:
        raise RunLogError("invalid or unreadable runtime ledger") from exc


def ensure_run_timestamp_capture(state_path: Path) -> None:
    """Install an additive runtime-ledger timestamp column and insert trigger."""
    db = Path(state_path).expanduser().resolve(strict=False)
    if not db.is_file():
        raise RunLogError("runtime ledger does not exist")
    try:
        with closing(sqlite3.connect(db, timeout=5)) as con:
            with con:
                columns = {row[1] for row in con.execute("PRAGMA table_info(runs)")}
                if not columns:
                    raise RunLogError("runtime ledger has no run table")
                if "created_at" not in columns:
                    con.execute("ALTER TABLE runs ADD COLUMN created_at TEXT")
                con.execute("CREATE INDEX IF NOT EXISTS hae_runs_created_at_idx ON runs(created_at DESC,run_id DESC)")
                con.execute(
                    "CREATE TRIGGER IF NOT EXISTS hae_runs_set_created_at "
                    "AFTER INSERT ON runs WHEN NEW.created_at IS NULL BEGIN "
                    "UPDATE runs SET created_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') "
                    "WHERE run_id=NEW.run_id; END"
                )
    except sqlite3.DatabaseError as exc:
        raise RunLogError("could not prepare runtime run timestamps") from exc


def record_run_started_at(state_path: Path, run_id: str, timestamp: str) -> None:
    """Stamp an LA-created run after its public v0 executor has initialized the ledger."""
    from .engine import IDENTIFIER

    if not isinstance(run_id, str) or not IDENTIFIER.fullmatch(run_id):
        raise RunLogError("run_id must be a safe identifier")
    if not isinstance(timestamp, str) or len(timestamp) != 24 or not _TIMESTAMP.fullmatch(timestamp):
        raise RunLogError("timestamp must be an ISO-8601 UTC value")
    try:
        datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise RunLogError("timestamp must be a valid ISO-8601 UTC value") from exc
    ensure_run_timestamp_capture(state_path)
    db = Path(state_path).expanduser().resolve(strict=True)
    try:
        with closing(sqlite3.connect(db, timeout=5)) as con:
            with con:
                con.execute(
                    "UPDATE runs SET created_at=COALESCE(created_at,?) WHERE run_id=?",
                    (timestamp, run_id),
                )
    except sqlite3.DatabaseError as exc:
        raise RunLogError("could not record runtime timestamp") from exc


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

