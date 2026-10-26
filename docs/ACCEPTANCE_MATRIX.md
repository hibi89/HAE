# AX FLOW Definition of Done — evidence matrix

**Statuses at 2026-10-27 KST: all product tests NOT RUN.** Docs-only GitHub validation does not count as customer/functional test. Mark verified only on exact commit, command, environment and result.

| ID | Component | Required proof | Current |
|---|---|---|---|
| R1 | REA_APP synthetic source analyzer | real parser/import/graph + bounds + no source mutation tests | NOT_STARTED |
| R2 | Permitted n8n study | evidence-linked functional spec, reviewed license/contracts, no transplanted n8n code | NOT_STARTED |
| F1 | Typed workflow IR | independently validated versioned schema, invalid/injection inputs fail closed | NOT_STARTED |
| F2 | Runtime SQLite + executor | deterministic CLI, durable journal, restart recovery, migrations/backup tests | NOT_STARTED |
| F3 | Business-data handling | user-selected SQLite read/write with integrity, no conflation with runtime DB | NOT_STARTED |
| F4 | AI & attachments | natural language → runnable plan, files parsed locally, bounded repair/dry-run, no manual nodes/JSON | NOT_STARTED |
| F5 | Connectors/auth | real user OAuth consent (no bypass), scoped Gmail send / Sheets calls with explicit approval | NOT_STARTED |
| D1 | DBVORA integration | real supported SQLite read-only catalog → UI schema/relations/size/provenance; API offline handling; no raw data leakage | NOT_STARTED |
| D2 | Data backup/restore | independently restored source, same content and source unchanged, corruption/restart safety on supported platform | NOT_STARTED |
| F6 | Customer dashboard | local browser with authenticated controls, permissions, status, errors, no manual node selection | NOT_STARTED |
| F7 | Security/reliability | file/OAuth/token secrecy, prompt injection, outbound limits, idempotency, fault injection, least privilege, dependency audit | NOT_STARTED |
| F8 | Install/customer release | native Windows/NTFS + UI/CLI + network + repeatable packaged install, three real-world-shaped workflows | NOT_STARTED |
| B1 | Commercial model | scoped customer pilot feedback/support time, legal/license review; price is a hypothesis | NOT_STARTED |

**Full AX FLOW + DBVORA product completion requires F1–F8 and D1–D2, not merely R1 or F2.** External SaaS provider features only within granted API permissions. Each API/DB feature must declare tested supported versions; do not call a limited SQLite-only result universal multi-DB support.

## Release states
- `MVP_INTERNAL`: R1/R2 research and F1/F2/F3 synthetic CLI only; no auth/customer data.
- `PILOT_CANDIDATE`: F4/F5/F6 plus read-only D1 on synthetic verified, secure local auth, bounded automation.
- `CUSTOMER_READY`: all feature gates incl. Windows, D2, and safety/commercial criteria pass. Any untested step = PARTIAL/NOT_READY.
