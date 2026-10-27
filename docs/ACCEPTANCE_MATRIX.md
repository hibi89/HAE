# AX FLOW Definition of Done — evidence matrix

**Evidence status at 2026-10-27 KST.** All status is limited to recorded bounded synthetic tests. PASS does not imply customer, production, or cross-platform readiness. Blueprint estimate: A100/B95/C95/D95/E65 = **90% PARTIAL** (heuristic).

**Latest full AX FLOW regression (P40):** Windows Python 3.11.9, `python -m unittest discover -s tests -v` from `apps/ax-flow` — **71/71 PASS** in 35.200 s with authorized synthetic loopback. Engine-only suite 31/31 PASS; Node UI regression and syntax checks PASS.

**P33 package integration:** current-source Windows zipapp (32,191 bytes) served its bundled page/assets and read a synthetic SQLite catalog through exact DBVORA `feature/p0-db-map@31b8257468d28743fb2d3767d1caa56938df756c` source. FK metadata present, POST rejected, source unchanged, no data/path leakage. This improves D1/E evidence without claiming customer release.

**P35 normalization evidence:** explicit column transformations, normalized filtering/import, duplicate-row receipts, source-lineage preservation, pre-write failure safety and crash replay are covered by the 66-test suite; duplicates are retained and runtime receipts omit row values.

**P36 DBVORA capability check:** exact archive CLI source was hash-verified and run on a synthetic SQLite source on Windows. It safely returned `PUBLISH_FAILED` before publishing a snapshot; source SHA/size/mtime remained unchanged. No archive or restore completed, so D2 remains NOT_STARTED.

**P37 concurrency evidence:** the same-run cross-process test explicitly opts into the bounded SQLite retry budget and passes 20/20 stress repetitions; no default retry policy change.

**P38 package evidence:** the Windows zipapp CLI completed normalized filtering/import, duplicate reporting and source-row preservation. Source SHA/size/mtime were unchanged, runtime receipts were redacted, and the full 67-test suite passed.

**P39 typed conversion evidence:** bounded English/Korean number/string normalization was tested via API and zipapp; invalid numeric input fails before writes. The zipapp now propagates exit status 2 on failure; full suite 70/70 PASS.

**P40 numeric boundary evidence:** engine, API and packaged CLI accept exact safe integer/decimal/exponent values and reject blank, malformed, non-finite, overflow, underflow, unsafe integers and precision-losing decimals. Invalid inputs preserve source files and produce no business rows; full suite 71/71 PASS.

**P41 Windows diagnosis:** the exact DBVORA staged-file read-only-fsync operation was reproduced locally as errno 9; read/write-fsync passed. A separate disposable SQLite online backup/restore round trip passed with the source unchanged. This is diagnostic evidence only: no product restore passed and D2 remains NOT_STARTED.

| ID | Component | Required proof | Current |
|---|---|---|---|
| R1 | REA_APP synthetic source analyzer | real parser/import/graph + bounds + no source mutation tests | PASS — bounded synthetic JS/TS; Python 11/11, Node parser PASS, deterministic fixture and self-scan |
| R2 | Permitted n8n study | evidence-linked functional spec, reviewed license/contracts, no transplanted n8n code | PASS — official behavior and license references recorded; no n8n code/assets copied |
| F1 | Typed workflow IR | independently validated versioned schema, invalid/injection inputs fail closed | PASS — bounded synthetic IR validation/rejection and CLI workflows exercised |
| F2 | Runtime SQLite + executor | deterministic CLI, durable journal, restart recovery, migrations/backup tests | PARTIAL — deterministic ledger, migrations, retries and crash/replay tested; backup/restore acceptance absent |
| F3 | Business-data handling | user-selected SQLite read/write with integrity, no conflation with runtime DB | PASS — synthetic CSV→business SQLite flow, separate runtime DB, explicit write approval, integrity/idempotency checks |
| F4 | AI & attachments | natural language → runnable plan, files parsed locally, bounded repair/dry-run, no manual nodes/JSON | PARTIAL — bounded full/filtered/conditional/lookup CSV flows plus an explicit single-column normalization/import path and duplicate report tested; visible browser flow verified previously; bounded number/string column conversion, exact numeric-boundary checks and invalid-value rejection added; no general AI, arbitrary attachments or bounded AI repair |
| F5 | Connectors/auth | real user OAuth consent (no bypass), scoped Gmail send / Sheets calls with explicit approval | NOT_STARTED — requires owner consent and real credentials |
| D1 | DBVORA integration | supported SQLite read-only catalog → UI schema/relations/size/provenance; API offline handling; no raw data leakage | PARTIAL — P24 visible synthetic schema/PK/FK/size verified against exact source; P27–P28 provenance allowlist, unavailable state and offline clearing verified; P31 packaged stub online/offline verified; P32 source-app adapter and P33 current Windows zipapp both read exact DBVORA feature/p0-db-map API, showing FK metadata and omitting data/path; customer/multi-asset and customer-installed service remain unverified |
| D2 | Data backup/restore | independently restored source, same content and source unchanged, corruption/restart safety on supported platform | NOT_STARTED — no successful independently verified restore. P36 Windows synthetic snapshot returned `PUBLISH_FAILED` before publication; P41 reproduced the staged-file read-only-fsync failure as errno 9 on Windows; source was unchanged and no restore was attempted |
| F6 | Customer dashboard | local browser with authenticated controls, permissions, status, errors, no manual node selection | PARTIAL — synthetic local browser controls/receipts/errors verified; customer authentication absent |
| F7 | Security/reliability | file/OAuth/token secrecy, prompt injection, outbound limits, idempotency, fault injection, least privilege, dependency audit | PARTIAL — local boundary/redaction/idempotency and fault paths tested; configured cross-process same-run replay passed a 20-run stress; no independent review, live OAuth validation or complete security gate |
| F8 | Install/customer release | native Windows/NTFS + UI/CLI + network + repeatable packaged install, three real-world-shaped workflows | PARTIAL — stdlib zipapp API smoke, P30 packaged browser workflow, P31 packaged provenance stub, and P33 packaged actual DBVORA API integration and P38 packaged normalization/import and P39 packaged failure-exit and P40 numeric-boundary verification passed; signed installer, customer installation, three real-world-shaped workflows and release evidence remain open |
| B1 | Commercial model | scoped customer pilot feedback/support time, legal/license review; price is a hypothesis | NOT_STARTED — no scoped pilot or commercial validation |

**Platform-specific unverified items:** an unprivileged Windows file-symlink fixture was skipped because Path.symlink_to returned OSError [WinError 1314]. A directory-junction fixture was also skipped because PowerShell New-Item -ItemType Junction returned Access is denied. Neither workflow ran and neither result is a pass. Do not elevate to claim either acceptance.

**Full AX FLOW + DBVORA product completion requires F1–F8 and D1–D2, not merely R1 or F2.** External SaaS provider features only within granted API permissions. Each API/DB feature must declare tested supported versions; do not call a limited SQLite-only result universal multi-DB support.

## Release states
- MVP_INTERNAL: **PARTIAL** because F2 backup/restore acceptance remains open.
- PILOT_CANDIDATE: **NOT READY**; F4/F5/F6/F7 and remaining operational evidence are incomplete.
- CUSTOMER_READY: **NOT READY**; D2, security, signed Windows distribution, customer evidence and commercial criteria remain open.
