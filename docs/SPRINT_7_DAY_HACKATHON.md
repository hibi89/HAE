# AX FLOW — 7-day hackathon-reusable integration sprint (2026-10-27 KST)

**ACTIVE USER TARGET supersedes the 5-week planning calendar for the *supported-scope integration MVP*.** Work fast, do not broaden the architecture.

- **Preferred functional MVP date:** Sat **2026-10-31** (D5, 3–5 calendar-day objective from Oct 27).
- **Maximum requested verification window:** Mon **2026-11-02** (D7).
- **Scope:** a working, independently coded, local automation engine with natural-language *supported template* intake, configuration, safe test/execute, a real SQLite business data sink and a genuine/limited DBVORA SQLite map; portable enough to assist KIC/PayPal/UGREEN teams without making them dependent on an immature engine.
- **Not within a 7-day guarantee:** full n8n feature parity, arbitrary SaaS OAuth/Google integrations, enterprise security certification, fully unsupervised AI plugin generation, complete DBVORA commercial backup/recovery for all OS/providers, customer onboarding/sales. Those are future product hardening backlog, not silently considered done.

## Critical path / exact outputs

| Day / KST | Focus | Acceptance gate (do not confuse adding files with PASS) |
|---|---|---|
| D1 Tue 10/27 | Reuse verified REA_APP 0.3.0 bounded JS/TS core; advance AX FLOW typed JSON IR + separate runtime/business SQLite; CLI status/resume | Real local synthetic CLI execution, safe replay, test/commit SHA; user rights/secret guard |
| D2 Wed 10/28 | Conditions, pure transform/mapping, explicit step budgets; resumption and concurrency/idempotency risk tests | 3 distinct synthetic workflows pass with actual results and no duplicate DB write |
| D3 Thu 10/29 | Real CSV fixture → validated transform → SQLite write/read, data provenance and approval; reproducible install | Run from fresh local directory; source files intact; invalid/malicious inputs rejected |
| D4 Fri 10/30 | **Constrained natural-language/templates → native IR → auto configure/test**; light local GUI or browser-facing API | User writes/selects a supported task, gets validated plan + dry-run; no manual JSON/node setup |
| D5 Sat 10/31 | DBVORA local approved SQLite metadata adapter + customer-visible DB map, demo sequence; simple result dashboard | Real DBVORA read-only service fixture/contract or explicitly verified local API, table/column/FK provenance, meaningful offline handling; connected end-to-end demo |
| D6 Sun 11/01 | Windows clean-environment, security/failure cases, no-secret checks, CLI/GUI packaging proof | Recorded SHA+environment+test commands; source protection; repeatable demo |
| D7 Mon 11/02 | Reserve for failures, hackathon adapter examples and handoff | Three reproducible demos; KIC/PayPal/UGREEN boundary review; red gates marked PARTIAL, no forged completion |

## Minimum workable hackathon demonstrations
1. **KIC, internal/finals only:** synthetic or authorized financial CSV/claim → typed validation → local evidence/report ledger. KIC preliminary is PDF-only and does not require this runtime.
2. **PayPal, optional narrow support only:** bounded AI quote approval and payment event ledger **without automatic capture/financial operation**. Existing PayPal repository remains source of truth; real Sandbox order/approval/capture and human permission remain mandatory to claim integration.
3. **UGREEN, developer-side tool only:** local file inventory, required-document/delta report, risk review. Round 1 ZIP has Markdown Skill only; do **not** bundle this executable or alter frozen compliant submission package.

## Architectural constraints
- **REA_APP** independent research tool; n8n lawful functional reference, never forked/copied to the customer engine.
- **AX FLOW engine** original source; versioned native JSON IR; Python local deterministic runner; runtime SQLite separate from business SQLite; explicit approval for writes and external side effects; synthetic safe default.
- **DBVORA** independent owner/repository. Latest available interface is read-only one-selected-SQLite `/api/inventory` + `/health`, not a universal multi-source management API. Do not assume full Windows backup/restore quality; test actual supported source before a completion claim.
- Start from real code, not more speculative docs. Chief GPT-6 designs/validates; Codex codes assigned bounded scopes (avoid both agents editing same branch/files simultaneously).
- Freeze a **supported path** before opening broad new features. Fast sprint cannot excuse secret leakage, unauthorized network actions, or destructive database operations.

## Current observed checkpoint 2026-10-27
REA_APP bounded synthetic 0.3.0 completed on REA_APP branch (Codex-reported 10/10 Python + Node parser tests, independent user-facing software not yet verified at real source). AX FLOW first engine slice on feature/axflow-mvp had local 5/5 synthetic tests; added independent read-only runlog and CLI status/resume, runlog isolated tests 2/2 PASS and CLI status smoke PASS. Full combined regression on updated GitHub HEAD **PENDING**. Natural-language GUI/DBVORA adapter/provider auth **NOT_STARTED**.

## Decision rule on 2026-11-02
If supported vertical flow passes Windows/browser/DBVORA/read-only and restart tests, mark **HACKATHON_CORE_READY** with exact supported capabilities and a pinned revision. If missing any mandatory DB/GUI/recovery gate, mark **PARTIAL**, list test failures and blockers, and ship only independently validated library slices to hackathon leads. Do not misstate a 7-day target as a guaranteed complete commercial product.
