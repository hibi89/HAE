# LIGHTNING AZENT — independent automation engine / phased development master plan
Status: OWNER NAME APPROVED, ARCHITECTURE PLAN; NOT YET A BUILT OR SEPARATELY RELEASED PRODUCT.
Decision date: 2026-10-27 KST. Owner wording: **Lightning Azent**; "Azent" is a coined brand suggesting autonomous work **A to Z**. Brand vision is not a claim of full capability, speed supremacy, or agent autonomy.

## 1. Non-negotiable development order
**REA_APP evidence → n8n functionality analysis & independent contracts → LIGHTNING AZENT reusable engine → AX FLOW end-user platform.**
- REA_APP = authorized read-only reverse engineering/source-evidence tool, kept separate, not a dependency of normal production workflow execution.
- LIGHTNING AZENT = wholly independently written local-first engine/runtime with validated workflow IR, operation/connector registry, explicit policies, durable state, retries/approvals, observability and versioned contracts.
- AX FLOW = task intake, AI/constrained planner, templates, auto-configuration, local GUI, user auth/approval, provider secret/OAuth broker, supported provider UX and read-only DBVORA map integration. It **uses** Lightning Azent as its execution backend; it is not the engine's other name.
- DBVORA remains independent database observability/backup/restore product. Independent source restore is not provided by Azent's runtime-ledger backup.
- The existing `apps/ax-flow/axflow/engine.py`, `scheduler.py`, `state_backup.py`, `runlog.py` are a **synthetic-only prototype / reference implementation** and possible extraction donors. They are NOT proof of a completed Lightning Azent or of n8n-derived architecture. Do not delete/rewrite without compatibility tests.

## 2. Why separate an engine, rather than just rename AX FLOW?
Option A: rename current AX FLOW Python package to Azent immediately. Lower initial effort, but breaks imports/CLI and erases distinction between platform and engine. REJECT.
Option B: keep current tested source intact, define a versioned engine port and migrate implementation in small backwards-compatible slices into `packages/lightning-azent/` (initial monorepo directory, **not created yet**). More up-front tests/adapter work, but minimal user-visible breakage, independent reuse, easy rollback. SELECTED for implementation review.
Option C: rewrite n8n as a derivative or use it as the embedded runner. Fast feature access but third-party terms, independence and maintenance risks; not the selected product.
Python stdlib + SQLite remains the MVP default (zero extra service costs, reuse already implemented paths). TypeScript/Node may be used for an isolated connector or adapter if concrete evidence warrants it; avoid unapproved framework pivot.

## 3. Gates and outputs — strictly sequential acceptance, not just elapsed days

### Gate R — REA_APP verified and evidence suitable for research
Baseline currently visible: `REA_APP` branch `tools/rea-app/rea_app/__init__.py` says v0.3.0; current README describes pinned Babel JS/TS parser, bounded scanning, import/export, entrypoints, partial call/data-flow and change impact, with explicit coverage limitations. Prior tests reported, but no fresh execution proof from this planning session.
Tasks:
1. Freeze exact REA_APP branch commit, actual dependency notices/licenses and command versions; run `cd tools/rea-app && python -m unittest discover -s tests -v && npm run test:parser` in a connected authorized checkout.
2. Verify synthetic JS/TS graphs, package boundaries, path/line citations, deterministic output, read-only source integrity, input caps and redaction; record OS, versions, test counts and SKIPs. No blanket 100% reverse engineering claim.
3. Create a bounded **authorized** n8n source/document reference set: exact official URL/tag/commit, observed behavior and coverage. Check current permission/license first. The analyzer runs read-only; no real credentials or client source.
Exit: reproducible real REA_APP tests + sample evidence artifact + coverage and licensing constraints signed off by chief. If no checkout/test executor, mark BLOCKED/UNVERIFIED rather than bypass.

### Gate N — lawful n8n behavior research → independent contracts
Do not directly transplant n8n code. Prefer n8n official documentation and public interfaces; use permitted source only within verified terms.
Research ONLY priority behaviors needed for the first engine, not all n8n nodes:
1. Workflow graph, typed node inputs/outputs, deterministic ordering, branch/merge and item lineage.
2. Manual/interval triggers and scoped execution scheduling.
3. Execution lifecycle, durable steps, failed/completed/waiting states, retry/replay and fault semantics.
4. Input mapping, expressions and sandbox/security boundaries.
5. Connector interface, resource budgets, idempotency and external side-effect approvals.
6. Credentials/OAuth boundary and redaction (design contracts only; no real tokens).
Per finding record evidence source/revision/path+line or official docs anchor, OBSERVED vs INFERRED distinction, abstract input/output/state/error contract, competitor behavior not worth copying, and an **original** synthetic conformance test.
Exit: `docs/lightning-azent/RESEARCH_TO_CONTRACTS.md` (future planned artifact) with at least three fully specified offline workflows, a risk register, explicit legal/coverage limits, and chief-approved v0.1 behavior spec. No source-code translation from n8n; reimplement from contracts.

### Gate L — independent LIGHTNING AZENT library, CLI and release contract
Target monorepo location **after Gate N**: `packages/lightning-azent/`, package `lightning_azent` (proposal; no new repo/branch created by this plan). Preferred feature branch `feature/lightning-azent` after approval, separate from ongoing AX FLOW commits.
Module boundaries:
- `ir/schema`: `azent.ir.v0` or explicitly negotiated upgrade from `axflow.ir.v0`; versioned schema/validation, strict unknown-step rejection, edge and limits.
- `planner contract`: accepts **validated declarative IR only**; no model-specific user prompt dependence.
- `executor + scheduler`: deterministic, bounded run, step policy, manual/interval, data lineage and structured receipts.
- `adapters`: explicit capability/consent contract, local CSV/SQLite first; no arbitrary shell or network unless allowlisted and approved.
- `state`: internal SQLite distinct from business SQLite, durable journal/checkpoints/recovery, safe no-overwrite backup.
- `policy`: validation, required approval for side effects, bounded retries/timeouts, idempotency limitations for remote actions.
- `sdk/api`: stable `validate(plan)`, `preview/dry_run(plan, fixtures)`, `execute(plan, approval)`, `status(run_id)`, `resume(run_id)`, and `capabilities()` contracts (names are design proposals, not existing implemented APIs).
Migration: (1) preserve old AX FLOW HEAD and tests; (2) add exact baseline parity tests; (3) extract non-UI runner primitives and keep temporary compatibility import facade in `axflow`; (4) update CLI to invoke Azent while preserving existing flags/receipt shape; (5) only remove duplicate engine paths when parity is verified. `planner.py`, `web.py`, `static/`, `dbvora_client.py` remain AX FLOW-owned.
Exit: three distinct **real offline** workflows on fixtures (manual CSV→SQLite, condition/branch, interval+recovery), restart/crash replay with no duplicate *local* writes, status/receipts redacted, independent CLI and package invocation, no raw external operations, exact Windows test SHA/commands/counts, backward-compatible AX FLOW subset tests. Do NOT claim exactly-once for external APIs.

### Gate A — AX FLOW integration on top of Lightning Azent
AX FLOW's app layer translates constrained prompts/templates to native Azent IR, automatically fills safe local parameters, uses **read-only file-level preflight** before user write approval, explains plan/risks, sends approved plan to Azent and renders receipts/errors. Adapter + version negotiation must reject unsupported Azent schema.
Integrate DBVORA through its separately approved existing read-only localhost API, **not** by copying DBVORA DB code into Azent. Keep provider OAuth/secret management in a permissioned app/broker and pass only opaque scoped handles to the engine (when implemented). Financial/email/external writes require explicit approval; no silent remote calls.
Exit: browser E2E for a supported synthetic workflow with plan, actual fixture preflight, approval, run, restart status, real DBVORA metadata and offline status; all existing AX FLOW tests green on the new engine. Do not call this general-purpose autonomous agent functionality.

### Gate C — customer product and commercial release (separate gate)
Broader connectors/OAuth, independent DBVORA source restore, bounded AI repair, original malware/prompt-injection review, Windows clean-install/signed or characterized build, privacy/security audit, approved pilot workflows and terms/price validation. Prior synthetic percentages are **not** customer-readiness progress.

## 4. The current AX FLOW work already done — avoid double work
Current `feature/axflow-mvp` historical P49 HEAD at planning start `9e8831b9755f803d39595338af7a4873968d91a9`. Inspect code/tests and preserve useful implementations: typed `axflow.ir.v0`, CSV normalization/filter, SQLite state/business separation, status/resume, interval scheduling, package smoke, bounded local UI and DBVORA read-only client. F4 general AI, real OAuth/F5, D2 source restore, customer auth/F6, full security/F7, customer release/F8 remain incomplete.
`docs/BLUEPRINT_CODE_AUDIT_2026-10-27.md` describes P49 gaps, including preview not being a real input dry-run, upload 512 KiB vs reader 256 KiB. Those must not be forgotten during Azent migration. P48/P49 actual full-suite regression **NOT RUN** in available environment; previous tests on older SHAs are historical evidence only.
**Freeze AX FLOW core feature expansion during Gates R/N/L, not the user-facing source or hackathon pinned demos.** Permit only critical safety fixes to the frozen app and existing independent hackathon deliverables if separately approved.

## 5. Integration contract / who owns what
Data path: **AX FLOW intent/UI → local planner → Azent native IR validation/preflight → explicit approval → Azent deterministic runner → status/receipts → AX FLOW dashboard**.
- REA_APP: produces research facts and independent feature contracts; **never** a runtime dependency or execution-of-third-party-code service.
- Azent: executes validated, versioned plans and enforces side-effect policy. Does not own customer-facing LLM chat, OAuth consent page, GUI, or DBVORA source recovery.
- AX FLOW: customer-friendly orchestration, UX, secret/consent broker, optional AI repair (only bounded verified later), business adapter configuration and DBVORA metadata panel.
- DBVORA: independently maintained database inventory/backup/restore per its own safety gates.
All components declare supported versions, schemas, provenance and failure states. Failed compatibility negotiation **fails closed**, no implicit fallback to a different engine.

## 6. Phasing, branch hygiene, delivery policy
- Current official task order replaces previous parallel-first implementation **for new feature work**. The old 7-day sprint (`docs/SPRINT_7_DAY_HACKATHON.md`, Oct31 preferred / Nov02 review) remains **historical, limited-scope hackathon target**, not proof the new three-stage full product can be finished on that schedule. Any previously pinned reusable demo must be treated as standalone evidence and protected from migration.
- Keep `REA_APP` branch for analyzer only. Do not modify it without dedicated review. Keep existing AX FLOW code in `feature/axflow-mvp` stable until migration. Future independent engine package/feature branch requires separate controlled creation; no repo/folder yet.
- Chief handles research scope, contract sign-off, accepted gates and design review. Codex, if explicitly assigned, handles bounded implementation/test chunks. Never allow both agents to modify the same branch/file simultaneously.
- Every change: actual base SHA, changed paths, test commands/outputs and versions, boundary failures, audit of original blueprint vs current, next task and rollback. Update STATUS/HANDOFF. Do not force push.
- Budget: zero-cost/local by default. No paid CI, new cloud, external auth, public service, customer data, n8n source redistribution, destructive DB operation or new repository without explicit owner approval.

## 7. Immediate next action
1. Verify exact current `REA_APP` branch SHA and rerun baseline tests on an authorized executable checkout. While unavailable, inspect only code/test completeness and record run blocker, not fabricated PASS.
2. List six feature contracts required for Lightning Azent v0.1, with official documented provenance and three original synthetic fixtures; no n8n code copying.
3. Audit/mark reusable AX FLOW engine files under `docs/BLUEPRINT_CODE_AUDIT_2026-10-27.md` before extracting anything.
4. Chief signs the v0.1 library/API+data-boundary design; then extract small slices and run full compatibility regression.
5. Reconnect AX FLOW only after Gate L passes.

Final deliverable is independent Lightning Azent functioning without AX FLOW UI or REA_APP installed, with AX FLOW consuming it through a stable boundary. "A to Z" is a design vision, not the first release's promised capability.
