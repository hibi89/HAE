"""Owner-approved *synthetic-only* SQLite-to-DBVORA read-only asset attestation.

This is a bounded local source/metadata agreement check, not a persistent asset
registry, real customer approval, authentication, or backup/restore certification.
"""
from __future__ import annotations

from collections import Counter
import hashlib
from pathlib import Path

from .dbvora_client import DbvoraClient
from .schema_inventory import SchemaInventoryError, inspect_offline_schema


class AssetAttestationError(ValueError):
    """The selected local asset and the read-only provider do not agree."""


def _deny() -> None:
    # Do not echo local paths, SQL identifiers, provider responses or customer rows.
    raise AssetAttestationError("HAE synthetic DB asset attestation refused safely")


def _schema_shape(tables: list[dict[str, object]], *, local: bool) -> tuple:
    """Compare exact table/column/PK/declared-nullability and FK edges, not data rows."""
    table_shapes: list[tuple] = []
    for table in tables:
        if local:
            name = table["table"]
            columns = tuple(sorted(
                (col["name"], col["type"], not col["not_null_declared"], col["pk_position"])
                for col in table["columns"]
            ))
            edges = Counter(
                (fk["target_table"], fk["from"], fk["to"])
                for fk in table["foreign_keys"]
            )
        else:
            name = table["name"]
            columns = tuple(sorted(
                (col["name"], col["type"], col["nullable_declared"], col["pk_position"])
                for col in table["columns"]
            ))
            edges = Counter(
                (fk["to_table"], from_col, to_col)
                for fk in table["foreign_keys"]
                for from_col, to_col in zip(fk["from_columns"], fk["to_columns"])
            )
            if any(len(fk["from_columns"]) != len(fk["to_columns"])
                   for fk in table["foreign_keys"]):
                _deny()
        table_shapes.append((name, columns, tuple(sorted(edges.items(),
                                                       key=lambda item: str(item[0])))))
    return tuple(sorted(table_shapes, key=lambda item: str(item[0])))


def attest_synthetic_dbvora_asset(
    source_path: Path | str, provider: DbvoraClient, *, synthetic: bool = False,
) -> dict[str, object]:
    """Check one explicit *closed synthetic* SQLite file against loopback DBVORA.

    No user table rows, path, credentials or SQL are exported in the receipt.
    HAE does not open/create any local database except read-only inspection.
    The provider must already be configured on 127.0.0.1. No writes or retry.
    """
    if synthetic is not True or not isinstance(provider, DbvoraClient):
        _deny()
    try:
        # Reuse scanner's source integrity, read-only and sidecar/link refusal.
        local = inspect_offline_schema(source_path, synthetic=True, reveal_names=True)
        path = Path(source_path).expanduser().resolve(strict=True)
        stat_before = path.stat()
        provider_inventory = provider.fetch_inventory()
        if provider_inventory.get("available") is not True:
            _deny()
        expected_db_id = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:24]
        if (provider_inventory.get("contract_version") != "p0-01.v1"
                or provider_inventory.get("engine") != "sqlite"
                or provider_inventory.get("db_id") != expected_db_id
                or provider_inventory.get("size_bytes") != local["source_size_bytes"]
                or provider_inventory.get("size_scope") !=
                    "main_database_file_only_excludes_wal_and_shm"
                or _schema_shape(local["tables"], local=True) !=
                    _schema_shape(provider_inventory["tables"], local=False)):
            _deny()
        # The UI renders top-level relationship metadata independently.
        # Do not attest a provider that contradicts its table FK catalog.
        local_relationships = Counter(
            (table["table"], key["target_table"], key["from"], key["to"])
            for table in local["tables"] for key in table["foreign_keys"]
        )
        remote_relationships = Counter(
            (rel["from_table"], rel["to_table"], from_col, to_col)
            for rel in provider_inventory["relationships"]
            for from_col, to_col in zip(rel["from_columns"], rel["to_columns"])
        )
        if (any(len(rel["from_columns"]) != len(rel["to_columns"])
                for rel in provider_inventory["relationships"])
                or remote_relationships != local_relationships
                or provider_inventory.get("provenance", {}).get("size_bytes") !=
                    "measured_local_filesystem"
                or provider_inventory.get("provenance", {}).get("tables") !=
                    "measured_sqlite_catalog"
                or provider_inventory.get("provenance", {}).get("relationships") !=
                    "declared_sqlite_foreign_keys"):

            _deny()
        # A provider network call can race the source; re-check the owner path,
        # bytes and file identity after the full response was validated.
        checked = inspect_offline_schema(source_path, synthetic=True, reveal_names=False)
        stat_after = path.stat()
        if (checked["source_sha256"] != local["source_sha256"]
                or stat_before.st_dev != stat_after.st_dev
                or stat_before.st_ino != stat_after.st_ino
                or stat_before.st_size != stat_after.st_size
                or stat_before.st_mtime_ns != stat_after.st_mtime_ns
                or stat_before.st_ctime_ns != stat_after.st_ctime_ns):
            _deny()
        asset_proof = hashlib.sha256((
            "hae.synthetic.sqlite.asset.v1:" + expected_db_id + ":" + local["source_sha256"]
        ).encode("ascii")).hexdigest()
        return {
            "version": "hae.synthetic.asset.attestation.v1",
            "asset_evidence_sha256": asset_proof,
            "source_sha256": local["source_sha256"],
            "source_size_bytes": local["source_size_bytes"],
            "table_count": local["table_count"],
            "column_count": local["column_count"],
            "foreign_key_count": local["foreign_key_count"],
            "source_unchanged": True,
            "provider_protocol_verified": True,
            "dbvora_process_identity_verified": False,
            "customer_ready": False,
            "release_gate": "HOLD",
        }
    except (SchemaInventoryError, OSError, ValueError, KeyError, TypeError, OverflowError):
        _deny()
