"""Owner-scoped, provider-neutral, synthetic-only SQLite asset registry.

The registry is a *separate* explicitly initialized SQLite metadata file.
No source path, table/column identifiers, SQL rows, OAuth material or secrets
are saved. Never rewrite an existing asset identity after source drift.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3
import stat

from .asset_attestation import AssetAttestationError, attest_synthetic_dbvora_asset
from .dbvora_client import DbvoraClient
from .schema_inventory import inspect_offline_schema, SchemaInventoryError

MAX_ASSETS = 64
MAX_REGISTRY_BYTES = 1024 * 1024
REGISTRY_VERSION = 1
DDL = (
    "CREATE TABLE IF NOT EXISTS asset_records("
    "db_id TEXT PRIMARY KEY CHECK(length(db_id)=24), "
    "engine TEXT NOT NULL CHECK(engine='sqlite'), "
    "provider TEXT NOT NULL CHECK(provider='dbvora'), "
    "contract_version TEXT NOT NULL CHECK(contract_version='p0-01.v1'), "
    "source_sha256 TEXT NOT NULL CHECK(length(source_sha256)=64), "
    "evidence_sha256 TEXT NOT NULL CHECK(length(evidence_sha256)=64), "
    "size_bytes INTEGER NOT NULL CHECK(size_bytes>=100), "
    "table_count INTEGER NOT NULL CHECK(table_count>=1), "
    "column_count INTEGER NOT NULL CHECK(column_count>=1), "
    "foreign_key_count INTEGER NOT NULL CHECK(foreign_key_count>=0)"
    ")"
)


class AssetRegistryError(ValueError):
    """No unsafe local metadata operation can continue."""


def _deny() -> None:
    raise AssetRegistryError("HAE synthetic asset registry operation refused safely")


def _absolute(path: Path | str, *, must_exist: bool) -> Path:
    if not isinstance(path, (Path, str)) or not str(path) or len(str(path)) > 1024:
        _deny()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        _deny()
    for part in (candidate, *candidate.parents):
        if part.is_symlink():
            _deny()
    if not candidate.parent.is_dir():
        _deny()
    if must_exist:
        info = candidate.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or not 100 <= info.st_size <= MAX_REGISTRY_BYTES):
            _deny()
    elif candidate.exists() or candidate.is_symlink():
        _deny()
    return candidate.resolve(strict=must_exist)


def _require_layout(conn: sqlite3.Connection) -> None:
    if conn.execute("PRAGMA user_version").fetchone() != (REGISTRY_VERSION,):
        _deny()
    if conn.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        _deny()
    definitions = conn.execute(
        "SELECT name,type FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
    ).fetchall()
    if definitions != [("asset_records", "table")]:
        _deny()
    columns = {row[1] for row in conn.execute("PRAGMA table_info(asset_records)")}
    if columns != {"db_id", "engine", "provider", "contract_version",
                   "source_sha256", "evidence_sha256", "size_bytes",
                   "table_count", "column_count", "foreign_key_count"}:
        _deny()


def _connect_existing(registry: Path, *, writable: bool) -> sqlite3.Connection:
    if any(Path(str(registry) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")):
        _deny()
    return sqlite3.connect(registry.as_uri() + ("?mode=rw" if writable else "?mode=ro"),
                           uri=True, timeout=2)


def initialize_synthetic_registry(
    registry_path: Path | str, *, synthetic: bool = False, acknowledge_new_file: bool = False
) -> dict[str, object]:
    """Create *only* the explicitly owner-approved, new, sidecar metadata file."""
    if synthetic is not True or acknowledge_new_file is not True:
        _deny()
    created = False
    registry = None
    try:
        registry = _absolute(registry_path, must_exist=False)
        fd = os.open(registry, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        os.close(fd)
        created = True
        with closing(sqlite3.connect(registry, timeout=2)) as conn, conn:
            conn.execute(DDL)
            conn.execute("PRAGMA user_version=1")
            _require_layout(conn)
        return {"version": "hae.synthetic.asset-registry.v1",
                "status": "INITIALIZED", "asset_count": 0,
                "customer_ready": False, "release_gate": "HOLD"}
    except (OSError, sqlite3.Error, ValueError, TypeError):
        if created and registry is not None:
            try:
                registry.unlink()
            except OSError:
                pass
        _deny()


def _receipt(record: tuple) -> dict[str, object]:
    return {
        "db_id": record[0], "engine": record[1], "provider": record[2],
        "contract_version": record[3], "source_sha256": record[4],
        "evidence_sha256": record[5], "size_bytes": record[6],
        "table_count": record[7], "column_count": record[8],
        "foreign_key_count": record[9],
    }


def _identity(source_path: Path | str) -> str:
    source = Path(source_path).expanduser()
    if not source.is_absolute():
        _deny()
    return hashlib.sha256(str(source.resolve(strict=True)).encode("utf-8")).hexdigest()[:24]


def read_synthetic_registry(registry_path: Path | str, *, synthetic: bool = False) -> dict[str, object]:
    """Offline, read-only listing of pinned metadata. No source file is touched."""
    if synthetic is not True:
        _deny()
    try:
        registry = _absolute(registry_path, must_exist=True)
        with closing(_connect_existing(registry, writable=False)) as conn:
            conn.execute("PRAGMA query_only=ON")
            _require_layout(conn)
            rows = conn.execute("SELECT * FROM asset_records ORDER BY db_id LIMIT ?",
                                (MAX_ASSETS+1,)).fetchall()
            if len(rows) > MAX_ASSETS:
                _deny()
        return {"version": "hae.synthetic.asset-registry.v1",
                "asset_count": len(rows),
                "assets": [_receipt(row) for row in rows],
                "customer_ready": False, "release_gate": "HOLD"}
    except (OSError, sqlite3.Error, RuntimeError, ValueError, TypeError):
        _deny()


def register_synthetic_asset(
    registry_path: Path | str, source_path: Path | str, provider: DbvoraClient,
    *, synthetic: bool = False, acknowledge_owner: bool = False,
) -> dict[str, object]:
    """Explicitly record one already-attested owner asset, never silently rebind."""
    if synthetic is not True or acknowledge_owner is not True:
        _deny()
    try:
        registry = _absolute(registry_path, must_exist=True)
        # No source, business or runtime database can serve as this registry.
        source = Path(source_path).expanduser().resolve(strict=True)
        if registry.samefile(source):
            _deny()
        proof = attest_synthetic_dbvora_asset(source_path, provider, synthetic=True)
        db_id = _identity(source_path)
        record = (
            db_id, "sqlite", "dbvora", "p0-01.v1", proof["source_sha256"],
            proof["asset_evidence_sha256"], proof["source_size_bytes"],
            proof["table_count"], proof["column_count"], proof["foreign_key_count"],
        )
        with closing(_connect_existing(registry, writable=True)) as conn:
            _require_layout(conn)
            conn.execute("BEGIN IMMEDIATE")
            current = conn.execute("SELECT * FROM asset_records WHERE db_id=?",
                                   (db_id,)).fetchone()
            if current is None:
                if conn.execute("SELECT count(*) FROM asset_records").fetchone()[0] >= MAX_ASSETS:
                    _deny()
                conn.execute("INSERT INTO asset_records VALUES (?,?,?,?,?,?,?,?,?,?)", record)
                status = "REGISTERED"
            elif current == record:
                status = "ALREADY_REGISTERED"
            else:
                # Source has changed: user must create a new reviewed registry,
                # not overwrite an immutable approval receipt.
                _deny()
            conn.commit()
        return {"status": status, **_receipt(record),
                "customer_ready": False, "release_gate": "HOLD"}
    except (AssetAttestationError, SchemaInventoryError, OSError, sqlite3.Error,
            RuntimeError, ValueError, TypeError):
        _deny()


def verify_registered_synthetic_asset(
    registry_path: Path | str, source_path: Path | str, provider: DbvoraClient,
    *, synthetic: bool = False,
) -> dict[str, object]:
    """After restart, require the owner to supply path and re-prove the pinned file."""
    if synthetic is not True:
        _deny()
    try:
        before = read_synthetic_registry(registry_path, synthetic=True)
        db_id = _identity(source_path)
        approved = next((r for r in before["assets"] if r["db_id"] == db_id), None)
        if approved is None:
            _deny()
        local = inspect_offline_schema(source_path, synthetic=True)
        if local["source_sha256"] != approved["source_sha256"]:
            _deny()  # No outgoing request if source drift already known.
        proof = attest_synthetic_dbvora_asset(source_path, provider, synthetic=True)
        if (_receipt((
                db_id, "sqlite", "dbvora", "p0-01.v1", proof["source_sha256"],
                proof["asset_evidence_sha256"], proof["source_size_bytes"],
                proof["table_count"], proof["column_count"], proof["foreign_key_count"],
            )) != approved):
            _deny()
        after = read_synthetic_registry(registry_path, synthetic=True)
        if after != before:  # Registry changed while network was checked.
            _deny()
        return {"status": "PINNED_SOURCE_REVERIFIED", **approved,
                "source_unchanged": True, "provider_protocol_verified": True,
                "dbvora_process_identity_verified": False,
                "customer_ready": False, "release_gate": "HOLD"}
    except (AssetAttestationError, SchemaInventoryError, OSError, sqlite3.Error,
            RuntimeError, ValueError, TypeError):
        _deny()
