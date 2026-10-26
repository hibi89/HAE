# TARGET BLUEPRINT V1 — product architecture frozen for accelerated build
2026-10-27 KST. Status: **TARGET**, not built. Do not rewrite this blueprint to hide implementation gaps. Requirement changes must be recorded in DECISIONS.md and review.

## REA_APP (independent R&D tool)
Input: explicitly authorized local source root / legal source snapshot. Output: bounded read-only repository inventory, parser-accurate JS/TS dependency graph with package boundaries and path+line evidence, entrypoint and call/data-flow evidence at supported precision, deterministic JSON graph and Markdown report. Scope-limited support identified per language. Optional AI only explains indexed evidence (never fabricates source). Can compare module architecture and export **independent functional contracts** for our own implementations. Exclusions: executing target code, harvesting secrets, copying licensed n8n source into customer code, universal binary source recovery.

## n8n-informed OWN executor — AX FLOW core
Input: canonical typed JSON IR, native schema version; compiler/validator validates edge references, connectors, scopes, budgets, retry/approval/idempotency. Runtime: manual/interval trigger, supported steps, branch/data flow, local SQLite durable job, step and receipt ledger, resumable execution, transaction boundaries and outcome state machine, safely observable logs, CLI independent of AI and GUI. Unknown nodes rejected; not an n8n fork. Runtime internal SQLite is distinct from business data SQLite.

## AX FLOW customer front end
Customer enters a task or chooses recommended automation / supplies supported local files. AI returns an inspectable plan, asks for minimal missing information, configures approved adapters and parameter mappings itself, requests user actions only for OAuth permissions, destructive/financial/external side effects, and runs fixtures/dry run before live operations. UI hides nodes/JSON by default; user sees required permissions, statuses, receipts, error cause and proposed repair. AI repair bounded and tested; no unrestricted command execution.

## Data plane and DBVORA
AX FLOW first-class business data adapters (SQLite baseline; provider-limited Google Sheets etc.) plus required runtime DB. DBVORA is independent process/repo for read-only database schema/FK/column/size/provenance map, optional separately approved verified snapshot/restore. AX FLOW adapter has local scoped versioned contract, explicit unavailable state, no privilege escalation, no raw customer DB copying to AI/GitHub.

## Measurable acceptance (supported scope, not all integrations)
A. REA_APP can scan at least one synthetic JS/TS fixture repo and report proven import/entrypoint edges by exact path/line, repeat deterministically, bound resources and never mutate original source.
B. Fresh independent runner can load its own typed IR, perform three fixture workflows incl. SQLite write/read and branch, restart without duplicate side effects, emit receipts and tests.
C. AX FLOW natural-language customer GUI can generate and auto-configure at least one supported workflow and test/execute without manual JSON/node setup; unsupported requests fail clearly.
D. DBVORA accepted fixture SQLite map shows real tables/columns/FKs and measured size/source; linked browser view works; offline link displays unavailable; restore only claimed after independently verified source-preserving replay.
E. Permission/privacy/fail-safe checks, safe local Windows deployment and end-to-end demonstration with logs, exact SHA and test counts. Any unmet required release gate = partial product.

## Scope not implied by 5-week plan
Full n8n parity, hundreds of integrations, arbitrary source-language reconstruction, cloud fleet orchestration, unsupervised production outbound operations, hardware power-loss guarantees, guaranteed pricing/sales, multi-tenant SaaS, audit certifications.

## Build priority
1. Functional slice with tests within 72h; 2. compare actual outputs to A–E; 3. fill highest-value gaps; 4. security/compatibility/packaging and monetization after baseline safety; 5. measure and decide go/no-go. Chief approves blueprint changes; Codex implements bounded slices.
