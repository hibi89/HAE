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
            step_count = con.execute(
                "SELECT COUNT(*) FROM steps WHERE run_id=?", (run_id,)
            ).fetchone()[0]
    except sqlite3.DatabaseError as exc:
        raise RunLogError("invalid or unreadable runtime ledger") from exc
    return {
        "run_id": run_id,
        "status": row[0],
        "steps_recorded": step_count,
        "plan_sha256": row[1],
        "error_type": row[2],
    }
