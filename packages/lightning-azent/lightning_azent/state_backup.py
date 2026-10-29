"""Verified, no-overwrite backup and fresh-path restore for runtime SQLite state.

Same-destination publishers coordinate through a persistent OS-locked sidecar;
after an unclean process exit, the next attempt removes only that destination's
unpublished regular staging files before creating a new artifact.
"""
from __future__ import annotations

import hashlib
import errno
import os
import sqlite3
import stat
import tempfile
import time
from contextlib import closing, contextmanager
from pathlib import Path


class StateBackupError(ValueError):
    """A local runtime-state backup or restore could not complete safely."""


@contextmanager
def _destination_lock(destination: Path, key: str):
    """Serialize cooperative publishers and stale-stage cleanup per target."""
    lock_path = destination.parent / f".axflow-state-{key}.lock"
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(lock_path, flags, 0o600)
    except OSError:
        raise StateBackupError("runtime database destination lock could not be opened safely") from None

    locked = False
    try:
        opened = os.fstat(fd)
        current = lock_path.lstat()
        attributes = getattr(opened, "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
                or attributes & reparse_flag):
            raise StateBackupError("runtime database destination lock is not a private regular file")

        if os.fstat(fd).st_size == 0:
            os.write(fd, b"\0")
        os.lseek(fd, 0, os.SEEK_SET)
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    break
                except OSError as exc:
                    if (exc.errno not in (errno.EACCES, errno.EDEADLK)
                            and getattr(exc, "winerror", None) not in (33, 36)):
                        raise
                    time.sleep(0.05)
            locked = True
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX)
            locked = True
        yield
    except StateBackupError:
        raise
    except OSError:
        raise StateBackupError("runtime database destination lock failed safely") from None
    finally:
        try:
            if locked:
                if os.name == "nt":
                    import msvcrt

                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _remove_abandoned_stages(destination: Path, key: str) -> None:
    """Remove only this destination's regular, unlinked staging artifacts.

    The destination lock is held by the caller, so no cooperative backup can
    still be using these names. Non-regular or multiply-linked entries fail
    closed instead of being followed or removed.
    """
    prefix = f".axflow-state-{key}-"
    for staged in destination.parent.glob(prefix + "*.part"):
        try:
            details = staged.lstat()
        except FileNotFoundError:
            continue
        attributes = getattr(details, "st_file_attributes", 0)
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if (not stat.S_ISREG(details.st_mode) or details.st_nlink != 1
                or attributes & reparse_flag):
            raise StateBackupError("abandoned runtime staging path is not a private regular file")
        try:
            staged.unlink()
        except OSError:
            raise StateBackupError("abandoned runtime staging file could not be removed safely") from None


def _path(path: Path | str) -> Path:
    if not isinstance(path, (Path, str)) or not str(path):
        raise StateBackupError("runtime database path is invalid")
    candidate = Path(path).expanduser().absolute()
    for item in (candidate, *candidate.parents):
        if item.is_symlink():
            raise StateBackupError("runtime database symlink paths are not supported")
    return candidate.resolve(strict=False)


def _fingerprint(path: Path) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    details = path.stat()
    return digest.hexdigest(), details.st_size, details.st_mtime_ns


def _require_ledger(connection: sqlite3.Connection) -> None:
    tables = {
        row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    if not {"runs", "steps"} <= tables:
        raise StateBackupError("file is not an AX FLOW runtime ledger")
    runs = {row[1] for row in connection.execute("PRAGMA table_info(runs)")}
    steps = {row[1] for row in connection.execute("PRAGMA table_info(steps)")}
    if not {"run_id", "plan_hash", "status"} <= runs or not {
        "run_id", "step_id", "output_json"
    } <= steps:
        raise StateBackupError("runtime ledger schema is incompatible")


def _integrity(path: Path) -> None:
    try:
        uri = path.as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=2)) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchall()
            if result != [("ok",)]:
                raise StateBackupError("runtime database integrity check failed")
            _require_ledger(connection)
    except sqlite3.Error:
        raise StateBackupError("runtime database could not be verified") from None


def _clone_runtime_state(source_path: Path | str, destination_path: Path | str) -> dict[str, object]:
    source = _path(source_path)
    destination = _path(destination_path)
    if source == destination:
        raise StateBackupError("source and destination must be different files")
    if not source.is_file() or not stat.S_ISREG(source.stat().st_mode):
        raise StateBackupError("runtime database source must be an existing regular file")
    if not destination.parent.is_dir():
        raise StateBackupError("destination parent directory must already exist")
    key = hashlib.sha256(os.fsencode(os.path.normcase(str(destination)))).hexdigest()[:24]
    with _destination_lock(destination, key):
        _remove_abandoned_stages(destination, key)
        try:
            destination.lstat()
        except FileNotFoundError:
            pass
        else:
            raise StateBackupError("destination already exists; overwrite is refused")

        before = _fingerprint(source)
        staged: Path | None = None
        published = False
        completed = False
        try:
            fd, name = tempfile.mkstemp(prefix=f".axflow-state-{key}-", suffix=".part", dir=destination.parent)
            os.close(fd)
            staged = Path(name)
            source_uri = source.as_uri() + "?mode=ro"
            with closing(sqlite3.connect(source_uri, uri=True, timeout=2)) as src:
                _require_ledger(src)
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
                raise StateBackupError("runtime database source changed during backup")
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
        except StateBackupError:
            raise
        except (OSError, sqlite3.Error, ValueError, TypeError):
            raise StateBackupError("runtime database backup or restore failed safely") from None
        finally:
            if published and not completed:
                try:
                    destination.unlink(missing_ok=True)
                except OSError:
                    pass
            if staged is not None:
                staged.unlink(missing_ok=True)


def backup_runtime_state(source_path: Path | str, backup_path: Path | str) -> dict[str, object]:
    """Create a verified SQLite online backup at a new path; never overwrite."""
    return _clone_runtime_state(source_path, backup_path)


def restore_runtime_state(backup_path: Path | str, state_path: Path | str) -> dict[str, object]:
    """Restore a verified ledger into a new file; never overwrite the source or target."""
    return _clone_runtime_state(backup_path, state_path)
