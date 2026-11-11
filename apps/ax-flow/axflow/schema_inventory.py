"""Owner-selected, synthetic-only, read-only offline SQLite schema inspection.

This is NOT a DBVORA service integration or a release authorization. It reads
SQLite catalog metadata, never user table rows, and never writes a database.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import stat
from contextlib import closing
from pathlib import Path

MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_TABLES = 64
MAX_COLUMNS = 256
MAX_RELATIONS = 1024


class SchemaInventoryError(ValueError):
    """Refuse unsupported or potentially unsafe local SQLite inventory."""


def _refuse() -> None:
    raise SchemaInventoryError("offline SQLite metadata inspection refused safely")


def _safe_name(value: object) -> bool:
    return (isinstance(value, str) and 1 <= len(value) <= 128 and
            not re.search(r'[<>\x00-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2066-\u2069]', value))


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _identity(path: Path) -> tuple[int, int, int, int, int]:
    details = path.lstat()
    if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1 or not 100 <= details.st_size <= MAX_SOURCE_BYTES:
        _refuse()
    return (details.st_dev, details.st_ino, details.st_size, details.st_mtime_ns, details.st_ctime_ns)


def inspect_offline_schema(source_path: Path | str, *, synthetic: bool = False,
                           reveal_names: bool = False) -> dict[str, object]:
    """Inspect an explicitly provided offline synthetic DB; never select files automatically.

    Names are returned only under explicit owner review. Default receipts contain
    counts/checksums and zero schema identifiers. This function makes no HTTP
    requests and does not permit a live database or customer-data inspection.
    """
    if synthetic is not True or type(reveal_names) is not bool or not isinstance(source_path, (str, Path)):
        _refuse()
    supplied = str(source_path)
    if not supplied or len(supplied) > 1024 or '\x00' in supplied:
        _refuse()
    candidate = Path(source_path).expanduser()
    if not candidate.is_absolute():
        _refuse()
    try:
        for component in (candidate, *candidate.parents):
            if component.is_symlink():
                _refuse()
        path = candidate.resolve(strict=True)
        before = _identity(path)
        if any(Path(str(path) + ext).exists() for ext in ('-wal', '-shm', '-journal')):
            _refuse()
        with path.open('rb') as stream:
            header = stream.read(100)
        if header[:16] != b'SQLite format 3\x00' or header[18:20] != b'\x01\x01':
            _refuse()
        original_sha = _sha_file(path)
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=2)) as db:
            db.execute('PRAGMA query_only=ON')
            if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                _refuse()
            if db.execute('PRAGMA foreign_key_check').fetchone() is not None:
                _refuse()
            objects = db.execute(
                "SELECT type, name, sql FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name"
            ).fetchall()
            if len(objects) > 1024 or any(
                kind not in {'table', 'index'} or not _safe_name(name) or
                (kind == 'table' and (statement or '').lstrip().upper().startswith('CREATE VIRTUAL'))
                for kind, name, statement in objects
            ):
                _refuse()
            table_names = [name for kind, name, _ in objects if kind == 'table']
            if not 1 <= len(table_names) <= MAX_TABLES:
                _refuse()
            present = set(table_names)
            total_columns = 0
            total_keys = 0
            details = []
            for table in table_names:
                columns = db.execute('PRAGMA table_xinfo(' + _quote(table) + ')').fetchall()
                keys = db.execute('PRAGMA foreign_key_list(' + _quote(table) + ')').fetchall()
                if not 1 <= len(columns) <= MAX_COLUMNS or len(keys) > MAX_RELATIONS:
                    _refuse()
                if any(not _safe_name(row[1]) or not isinstance(row[2], str) or len(row[2]) > 128
                       for row in columns):
                    _refuse()
                if any(row[2] not in present or not _safe_name(row[3]) or
                       (row[4] is not None and not _safe_name(row[4])) for row in keys):
                    _refuse()
                total_columns += len(columns)
                total_keys += len(keys)
                if total_columns > MAX_TABLES * MAX_COLUMNS or total_keys > MAX_RELATIONS:
                    _refuse()
                if reveal_names:
                    details.append({
                        'table': table,
                        'columns': [{'name': row[1], 'type': row[2],
                                     'not_null_declared': bool(row[3]), 'pk_position': row[5]}
                                    for row in columns],
                        'foreign_keys': [{'target_table': row[2], 'from': row[3], 'to': row[4]}
                                         for row in keys],
                    })
        if _identity(path) != before or _sha_file(path) != original_sha:
            _refuse()
        return {
            'version': 'hae.offline.schema.v1', 'engine': 'sqlite',
            'source_sha256': original_sha, 'source_size_bytes': before[2],
            'table_count': len(table_names), 'column_count': total_columns,
            'foreign_key_count': total_keys, 'identifiers_visible': reveal_names,
            'tables': details if reveal_names else [],
            'source_unchanged': True, 'dbvora_remote_verified': False,
            'customer_ready': False, 'release_gate': 'HOLD',
        }
    except (OSError, sqlite3.Error, UnicodeError, RuntimeError, ValueError) as exc:
        if isinstance(exc, SchemaInventoryError):
            raise
        _refuse()
