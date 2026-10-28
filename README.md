# HAE — Humanized Automation Ecosystem

**Final customer-facing product name: HAE (Humanized Automation Ecosystem).** Former name: AX FLOW. Internal `axflow` package, `apps/ax-flow/` path, `feature/axflow-mvp` branch, and `hibi89/AX_FLOW` repository remain compatibility identifiers, not product branding.

**Status:** This shared README is a planning entry point. Synthetic REA_APP and automation prototypes exist on their dedicated branches; OAuth, full DBVORA restoration and customer release remain unverified.

## What we are building
A user chooses a suggested task or writes a natural-language instruction, adds optional documents, approves first-party credentials and high-risk actions, and receives a **configured, tested, runnable** local automation. The user never needs to edit workflow JSON/nodes. AI plans and diagnoses; a permission-checked deterministic engine configures, runs, validates and recovers.

**Database capability is part of the definition of a complete HAE product**, not an optional afterthought:
- Always include a local SQLite **runtime ledger** for workflows, events, checkpoints and receipts (no raw secrets).
- Provide business-data adapters for local SQLite and later PostgreSQL/Google Sheets as scoped sources/sinks. No mandatory user business DB for tasks such as sending email.
- **DBVORA is a required integration for the complete bundled product** (supported schema visibility, asset map, metrics provenance, verified safe backup/recovery where supported). DBVORA stays an independent repository/process; its presence is not required for earliest engine-only technical MVP.
- External SaaS (Gmail, Google Sheets etc.) remains the data authority; do not replicate whole mailboxes or promise the cloud provider's physical DB internals.

## Separate tools / products
- `tools/rea-app/` — REA_APP: source architecture, dependency and behavior analysis for lawful independent engineering; development tool, not automation runtime.
- `apps/ax-flow/` — HAE: standalone automation + data product; not a modified n8n distribution.
- `hibi89/DBVORA` — distinct private database visibility, optimization, recovery and archiving tool. Only approved, versioned local interface integration; no code copying by default.
- SMAX²/SOVIA are separate optional future interoperability targets.

## Development stages
REA_APP core → permitted n8n functionality/architecture study → independent Lightning Azent execution engine + SQLite → AI/file workflows + OAuth → DBVORA data-management UI integration → browser/Windows/security, recovery, customer pilots.

Master engineering plan: [docs/MASTER_SCHEDULE.md](docs/MASTER_SCHEDULE.md). Database architecture: [docs/DATA_ARCHITECTURE.md](docs/DATA_ARCHITECTURE.md). Validation: [docs/ACCEPTANCE_MATRIX.md](docs/ACCEPTANCE_MATRIX.md).

## Branches
`main` stable docs/verified integrations; `develop` review/integration; `REA_APP` internal source analyzer; `feature/axflow-mvp` runtime; `feature/dbvora-integration` HAE-side DBVORA adapter/contract (branch creation is separately verified). Branch names identify work tracks; code must live in stable folders, not only branches.

## Handoff
Read `HANDOFF.md` → `STATUS.md` → `AGENTS.md` → `REQUIREMENTS.md` → `docs/NEXT_TASK.md` → actual source. `ㄱ` means continue with next safe work unit. No paid service, credentials, public deployment, customer data or third-party uploads without explicit approval.

## ACTIVE 5-week schedule (owner correction 2026-10-27 KST)
**REA_APP + independently written n8n-like runner in first 2 weeks, then HAE customer front-end + parallel DBVORA integration and real supported-path test in next 3 weeks.** First working MVP in 2–3 days, followed by blueprint gap closure then broad hardening. **n8n is research reference only, not the source of HAE runtime code.** See docs/FAST_TRACK_5_WEEK.md, docs/TARGET_BLUEPRINT_V1.md and docs/CODEX_EXTRA_HIGH_ORDER.md; prior 21-week plan is historical.

## CURRENT SPRINT OVERRIDE — 2026-10-27 KST
**3–5-day preferred HAE hackathon-reusable supported-scope MVP (Oct31), max 7-day release review goal (Nov02)**. Active plan: [docs/SPRINT_7_DAY_HACKATHON.md](docs/SPRINT_7_DAY_HACKATHON.md). Previous five-week calendar is historical. This is not full commercial product completion; actual SHA-bound integration and security tests determine what can be reused. REA_APP and DBVORA remain independent tools.
# Windows local quick start

On Windows with Python 3.11 or newer installed, double-click `HAE-Start.cmd`. It starts the existing HAE app on loopback, waits until the page responds, and opens the default browser. The console stays open while HAE runs; closing it stops the local server. No administrator rights, installer, account, or external service is used. The default data directory is `%LOCALAPPDATA%\HAE`; set `HAE_DATA_DIR` to choose another location or `HAE_PORT` to select a different local port. The launcher prefers a compatible Lightning Azent package available in the checkout and otherwise uses HAE's existing local engine; set `HAE_BACKEND=lightning-azent` to require LA and fail closed if it is unavailable.
