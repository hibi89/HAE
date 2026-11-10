"""No-overwrite offline business SQLite snapshots derived from HAE runtime backup.\n\nOnly a quiescent, bounded ordinary SQLite file is supported. No customer data\nmay leave the owner device or be used without explicit consent.\n"""
from __future__ import annotations

import hashlib
import os
import sqlite3
import stat
import tempfile
from contextlib import closing
from pathlib import Path


class BusinessBackupError(ValueError):
    """A local business-database backup or restore could not complete safely."""


def _path(path: Path | str) -> Path:
    if not isinstance(path, (Path, str)) or not str(path):
        raise BusinessBackupError("business database path is invalid")
    candidate = Path(path).expanduser().absolute()
    for item in (candidate, *candidate.parents):
        if item.is_symlink():
            raise BusinessBackupError("business database symlink paths are not supported")
    return candidate.resolve(strict=False)


def _fingerprint(path: Path) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    details = path.stat()
    return digest.hexdigest(), details.st_size, details.st_mtime_ns


MAX_BUSINESS_BYTES = 32 * 1024 * 1024


def _require_offline_source(path: Path) -> None:
    """Avoid opening live WAL DBs (which could create shared-memory sidecars)."""
    try:
        if not path.is_file() or path.stat().st_size > MAX_BUSINESS_BYTES:
            raise BusinessBackupError("unsupported business SQLite file size")
        if any(Path(str(path) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")):
            raise BusinessBackupError("close the SQLite source and its journal before snapshot")
        with path.open("rb") as stream:
            header = stream.read(100)
        if header[:16] != b"SQLite format 3\x00" or header[18:20] != b"\x01\x01":
            raise BusinessBackupError("only ordinary offline SQLite databases are supported")
    except OSError:
        raise BusinessBackupError("unable to inspect local business SQLite file") from None


def _require_business_db(connection: sqlite3.Connection) -> None:
    objects = connection.execute(
        "SELECT type, name, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
    ).fetchall()
    tables = [name for kind, name, _ in objects if kind == "table"]
    if not 1 <= len(tables) <= 64 or len(objects) > 1024:
        raise BusinessBackupError("unsupported business database table count")
    if any(kind not in {"table", "index"} or (
        kind == "table" and (sql or "").lstrip().upper().startswith("CREATE VIRTUAL")
    ) for kind, _, sql in objects):
        raise BusinessBackupError("unsupported business database schema element")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise BusinessBackupError("business database contains invalid foreign keys")


def _integrity(path: Path) -> None:
    try:
        uri = path.as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=2)) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchall()
            if result != [("ok",)]:
                raise BusinessBackupError("business database integrity check failed")
            _require_business_db(connection)
    except sqlite3.Error:
        raise BusinessBackupError("business database could not be verified") from None


def _clone_runtime_state(source_path: Path | str, destination_path: Path | str) -> dict[str, object]:
    source = _path(source_path)
    destination = _path(destination_path)
    if source == destination:
        raise BusinessBackupError("source and destination must be different files")
    _require_offline_source(source)
    if not source.is_file() or not stat.S_ISREG(source.stat().st_mode) or source.stat().st_nlink != 1:
        raise BusinessBackupError("business database source must be an existing unlinked regular file")
    if not destination.parent.is_dir():
        raise BusinessBackupError("destination parent directory must already exist")
    try:
        destination.lstat()
    except FileNotFoundError:
        pass
    else:
        raise BusinessBackupError("destination already exists; overwrite is refused")

    before = _fingerprint(source)
    staged: Path | None = None
    published = False
    completed = False
    try:
        fd, name = tempfile.mkstemp(prefix=".axflow-state-", suffix=".part", dir=destination.parent)
        os.close(fd)
        staged = Path(name)
        source_uri = source.as_uri() + "?mode=ro"
        with closing(sqlite3.connect(source_uri, uri=True, timeout=2)) as src:
            _require_business_db(src)
            with closing(sqlite3.connect(staged, timeout=2)) as dst:
                src.backup(dst, pages=64, sleep=0.01)

        _integrity(staged)
        staged_info = staged.lstat()
        fd = os.open(staged, os.O_RDWR | getattr(os, "O_NOFOLLOW", 0))
        try:
            opened_info = os.fstat(fd)
            current_info = staged.lstat()
            if (not stat.S_ISREG(opened_info.st_mode) or opened_info.st_nlink != 1 or
                    (opened_info.st_dev, opened_info.st_ino) != (current_info.st_dev, current_info.st_ino) or
                    (staged_info.st_dev, staged_info.st_ino) != (current_info.st_dev, current_info.st_ino)):
                raise OSError("staging file identity changed")
            os.fsync(fd)
        finally:
            os.close(fd)

        after = _fingerprint(source)
        if after != before:
            raise BusinessBackupError("business database source changed during backup")
        if os.name == "nt":
            # Windows os.rename is atomic on the same volume and refuses an existing target.
            os.rename(staged, destination)
            published = True
        else:
            # POSIX os.rename may replace a target, so publish with a no-overwrite hard link.
            os.link(staged, destination)
            published = True
            staged.unlink()
        _integrity(destination)
        digest, size, _ = _fingerprint(destination)
        result = {
            "source_sha256": before[0],
            "source_size_bytes": before[1],
            "artifact_sha256": digest,
            "artifact_size_bytes": size,
            "sqlite_integrity": "ok",
            "source_unchanged": True,
        }
        completed = True
        return result
    except BusinessBackupError:
        raise
    except (OSError, sqlite3.Error, ValueError, TypeError):
        raise BusinessBackupError("business database backup or restore failed safely") from None
    finally:
        if published and not completed:
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                pass
        if staged is not None:
            staged.unlink(missing_ok=True)


def backup_business_state(source_path: Path | str, backup_path: Path | str) -> dict[str, object]:
    """Create a verified SQLite online backup at a new path; never overwrite."""
    return _clone_runtime_state(source_path, backup_path)


def restore_business_state(backup_path: Path | str, state_path: Path | str) -> dict[str, object]:
    """Restore a verified ledger into a new file; never overwrite the source or target."""
    return _clone_runtime_state(backup_path, state_path)


def inspect_business_state(source_path: Path | str) -> dict[str, object]:
    """Return only aggregate non-PII provenance for offline, supported SQLite."""
    source = _path(source_path)
    _require_offline_source(source)
    _integrity(source)
    digest, size, _ = _fingerprint(source)
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True, timeout=2)) as conn:
        _require_business_db(conn)
        count = conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0]
    return {
        "status": "VERIFIED_OFFLINE_SOURCE", "source_sha256": digest,
        "source_size_bytes": size, "table_count": count,
        "sqlite_integrity": "ok", "source_modified": False,
        "customer_ready": False, "release_gate": "HOLD",
    }


def restore_business_state_pinned(
    backup_path: Path | str, new_business_path: Path | str, expected_sha256: str
) -> dict[str, object]:
    """Restore only the owner-selected SHA-pinned backup into a nonexistent path."""
    import re
    if not isinstance(expected_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
        raise BusinessBackupError("backup SHA256 must be explicitly provided")
    source = _path(backup_path)
    _require_offline_source(source)
    if _fingerprint(source)[0] != expected_sha256:
        raise BusinessBackupError("selected backup does not match the expected SHA256")
    return restore_business_state(source, new_business_path)
