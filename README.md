# AX FLOW — AI-first Automation + Data Platform

**Current:** private planning/architecture only. No functioning REA_APP analyzer, automation engine, DB integration, OAuth or customer release yet.

## What we are building
A user chooses a suggested task or writes a natural-language instruction, adds optional documents, approves first-party credentials and high-risk actions, and receives a **configured, tested, runnable** local automation. The user never needs to edit workflow JSON/nodes. AI plans and diagnoses; a permission-checked deterministic engine configures, runs, validates and recovers.

**Database capability is part of the definition of a complete AX FLOW product**, not an optional afterthought:
- Always include a local SQLite **runtime ledger** for workflows, events, checkpoints and receipts (no raw secrets).
- Provide business-data adapters for local SQLite and later PostgreSQL/Google Sheets as scoped sources/sinks. No mandatory user business DB for tasks such as sending email.
- **DBVORA is a required integration for the complete bundled product** (supported schema visibility, asset map, metrics provenance, verified safe backup/recovery where supported). DBVORA stays an independent repository/process; its presence is not required for earliest engine-only technical MVP.
- External SaaS (Gmail, Google Sheets etc.) remains the data authority; do not replicate whole mailboxes or promise the cloud provider's physical DB internals.

## Separate tools / products
- `tools/rea-app/` — REA_APP: source architecture, dependency and behavior analysis for lawful independent engineering; development tool, not automation runtime.
- `apps/ax-flow/` — AX FLOW: standalone automation + data product; not a modified n8n distribution.
- `hibi89/DBVORA` — distinct private database visibility, optimization, recovery and archiving tool. Only approved, versioned local interface integration; no code copying by default.
- SMAX²/SOVIA are separate optional future interoperability targets.

## Development stages
REA_APP core → permitted n8n functionality/architecture study → independent AX FLOW execution engine + SQLite → AI/file workflows + OAuth → DBVORA data-management UI integration → browser/Windows/security, recovery, customer pilots.

Master engineering plan: [docs/MASTER_SCHEDULE.md](docs/MASTER_SCHEDULE.md). Database architecture: [docs/DATA_ARCHITECTURE.md](docs/DATA_ARCHITECTURE.md). Validation: [docs/ACCEPTANCE_MATRIX.md](docs/ACCEPTANCE_MATRIX.md).

## Branches
`main` stable docs/verified integrations; `develop` review/integration; `REA_APP` internal source analyzer; `feature/axflow-mvp` runtime; `feature/dbvora-integration` AX FLOW-side DBVORA adapter/contract (branch creation is separately verified). Branch names identify work tracks; code must live in stable folders, not only branches.

## Handoff
Read `HANDOFF.md` → `STATUS.md` → `AGENTS.md` → `REQUIREMENTS.md` → `docs/NEXT_TASK.md` → actual source. `ㄱ` means continue with next safe work unit. No paid service, credentials, public deployment, customer data or third-party uploads without explicit approval.

## ACTIVE 5-week schedule (owner correction 2026-10-27 KST)
**REA_APP + independently written n8n-like runner in first 2 weeks, then AX FLOW customer front-end + parallel DBVORA integration and real supported-path test in next 3 weeks.** First working MVP in 2–3 days, followed by blueprint gap closure then broad hardening. **n8n is research reference only, not the source of AX FLOW runtime code.** See docs/FAST_TRACK_5_WEEK.md, docs/TARGET_BLUEPRINT_V1.md and docs/CODEX_EXTRA_HIGH_ORDER.md; prior 21-week plan is historical.
