# AX FLOW Definition of Done — evidence matrix

**Evidence status at 2026-10-27 KST.** Status reflects tests actually run on the recorded bounded synthetic environment. “PASS” does not imply customer, production, or cross-platform readiness.

**Latest complete AX FLOW regression:** Windows Python 3.11.9, from apps/ax-flow, python -m unittest discover -s tests -v — 60/60 PASS with loopback permission. Restricted-sandbox attempt had 9 failures / 10 errors from WinError 10013 plus one transient SQLite busy-cap failure that did not recur; see P25 in STATUS/HANDOFF.

| ID | Component | Required proof | Current |
|---|---|---|---|
| R1 | REA_APP synthetic source analyzer | real parser/import/graph + bounds + no source mutation tests | PASS — bounded synthetic JS/TS; Python 11/11, Node parser PASS, deterministic fixture and self-scan |
| R2 | Permitted n8n study | evidence-linked functional spec, reviewed license/contracts, no transplanted n8n code | PASS — official behavior and license references recorded; no n8n code/assets copied |
| F1 | Typed workflow IR | independently validated versioned schema, invalid/injection inputs fail closed | PASS — bounded synthetic IR validation/rejection and CLI workflows exercised |
| F2 | Runtime SQLite + executor | deterministic CLI, durable journal, restart recovery, migrations/backup tests | PARTIAL — deterministic ledger, migrations, retries and crash/replay tested; backup/restore acceptance absent |
| F3 | Business-data handling | user-selected SQLite read/write with integrity, no conflation with runtime DB | PASS — synthetic CSV→business SQLite flow, separate runtime DB, explicit write approval, integrity/idempotency checks |
| F4 | AI & attachments | natural language → runnable plan, files parsed locally, bounded repair/dry-run, no manual nodes/JSON | PARTIAL — four bounded CSV intents and fail-closed UI tested; no general AI, arbitrary attachments or bounded AI repair |
| F5 | Connectors/auth | real user OAuth consent (no bypass), scoped Gmail send / Sheets calls with explicit approval | NOT_STARTED — requires owner consent and real credentials |
| D1 | DBVORA integration | supported SQLite read-only catalog → UI schema/relations/size/provenance; API offline handling; no raw data leakage | PARTIAL — connected/offline states and visible schema/PK/FK/size, refresh and redaction verified on selected synthetic SQLite with pinned local API; customer/multi-asset/packaged provenance not verified |
| D2 | Data backup/restore | independently restored source, same content and source unchanged, corruption/restart safety on supported platform | NOT_STARTED — separately owner-approval gated; no restore was performed |
| F6 | Customer dashboard | local browser with authenticated controls, permissions, status, errors, no manual node selection | PARTIAL — synthetic local browser controls/receipts/errors verified; customer authentication absent |
| F7 | Security/reliability | file/OAuth/token secrecy, prompt injection, outbound limits, idempotency, fault injection, least privilege, dependency audit | PARTIAL — local boundary/redaction/idempotency and fault paths tested; no independent review, live OAuth validation or complete security gate |
| F8 | Install/customer release | native Windows/NTFS + UI/CLI + network + repeatable packaged install, three real-world-shaped workflows | PARTIAL — stdlib zipapp and synthetic local CLI/UI smoke; no signed installer or customer installation/release evidence |
| B1 | Commercial model | scoped customer pilot feedback/support time, legal/license review; price is a hypothesis | NOT_STARTED — no scoped pilot or commercial validation |

**Platform-specific unverified items:** an unprivileged Windows file-symlink fixture was skipped because Path.symlink_to returned OSError [WinError 1314]. A directory-junction fixture was also skipped because PowerShell New-Item -ItemType Junction returned Access is denied. Neither workflow ran and neither result is a pass. Do not elevate to claim either acceptance.

**Full AX FLOW + DBVORA product completion requires F1–F8 and D1–D2, not merely R1 or F2.** External SaaS provider features only within granted API permissions. Each API/DB feature must declare tested supported versions; do not call a limited SQLite-only result universal multi-DB support.

## Release states
- MVP_INTERNAL: **PARTIAL** because F2 backup/restore acceptance remains open.
- PILOT_CANDIDATE: **NOT READY**; F4/F5/F6/F7 and remaining operational evidence are incomplete.
- CUSTOMER_READY: **NOT READY**; D2, security, signed Windows distribution, customer evidence and commercial criteria remain open.
