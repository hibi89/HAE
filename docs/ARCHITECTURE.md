# Architecture options and preliminary ADR

## A. Modular Python core + local CLI + optional localhost web UI (RECOMMENDED for MVP)
Planner interface (AI optional) → validated workflow spec → policy/consent engine → deterministic executor → SQLite durable job ledger → connector adapters → result receipts. Independent secret broker uses OS secure store. DBVORA integration uses a scoped local contract if implemented. REA_APP keeps separate parser/index/graph/report modules.

**Performance/cost:** stdlib Python+SQLite can run locally at zero service cost for small/medium workflows; startup/UI smaller than full workflow suites. Performance gains over n8n are unverified. Memory limits/timeouts and job concurrency should be measured.
**Maintenance:** small core and narrow adapter contracts; gradual expansion. Weakness: custom integrations and scheduling/recovery require engineering/testing.

## B. Open-source Node-RED / Activepieces core + our AI front end
Existing flow editor/executor and connectors speed up breadth; license obligations/third-party notices must be reviewed per exact revision (Node-RED Apache 2.0; Activepieces core MIT with separately licensed components). Larger runtime/dependencies, upstream compatibility burden and UI complexity.
**Tradeoff:** potentially quickest prototype for supported connectors; greater upgrade/licensing surface.

## C. n8n fork or n8n-based customer platform (NOT RECOMMENDED)
Fast reuse but modified n8n commercial offering and AI-based customer-facing builder can require commercial license; contract, trademark and copyright restrictions. Not the default distributable implementation.

### Decision proposal
Choose A for **local deterministic runtime and own UX**; optionally use permitted individual OSS libraries/connectors, not a wholesale n8n derivative. Record acceptance in ADR before substantive code. Avoid equating CLI with faster workflows; benchmark workflow authoring time, CPU/memory, run latency, error recovery and user interventions.

## Logical module boundaries
```
AX FLOW UI/CLI ──> Planner (natural language or templates)
                         │ validated typed workflow IR
                         v
                    Policy & Consent
                         │ approved execution intent
                         v
                Local Deterministic Runner
                ├─ durable SQLite job/event ledger
                ├─ scheduling, locks, idempotency and replay checks
                ├─ adapter registry (only selected adapters load)
                ├─ secrets broker (OS store / least privilege)
                └─ result evidence + safe error reports
                         │ optional metadata-only contract
                         v
                   DBVORA [external repo]

REA_APP source-inventory/parser/graph/report [separate tool]
```

## Failure modes and constraints
- Untrusted document text and agent tool output may contain prompt injection.
- Filesystem operations need path bounds, sandboxing and explicit authorization; never run raw unrestricted AI shell plans.
- Outbound email can be accepted by remote provider before response lost; remote message-ID reconciliation, bounded retries and an ambiguous state are necessary. "Exactly once" not guaranteed globally.
- Cron locally executes only while host is powered/on; offline catch-up policy explicit.
- OAuth scopes and external AI upload require informed consent and separate user approvals.
- No silent public network listener, webhook port forwarding, telemetry or elevated privileges.
- Cost governance: optional hosted LLM/provider usage has separate pay limits and explicit opt-in.
