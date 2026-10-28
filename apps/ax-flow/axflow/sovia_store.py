"""Bounded storage for SOVIA post-run metadata, separate from business SQLite."""
from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.parse import quote


class SOVIAStoreError(ValueError):
    """SOVIA result metadata could not be read or stored safely."""


_RUN_ID = re.compile(r"^Gui[A-Fa-f0-9]{12}$")
_SHA = re.compile(r"^[a-f0-9]{64}$")
_MAX_REPORT_BYTES = 256 * 1024


class SOVIAStore:
    def __init__(self, state_path: Path, business_path: Path):
        state = Path(state_path).expanduser().resolve(strict=False)
        business = Path(business_path).expanduser().resolve(strict=False)
        self.path = state.with_name(state.name + ".sovia-audit.sqlite")
        if self.path == state or self.path == business:
            raise SOVIAStoreError("SOVIA audit store must be separate from runtime and business databases")

    def _check_path(self, *, require_file: bool) -> None:
        if self.path.parent.is_symlink() or self.path.is_symlink():
            raise SOVIAStoreError("SOVIA audit store path cannot contain a symbolic link")
        if require_file and not self.path.is_file():
            raise SOVIAStoreError("SOVIA audit record is unavailable")
        if self.path.exists() and not self.path.is_file():
            raise SOVIAStoreError("SOVIA audit store must be a regular file")

    def save(self, run_id: str, plan_sha256: str, report: dict[str, object]) -> None:
        if not _RUN_ID.fullmatch(run_id) or not _SHA.fullmatch(plan_sha256):
            raise SOVIAStoreError("SOVIA audit identifiers are invalid")
        try:
            encoded = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError, OverflowError) as exc:
            raise SOVIAStoreError("SOVIA report is not safe JSON") from exc
        if len(encoded.encode("utf-8")) > _MAX_REPORT_BYTES:
            raise SOVIAStoreError("SOVIA report exceeds the local metadata limit")
        self._check_path(require_file=False)
        try:
            with closing(sqlite3.connect(self.path, timeout=2)) as connection:
                connection.execute("PRAGMA trusted_schema=OFF")
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS sovia_reports ("
                    "run_id TEXT PRIMARY KEY, plan_sha256 TEXT NOT NULL, report_json TEXT NOT NULL)"
                )
                existing = connection.execute(
                    "SELECT plan_sha256 FROM sovia_reports WHERE run_id=?", (run_id,)
                ).fetchone()
                if existing is not None and existing[0] != plan_sha256:
                    raise SOVIAStoreError("SOVIA audit run ID is already bound to another plan")
                connection.execute(
                    "INSERT INTO sovia_reports(run_id,plan_sha256,report_json) VALUES (?,?,?) "
                    "ON CONFLICT(run_id) DO UPDATE SET report_json=excluded.report_json "
                    "WHERE sovia_reports.plan_sha256=excluded.plan_sha256",
                    (run_id, plan_sha256, encoded),
                )
                connection.commit()
        except SOVIAStoreError:
            raise
        except (sqlite3.Error, OSError, ValueError) as exc:
            raise SOVIAStoreError("SOVIA audit metadata could not be stored safely") from exc

    def get(self, run_id: str) -> dict[str, object] | None:
        if not _RUN_ID.fullmatch(run_id):
            raise SOVIAStoreError("SOVIA audit run ID is invalid")
        self._check_path(require_file=True)
        uri = "file:" + quote(self.path.as_posix(), safe="/:") + "?mode=ro"
        try:
            with closing(sqlite3.connect(uri, uri=True, timeout=2)) as connection:
                connection.execute("PRAGMA query_only=ON")
                integrity = connection.execute("PRAGMA quick_check(1)").fetchone()
                if not integrity or integrity[0] != "ok":
                    raise SOVIAStoreError("SOVIA audit store integrity check failed")
                columns = {row[1] for row in connection.execute("PRAGMA table_info(sovia_reports)")}
                if columns != {"run_id", "plan_sha256", "report_json"}:
                    raise SOVIAStoreError("SOVIA audit store contract is incompatible")
                row = connection.execute(
                    "SELECT plan_sha256,report_json FROM sovia_reports WHERE run_id=?", (run_id,)
                ).fetchone()
        except SOVIAStoreError:
            raise
        except (sqlite3.Error, OSError, ValueError) as exc:
            raise SOVIAStoreError("SOVIA audit metadata could not be read safely") from exc
        if row is None:
            return None
        if (not isinstance(row[0], str) or not _SHA.fullmatch(row[0])
                or not isinstance(row[1], str)
                or len(row[1].encode("utf-8")) > _MAX_REPORT_BYTES):
            raise SOVIAStoreError("SOVIA audit record is invalid")
        try:
            report = json.loads(row[1])
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise SOVIAStoreError("SOVIA audit record is invalid") from exc
        if (not isinstance(report, dict) or report.get("run_id") != run_id
                or report.get("plan_sha256") != row[0]):
            raise SOVIAStoreError("SOVIA audit record does not match its stored plan")
        return report
