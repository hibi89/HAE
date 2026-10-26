# AX FLOW

**AI-first Local Automation Platform** — Private, pre-implementation planning repository.

## Goal
A customer describes a task in natural language or picks a template, optionally attaches files, grants only necessary permissions, and receives an actually tested, deployable local automation. An independent runtime handles schedules, durable state, retries and recovery; AI assists with planning and diagnosis, not unrestricted execution.

## Two products, one private repository (initial operating model)
- **AX FLOW** (`apps/ax-flow/`): customer-facing automation product, currently unimplemented.
- **REA_APP** (`tools/rea-app/`): source analysis and independent architecture/specification tool, currently unimplemented. It is **not** the orchestration runtime.
- **DBVORA**: separate private repository and standalone optional data governance/inventory/archive tool; connect only via documented APIs and explicit consent.
- **SMAX² / SOVIA**: separate products; optional future interoperability, no dependency assumed.

## Branch rules
- `main` — stable documentation/integrated verified code; avoid direct feature experiments.
- `develop` — integration (PR/review gate).
- `REA_APP` — user-requested REA_APP research and build branch; put related files under `tools/rea-app/`.
- `feature/axflow-mvp` — initial AX FLOW implementation; put code under `apps/ax-flow/`.
Treat branches as temporary work tracks, **not separate products forever**; maintain separate directories so code can be merged later.

## First milestones
1. REA_APP: local repository tree, language inventory, call/import dependency map, structured source report on an authorized/public fixture, with repeatable tests.
2. AX FLOW: local CLI runner on a synthetic workflow (schedule/event → transform → SQLite/file → receipt), without external API credentials.
3. Natural-language spec-to-workflow from a schema-constrained plan; dry run, approvals, import of local CSV, then least-privilege OAuth connectors.
4. Local optional web UI, customer verification, and paid service validation only after explicit approval.

Read in this order: **HANDOFF.md → STATUS.md → AGENTS.md → REQUIREMENTS.md → docs/ARCHITECTURE.md → docs/NEXT_TASK.md → actual source.**

**No real product implementation, tests, deployment or customer verification completed at bootstrap.** Do not put secrets, customer content, proprietary n8n code or private datasets in GitHub.
