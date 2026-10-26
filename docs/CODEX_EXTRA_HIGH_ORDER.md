> **ACTIVE OVERRIDE — 2026-10-27 KST:** user shortened AX FLOW core for hackathon reuse to **3–5 days preferred (Oct31), 7-day review target (Nov02)**. The older 5-week dates in this file are superseded for the supported-scope reusable integration MVP. Execute `docs/SPRINT_7_DAY_HACKATHON.md` first. Full commercial gates and third-party permissions remain unchanged. No guaranteed completion claim.

# Codex GPT-6 Extra-High — REA_APP / AX FLOW implementation order
Issued 2026-10-27 KST by AX FLOW chief GPT-6. This is an **executable work brief**, not evidence that Codex has started.

## User-imposed schedule
- D1–D3: **working REA_APP MVP**, not weeks of speculative design.
- D4–D6: compare with frozen blueprint, perform permitted n8n architectural research, document independent functionality contracts.
- D7–D14: **new, independently written n8n-like local runner** (not a fork).
- D15–D35: AX FLOW natural-language UI/configuration/verified run and parallel DBVORA integration. Whole target 5 weeks; not all n8n capabilities or enterprise certification. See docs/FAST_TRACK_5_WEEK.md.

## Ownership and source boundary
Chief GPT-6 = scope, design, review, quality gates. Codex = focused implementation, tests, small bugfixes, evidence-driven reports. Work in hibi89/AX_FLOW private. Use REA_APP branch for tools/rea-app only; feature/axflow-mvp for apps/ax-flow; feature/dbvora-integration for AX FLOW-side adapter; integrate through develop after testing. DBVORA stays another repo and is not modified from this brief.

REA_APP studies only authorized/source-available apps and documentation. n8n is a **research example**; source/LICENSE restrictions must be assessed, and n8n code/assets/node implementations may not be pasted into the commercial AX FLOW engine. Independently specified behavior and clean implementation are required.

## First 72 hours — do this first
1. Read HANDOFF.md, STATUS.md, AGENTS.md, REQUIREMENTS.md, docs/TARGET_BLUEPRINT_V1.md, docs/FAST_TRACK_5_WEEK.md, docs/NEXT_TASK.md and actual branch content.
2. Implement read-only, bounded source walker CLI for explicit user-selected repository root under tools/rea-app. Default only files the user authorized; skip .git/node_modules, symlinks outside root, binaries, secrets, large files and dangerous file types. Do not execute inspected project code.
3. JS/TS imports/exports **must use an actual parser adapter** (TypeScript AST or Tree-sitter) rather than guessing complex imports using regex; Python AST optional. If adapter unavailable, fail with a clear coverage limitation. Pin/notice permissibly licensed dependencies.
4. Emit stable machine-readable dependency/entrypoint graph and a human summary; every observed relation cites path+line. Separate observed from inferred. Allow explicit output directory without mutating source tree.
5. Build synthetic fixtures for ESM CommonJS imports, multiline imports, external/dependency aliases, cyclic graph, binary/secret files, syntax errors, symbolic links, zero files, count/bytes caps. Run real CLI and unit tests and prove original fixture tree remains unchanged.
6. Update STATUS/HANDOFF with exact SHA, commands, PASS/FAIL/SKIP and blueprint gaps. First MVP acceptance = working source map + repeatable tests, NOT a universal reverse engineer.

## Days 4–6 — stop at sufficient research
Use permissible n8n documentation/source revisions to map trigger/step execution, workflow configuration, persistence, credential boundaries, retries and error handling for our first runner. Produce original abstract contracts and independent fixtures; flag uncertain behavior. Do not develop a modified/distributed n8n fork or allow unlimited research time. Record license constraints and evidence.

## Days 7–14 — build our own runner
Native versioned JSON Schema/IR; compiler validates trigger, step type, inputs, scopes, timeouts, retries, idempotency and side effects. Minimal operation registry: manual/interval trigger, condition, transform, restricted HTTP stub/GET, SQLite read/write. Transactional state/job/step ledger in runtime SQLite, **separate** synthetic business SQLite database. CLI operations test/run/status/resume; durable checkpoints, bounded retry, receipts and clear errors. No arbitrary AI-generated shell execution. Pass three end-to-end offline workflows and crash/duplicate/restart tests at Week 2 review.

## Weeks 3–5 — customer UX, DB management and release QA
W3: natural language or template + optional bounded files → validated IR → auto-filled supported settings, dry run, bounded AI failure diagnosis, minimal local browser UI.
W4: scoped OAuth/user-consent connector(s), supported Gmail/Sheets only after permission, DBVORA read-only inventory bridge based on actual DBVORA API. A nonexistent multi-asset endpoint must not be assumed.
W5: independent DBVORA verification / restore receipts on supported source with user's approval, Windows and local GUI end-to-end, failure recovery, comparative results. No universal app compatibility claim.

## Chief review / Codex reporting contract
Every atomic increment should include:
TASK; branch; before/after commit SHA; changed paths; executed commands; observed PASS/FAIL/SKIP; remaining gaps vs TARGET_BLUEPRINT_V1; risks/rollback; next atomic task; required owner actions.
Use repeatable synthetic data; never equate docs or mocks to real SaaS verification. Update STATUS/HANDOFF upon material changes; commit only verified work. Do not force-push or modify other products, customer files, secrets, paid cloud, privacy controls or deployment without authority.

Low-risk implementation choices are delegated. Architectural changes, new licenses and customer-facing external effects are escalated for review. Owner message "ㄱ" advances the next authorized small task.

**No background execution is initiated by this document.** The owner must invoke the actual Codex session/connected coding workflow.
