# AX FLOW ↔ DBVORA — data architecture and integration contract (design v0)

**Status: proposed interface, NOT deployed.** AX FLOW and DBVORA are distinct private products/repositories. AX FLOW product completeness requires verified DBVORA integration for *supported* databases; early engine-only MVP has its own SQLite and can run before the integration gate.

## Why not one merged database engine?
DBVORA is not a replacement for SQLite/PostgreSQL. It inventories schema/size/provenance and evolves safe snapshot/backup/archive and restore. AX FLOW owns actual workflow execution and data connectors. Merging code would entangle destructive recovery permissions with outward-facing workflow integrations; separate local processes provide independent rollback, limited privileges and deployments. Additional localhost IPC complexity is worth it for a customer product.

## Three databases/data planes
1. **AX FLOW runtime state DB (required)** — local SQLite stored under OS application-data directory, durable workflow spec versions, executions, step states, input references, approvals, schedule metadata, retries, external receipt IDs, schema migrations; no OAuth secrets or raw incoming mail by default.
2. **Business data connector plane (required)** — user-approved sources/sinks: SQLite P0, Google Sheets and PostgreSQL progressively. Different logical/physical DB from runtime state. A send-Gmail action may generate no additional business DB rows; provider retains message, local ledger holds only minimal status/provider ID. Cloud Sheets remains its own data authority.
3. **DBVORA management plane (mandatory for final bundled-product release)** — read-only inventory, evidence-based map, table/column/FK/index details, measured size/source where supported; optional explicit backup/restore and archive, with source protected and independent restore proof.

## Proposed AX FLOW asset metadata contract v0
```json
{
  "contract_version": "axflow.data.v0",
  "asset_id": "nonsecret-stable-id",
  "provider": "sqlite",
  "kind": "relational_database",
  "owner_scope": "user_approved",
  "capabilities": ["read_metadata", "read_data", "write_data"],
  "schema_observed_at": null,
  "metrics": {"size_bytes": null, "provenance": "unavailable"},
  "dbvora": {"linked": false, "health": "not_configured", "inventory_version": null}
}
```
Capability list varies by provider and permissions. `read_metadata` is not raw row access. Asset ID maps to secrets/paths only in a local protected broker.

## Proposed DBVORA read-only v1 adapter
- Precondition: user registers/approves a local SQLite file via DBVORA trusted UI, not an unauthenticated HTTP request.
- Health/version: existing DBVORA endpoint `GET /health`, but **version negotiation extension is not yet implemented**.
- Inventory: current DBVORA `GET /api/inventory` returns metadata about one selected SQLite source. Generalized `GET /v1/assets/{id}/inventory`, multiple assets and authenticated inter-process channel are **future contract endpoints**, not existing APIs.
- Response mapping: DB ID, source type, observed_at, measured size with scope, tables, columns, PK/FK/index relationship evidence. Unavailable fields represented as `null` / unavailable, not guesses.
- Failure: DBVORA absent/unsupported/locked/offline → explicit `management_unavailable`; AX FLOW may continue approved tasks using its own data adapter, but cannot display a fictitious successful DB management check or claim the full product ready.
- Local IPC: first prototype loopback-bound endpoint + local token in OS credential manager + narrow peer allowlist; prefer named pipe/Unix socket if appropriate after benchmark and threat model. Even localhost endpoints require origin/host/CSRF protections.
- No arbitrary SQL, raw table dumps, credentials, migration or DBVORA archive delete exposed through AI or this read-only bridge.

## Safe backup/restore gate
Any backup/restore is a DBVORA-owned explicit action with its own approval, consistency snapshot, checksum verification, immutable original, separate restore destination and corruption/power failure checks. First integrate **status and receipts only**; do not expose backup triggers until full Windows/NTFS and regression gates pass. Neither compression ratio nor production readiness is established today.

## Provider limitations
Gmail: mail lives at Google. Google Sheets: scoped worksheet/tab metadata and values API, not Google's physical DB. Supabase/Postgres: SQL schema queries only with credentials and explicit permissions, not automatic access to provider internals. Never imply unsupported cloud backup or CPU-by-database file measurement.

## Current evidence (2026-10-27 KST)
Read from independent private `hibi89/DBVORA` `feature/p0-db-map`: `dbvora/api.py` read-only localhost one-file inventory API, `dbvora/inventory.py` SQLite schema metadata. Feature HANDOFF/STATUS record targeted synthetic tests and **210 test definitions** in latest revision, but not full 210 latest-head PASS, Windows/NTFS/customer-ready. No working AX FLOW ↔ DBVORA adapter exists. DBVORA repository/source unmodified in this design task.

## Contract acceptance tests
Schema mapping accuracy, source SHA/mtime unchanged, attack inputs rejected, secret/path redaction, readonly DB selection, DBVORA unavailable / older version behavior, duplicate/retry state, 2 schema snapshots, local API security, restore to independent path if enabled, full DBVORA acceptance gate on appropriate OS.
