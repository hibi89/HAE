"""Read-only, pinned, independent SQLite restore-chain verification.

Uses deterministic SQLite logical dump hashing on *synthetic-only*, small,
quiescent offline databases. It never exports rows/SQL, creates a backup,
restores data, or changes any source path.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import hmac
from pathlib import Path
import re
import sqlite3
import stat

from .schema_inventory import SchemaInventoryError, inspect_offline_schema

_SHA = re.compile(r"^[a-f0-9]{64}$")


class RecoveryChainError(ValueError):
    """Three owner-selected local files cannot be verified as one restore chain."""


def _refuse() -> None:
    raise RecoveryChainError("HAE synthetic SQLite recovery chain refused safely")


def _selected(path: Path | str) -> Path:
    if not isinstance(path, (str, Path)):
        _refuse()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        _refuse()
    # Keep the supplied path intact until the link/parent-link validation runs.
    # Resolving first would silently accept a prohibited symlink alias.
    return candidate


def _identity(path: Path) -> tuple[int, int, int, int, int, int]:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        _refuse()
    return (info.st_dev, info.st_ino, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns, info.st_nlink)


def _logical_digest(path: Path) -> str:
    """Hash row/schema contents via SQLite's read-only canonical dump iterator."""
    digest = hashlib.sha256()
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True,
                                 timeout=2)) as connection:
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA trusted_schema=OFF")
        for statement in connection.iterdump():
            # Length-prefix statements to avoid concatenation ambiguity.
            content = statement.encode("utf-8", "surrogatepass")
            digest.update(len(content).to_bytes(8, "big"))
            digest.update(content)
    return digest.hexdigest()


def verify_synthetic_restore_chain(
    source_path: Path | str, backup_path: Path | str, restored_path: Path | str,
    *, expected_source_sha256: str, expected_backup_sha256: str,
    synthetic: bool = False,
) -> dict[str, object]:
    """Verify SHA-pinned source->backup->restored files, never performing copies.

    Source is first, backup is an existing owner-selected artifact, restore is
    another existing independent file. All must be <=32 MiB, ordinary, closed
    SQLite files without active journals, symlinks, hardlinks or corruption.
    """
    if (synthetic is not True or not isinstance(expected_source_sha256, str)
            or not isinstance(expected_backup_sha256, str)
            or _SHA.fullmatch(expected_source_sha256) is None
            or _SHA.fullmatch(expected_backup_sha256) is None):
        _refuse()
    try:
        paths = (_selected(source_path), _selected(backup_path),
                 _selected(restored_path))
        identities = tuple(_identity(path) for path in paths)
        if len({(item[0], item[1]) for item in identities}) != 3:
            _refuse()
        # The scanner checks all components for links, closed SQLite headers,
        # FK integrity, valid schema, size limits, and SHA-preserving reads.
        before = tuple(inspect_offline_schema(path, synthetic=True)
                       for path in paths)
        if (not hmac.compare_digest(before[0]["source_sha256"], expected_source_sha256)
                or not hmac.compare_digest(before[1]["source_sha256"], expected_backup_sha256)):
            _refuse()
        # Independent row+schema check: byte-identical page images are NOT
        # assumed; backup/restore can have different physical page layouts.
        logical = tuple(_logical_digest(path) for path in paths)
        if logical[0] != logical[1] or logical[1] != logical[2]:
            _refuse()
        after = tuple(inspect_offline_schema(path, synthetic=True)
                      for path in paths)
        identities_after = tuple(_identity(path) for path in paths)
        if (before != after or identities != identities_after
                or any(receipt.get("source_unchanged") is not True for receipt in after)):
            _refuse()
        return {
            "version": "hae.synthetic.sqlite.restore-chain.v1",
            "source_sha256": after[0]["source_sha256"],
            "backup_sha256": after[1]["source_sha256"],
            "restored_sha256": after[2]["source_sha256"],
            "table_count": after[0]["table_count"],
            "column_count": after[0]["column_count"],
            "foreign_key_count": after[0]["foreign_key_count"],
            "logical_schema_and_rows_equal": True,
            "all_three_sources_unchanged": True,
            "independent_restore_verified": True,
            "dbvora_real_process_verified": False,
            "customer_ready": False,
            "release_gate": "HOLD",
        }
    except (SchemaInventoryError, OSError, RuntimeError, ValueError,
            sqlite3.Error, TypeError, UnicodeError, OverflowError):
        _refuse()
