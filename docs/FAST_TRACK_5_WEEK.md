> **ACTIVE OVERRIDE — 2026-10-27 KST:** user shortened AX FLOW core for hackathon reuse to **3–5 days preferred (Oct31), 7-day review target (Nov02)**. The older 5-week dates in this file are superseded for the supported-scope reusable integration MVP. Execute `docs/SPRINT_7_DAY_HACKATHON.md` first. Full commercial gates and third-party permissions remain unchanged. No guaranteed completion claim.

# AX FLOW — 5-week accelerated delivery baseline v2
Decision: 2026-10-27 KST. **This file supersedes the older 21-week master schedule.**

## User's required sequence and time box

- **Weeks 1–2 (Oct 27–Nov 9):** REA_APP usable for the selected research target **and** an **independently authored n8n-like execution-engine v0**. Here “n8n 개조” is shorthand for studying supported functionality and building **our own new code**, not shipping a fork or pasting n8n source.
- **Weeks 3–5 (Nov 10–Nov 30):** Build AX FLOW user-facing natural-language workflow authoring, automatic integration/configuration/testing, and run the **DBVORA integration track in parallel**, finishing with full supported-path integration tests.
- Hard cap is a **planning goal**, not demonstrated feasibility. “Completed” means the **scope-limited v1 acceptance matrix below**, not all n8n nodes/connectors, all source languages, certified enterprise security, every database, or all possible Windows installations.
- The three 2026 hackathon deadlines (KIC Nov 12 10:00 KST, PayPal Nov 13 05:00 KST, UGREEN Nov 16 16:45 KST) coincide with Weeks 3–4; their submissions and human-account/third-party gating take precedence when needed. Record actual blocked days and make up missed work; do not claim calendar deadlines were met without evidence.

## MVP-first operating rule
Every stage uses: **2–3-day working slice → compare with the frozen TARGET_BLUEPRINT → implement highest-impact gaps → tests/evidence → next slice**. Security/permissions/anti-corruption baseline is included from Day 1; deeper hardening, environment compatibility, packaging and commercialization are later gates. Do NOT knowingly delay minimum safety checks or claim unsafe builds are customer-ready.

| Window | Date KST | REA_APP / engine / product outcomes | DoD (must have executed tests) |
|---|---|---|---|
| D1–D3 / first MVP | Oct 27–29 | Read-only bounded REA_APP CLI: directory + package inventory, JS/TS import-export mapping via lawful parser, Python AST optional, graph JSON + text report, synthetic fixtures | CLI actually runs, deterministic outputs, no source modification, bounds/symlink/secret exclusions tested |
| D4–D6 | Oct 30–Nov 1 | Compare MVP with target blueprint; permitted n8n functionality/trigger/nodes/DB/status model research and **clean independent contracts**; improve REA_APP entrypoint/data-path mapping | References to permissible docs/source revision and evidence; no third-party source copy; unobserved relationships marked inferred |
| D7–D10 | Nov 2–5 | Build independent runner v0: versioned JSON IR, validation, manual/interval trigger, safe step registry, local SQLite job/event ledger and data adapter | 1 synthetic end-to-end workflow; invalid spec rejected; checkpoint restart and duplicate-work tests |
| D11–D14 | Nov 6–9 | Add branch/transform/HTTP stub, retries/timeout/rate guard, dry-run, CLI logs/result receipts; adjust against original blueprint | 3 workflows reproducible; crash/restart/retry tests, source unchanged. **Week 2 engine v0 gate** |
| W3 | Nov 10–16 | AX FLOW natural-language/template → typed IR, automatic supported config, bounded error diagnosis/repair; minimum local GUI with clear auth placeholders; preserve hackathon deadlines | AI output never executed before schema/risk validation; supported test cases build/test through GUI; hacks not disrupted |
| W4 | Nov 17–23 | Connect scoped Google OAuth and one actual read/write connector as allowed; CSV/Sheets/Gmail progressive; **parallel DBVORA adapter and metadata panel on approved SQLite fixture** | User consent, secret redaction, dry-run vs live distinctions; schema inventory matches fixture; offline DBVORA fails visibly |
| W5 | Nov 24–30 | DBVORA integrated run, data-view and verified source-preserving restore receipts if independent DBVORA gate allows; UI & Windows E2E, basic security/restart/perf benchmark, packaging and synthetic customer trial | Supported demo: language → generated IR → local DB write → DBVORA inventory → result/retry audit; plus separate authorized Google flow if available. Independent restore Windows evidence mandatory for **full DB suite** release, otherwise PARTIAL. |

## Critical path & division of work
1. Chief architect **GPT-6** owns scope, frozen blueprint, contracts, acceptance, review of architectural drift and independent verification.
2. **Codex GPT-6 Extra-High** implements narrow assigned slices on correct branch, tests, commits, checks remote SHA, updates the handoff. It must not redesign whole product or manufacture test results.
3. REA_APP code under `tools/rea-app/` on `REA_APP`. Original AX FLOW runner under `apps/ax-flow/` on `feature/axflow-mvp`. DBVORA integration adapter on `feature/dbvora-integration`. Integration via `develop` and verified `main`; separate `hibi89/DBVORA` code owner/release unaffected.
4. DBVORA currently has SQLite read-only inventory and backup work on independent feature branch, **not** a verified generalized or Windows/customer release. In W4–5 use exactly available contract or request approved versioned extension; do not claim a nonexistent multi-asset endpoint.
5. No work on user/customer database, PayPal, Gmail, OAuth setup, paid calls, public ports, deployment or production without applicable approval and validated test account.
6. Avoid extra features while high-priority gates are red. Compare plan against implemented evidence daily; stop on build/test safety regressions.

## Scope-limited v1 acceptance
- **REA_APP:** deterministic authorized JS/TS monorepo source inventory, package and import graph, selected function/entrypoint references with file+line evidence; repeatable offline sample; no executes, secrets or nonconsensual source collection.
- **Independent runner:** from-scratch code, canonical JSON IR with validation, minimal manual/interval triggers, conditions/transform/HTTP stub/SQLite adapter, durable checkpoints and receipts, re-run protection.
- **AX FLOW:** natural-language input and recommended templates map to supported IR. AI automates input/configuration/testing of those connectors; only permissions/financial/destructive actions seek user approval. A simple local browser GUI runs a supported workflow without user editing JSON or nodes.
- **DBVORA:** AX FLOW runtime SQLite distinct from business SQLite; licensed/approved read-only DBVORA bridge shows supported DB tables/columns/FKs/provenance and handles unavailable state; independently verified restore to another path only if full DBVORA gate passes.
- **Evidence:** exact source SHA, commands, test pass/fail/skip, simulated vs real API, environment (Windows and Linux), safety/cost, three reproducible demonstrations, known gaps and next tasks. No “100%” without completing applicable gates.

## What can move past Week 5 without pretending success?
Full n8n feature parity, arbitrary plugin marketplace, multi-tenant hosted cloud, all providers/databases, automated migration/destruction, enterprise security certification, universal compatibility and customer SLA. These form separately estimated commercialization backlog and must never be silently folded into the 5-week promise.

## Status at creation
This schedule is a **new plan**. No REA_APP analyzer, own runner, real OAuth, GUI or DBVORA integration source/tests were completed merely by writing it. The previous 21-week plan is preserved in Git history; this v2 takes priority going forward.
