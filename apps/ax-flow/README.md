# HAE — Humanized Automation Ecosystem (independently coded customer automation platform)

**Final product name:** HAE, formerly AX FLOW. Internal directory and package names stay as-is; Lightning Azent is the planned independently versioned engine.

Status: planning; no runnable code or customer UI.

**Core from first MVP:** validated JSON workflow IR, safe deterministic CLI executor, dedicated private runtime SQLite, separate test-business SQLite adapter, run receipts, idempotency/restart controls, evidence-based dry-run.

**Full product:** natural-language + attachment intake, auth wizard, verified test/repair, Gmail/Sheets adapters, GUI + **mandatory DBVORA integrated DB view** before full-package sign-off. The customer does not manually configure nodes or paste JSON.

Database scope: runtime SQLite stores workflow metadata only. Business data is stored in user-chosen SQLite or authorized external store. DBVORA provides a separate local read-only metadata/backup safety subsystem; adapter is planned under `apps/ax-flow/adapters/dbvora/` on `feature/dbvora-integration`. Refer to docs/DATA_ARCHITECTURE.md, MASTER_SCHEDULE.md and ACCEPTANCE_MATRIX.md. No modified n8n source included.
