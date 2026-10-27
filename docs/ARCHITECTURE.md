# Architecture Decision: HAE platform, independent Lightning Azent runtime + separate DBVORA

**Name and architecture clarification (2026-10-27):** HAE is the final customer product name (formerly AX FLOW). The original Python `axflow` runtime is a reference implementation to be progressively extracted into independent **Lightning Azent**, while the HAE UI/AI layer consumes it. Historical decisions and test obligations remain valid; no migration has happened yet.

## Alternatives
| Criterion | A. Merge DBVORA code and automation into one executable | B. Separate local DBVORA process + versioned API (SELECTED) | C. Embed modified n8n as execution service |
|---|---|---|---|
| Engineering setup | simpler initially | adapter and lifecycle setup needed | quick node reuse |
| Maintenance | DB recovery changes risk workflow regressions | independent releases/rollback, bounded contracts | upstream drift and licensing obligations |
| Runtime overhead | one process | second service only when DB management enabled | larger service stack |
| Cash cost | local zero possible | local zero possible | commercial licensing may be required |
| Data safety | mixed write and backup privileges | allowlist/read-only boundary | modified engine security review |
| Product independence | weak | strong | weak / sales risk |

**Decision:** B for final product: HAE owns workflow state and actual data adapters; DBVORA owns observation, catalog, verified backups and restores. HAE can operate on a single local SQLite data destination without a running DBVORA **during early MVP**; release claiming the **full HAE + DB suite** requires passing DBVORA integration acceptance.

## HAE layers
```
Customer (natural language, template, files) → planner / typed JSON IR
   → validator + risk policy + approval
   → connector/secret broker → deterministic local runner
   ├── private runtime SQLite (jobs, workflow versions, run receipts)
   ├── business data adapters (SQLite first, Sheets/Postgres as authorized)
   └── data asset registry + DBVORA adapter → localhost read-only DBVORA API
                                             └── source databases (no raw data export)
```
REA_APP is external R&D source analysis and cannot execute customer jobs.

## Data protection and execution
- Runtime SQLite and business SQLite have **different paths, schemas and privileges**. Never make DBVORA's own metadata catalog the only state store for HAE.
- The registry stores stable source IDs, type, provider, scope, time/provenance, latest available inventory status; credentials remain in the OS secret store.
- DBVORA's currently available `dbvora/api.py` exposes one user-selected SQLite file read-only (`/api/inventory` and `/health`); a generic multi-asset / versioned service contract and trusted enrollment mechanism are **not implemented**.
- First adapter can use a pre-approved selected local SQLite database; report DBVORA unavailable explicitly. Do not silently fall back to fabricated metrics.
- Any backup/restore command belongs to an **independent, explicitly approved, fail-closed DBVORA workflow**; no general-purpose raw SQL executor or source delete API across the bridge.
- External Google Sheets is **API-observable tabular storage**, not a promise to administer Google's physical storage or backups. Gmail retains email messages on Google's servers; runtime SQLite records minimal provider IDs and receipts.
- Use localhost only, authenticated app-to-app channel, origin checks, limited file/path access, least privilege. Secrets never enter AI prompt or GitHub.
- Benchmark CLI vs n8n on identical workloads; neither CPU, memory, speed nor compression improvements are assumed.

## Compiler/executor contract
AI produces **typed, canonical, versioned JSON IR**, not executable raw shell script. Validator checks node references, connector capability schema, scopes, path policy, data mappings, resource budgets, retries/timeouts, and side effects. Compiler binds adapters and dry-run checks; runner performs only approved operations with receipts and crash-safe checkpoint ledger. Unknown node types are rejected or treated as plugin development tasks.

## Open questions before implementation
Exact DBVORA adapter API version, OS secret broker, Windows process lifecycle, whether embedded GUI uses FastAPI + static assets/Tauri, local AI vs cloud budget. Default local and zero service cost until approved; require regression tests at every integration gate.
