# Roadmap (gated, not a completed release)

See [MASTER_SCHEDULE.md](MASTER_SCHEDULE.md) for detailed calendar, engineering-hours estimates, dependencies, contingency and completion gates.

| Gate | Outcome | Main work track |
|---|---|---|
| R0 (done docs only) | private repository, role boundaries, initial docs/branches | main |
| R1 | REA_APP static source analyzer and synthetic corpus tests | REA_APP |
| R2 | n8n permissible functionality mapping and independent specifications | REA_APP |
| F1 | AX FLOW typed IR, deterministic CLI runner, separate state SQLite and business data SQLite | feature/axflow-mvp |
| F2 | natural language / template / local file intake, automatic setup and verified dry-run | feature/axflow-mvp |
| F3 | OAuth broker, Gmail send / Sheets adapters with explicit permissions | feature/axflow-mvp |
| D1 | DBVORA metadata-only bridge, graph view, version/health, backup/restore verification (supported DB) | feature/dbvora-integration |
| F4 | local customer dashboard without node assembly and approval wizard | feature/axflow-mvp |
| F5 | security, crash recovery, benchmarks, Windows package and E2E | develop |
| F6 | customer-style pilots, support-cost evidence, commercial/license/privacy sign-off | develop → main |

**Full product cannot be called complete until D1 + F5 pass**, even if automation engine and AI work. REA_APP is a development tool and DBVORA remains its own repository. Earlier single-workflow runner success is a partial milestone only.

Proposed assisted implementation price 590,000 KRW remains a hypothesis; no purchases or willingness-to-pay proof. External OAuth verification and third-party approvals may extend schedule without a reliable fixed date.
