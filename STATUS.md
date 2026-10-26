# STATUS — 2026-10-27 KST

## Verified by GitHub at start of bootstrap
- Repository `hibi89/AX_FLOW`: **Private** (renamed from user-created REA_APP), default branch `main`, read/write admin available.
- Initial state was **empty repository**, zero branches, zero product code. Bootstrap README initialized main commit `8d528821097fcf6b983e52d9de804613cd8d8c3d`.
- Documentation/bootstrap tree and branch creation should be checked from actual GitHub before calling them complete.

## Product readiness
| Component | State | Evidence |
| --- | --- | --- |
| REA_APP static source analyzer | MVP_VERIFIED (PARTIAL) | `23bbc979657ccb25bcbba5ddfe2c647476dc0051`, gap slice `52c7860b67dd6dc991c46141b2e841bde74d858f`; 8 Python tests + Node parser assertions pass |
| AX FLOW local runtime | NOT_STARTED | no code/tests |
| Natural-language planner and file input | NOT_STARTED | no code/tests |
| OAuth, Gmail/Sheets connectors | NOT_STARTED | no account credentials, no auth test |
| DBVORA integration | NOT_STARTED | separate repository remains unchanged |
| Recovery, resilience and performance | NOT_STARTED | no observed benchmarks |
| Windows install, customer tests, security assessment | NOT_STARTED | no releases |
| Vercel/Production | NOT_APPLICABLE | local-first product, no hosted service |

## Next
Use the bounded n8n notes and remaining REA_APP blueprint gaps in `docs/NEXT_TASK.md` for chief review. Keep the independent AX FLOW runner/engine on hold until that review. Update exact SHAs/test evidence after writes.

## Bootstrap verified after GitHub writes (2026-10-27 KST)
- GitHub repository visibility independently rechecked: **private**.
- Branches independently rechecked: `main`, `develop`, `REA_APP`, `feature/axflow-mvp`.
- Initial organized documentation tree commit: `28271b5b8df6241d4a6be3a1e404b93d41379bb2`; fetched GitHub commit shows **14 changed files**; author and committer both connected `hibi89`.
- Remote file fetches succeeded from each target branch: main/HANDOFF.md; develop/docs/ARCHITECTURE.md; REA_APP/tools/rea-app/README.md; feature/axflow-mvp/apps/ax-flow/README.md.
- Documentation only, **0 source tests and 0 deployments**. All feature branches were created off the same documentation baseline; docs-only HEAD alignment is performed separately after status/handoff changes.

## 2026-10-27 KST — user-approved DB-required scope and schedule (latest policy)
- **Scope decision:** Full AX FLOW now requires business-data capability + verified DBVORA integration; early internal CLI MVP may operate on its own runtime/business SQLite before DBVORA service is ready. REA_APP independent; n8n research only, no copied fork in customer product.
- **Docs authored:** REQ/ARCH/ROADMAP/NEXT_TASK/DECISIONS/REPOSITORY_LAYOUT, docs/DATA_ARCHITECTURE.md, docs/ACCEPTANCE_MATRIX.md, docs/MASTER_SCHEDULE.md, README and HANDOFF updates. Verify committed actual tree/SHA at end.
- **Branches:** main/develop/REA_APP/feature/axflow-mvp verified at start; user requested new feature/dbvora-integration branch for AX FLOW-side adapter, creation and alignment are separate verification operations.
- **DBVORA inspected:** independent private hibi89/DBVORA feature/p0-db-map has a one-selected-SQLite read-only schema API, archive-related source and test evidence; latest recorded 210 test definitions, not a current full-suite PASS. Windows/customer installation remains unverified. DBVORA repository unchanged.
- **Schedule:** 21-week planning baseline, 445–750 focused hours, target review 2027-03-22 if continuous, possible +2–6-week risk buffer; not an estimated uptime, quote or guaranteed finish.
- **Implementation/tests:** only planning and GitHub configuration; 0 application tests / 0 live workflows / 0 DB adapter tests / 0 customer installs. Vercel/Production N/A; release UNVERIFIED.
- **Next:** source-safe REA_APP R1 design and synthetic MVP on REA_APP branch following docs/NEXT_TASK.md. No permission to use real customer DB, paid API, public hosting, OAuth account/app or mutate DBVORA.

## 2026-10-27 — LATEST SCHEDULE DECISION (supersedes 21-week estimate)
- **New target: 5 weeks total**: REA_APP + lawful n8n reference study + independently written basic runner in Weeks 1–2 (Oct27–Nov09); AX FLOW AI/GUI/auth with DBVORA adapter/independent DBVORA readiness concurrently in Weeks 3–5 (Nov10–Nov30).
- User workflow: **2–3 day executable MVP → freeze/compare original blueprint → gap repair → security/Windows/commercial hardening**, not upfront months of elaborate architecture.
- New docs: docs/FAST_TRACK_5_WEEK.md, docs/TARGET_BLUEPRINT_V1.md, docs/CODEX_EXTRA_HIGH_ORDER.md. docs/MASTER_SCHEDULE.md, docs/NEXT_TASK.md, docs/ROADMAP.md replaced with v2 active schedule. GitHub commits/refs need final live verification.
- **Code/tests:** no implementation authorized as completed by documentation. REA_APP, runner, GUI, OAuth, DBVORA integration remain NOT_STARTED as of planning. No Codex autonomous execution initiated.
- Schedule caveat: three hackathon submissions fall in Week 3; calendar target is stretch only. Existing DBVORA still separately owned and independently gated.
- Next action: Codex first 72-hour synthetic JS/TS analyzer MVP on REA_APP branch, actual tests and SHA recorded.

## 2026-10-27 KST — REA_APP MVP verified
- Branch/base verified: `REA_APP`, base `dc4b572f638892bd09f65698ec0768588974a887`; implementation commit `23bbc979657ccb25bcbba5ddfe2c647476dc0051`. The implementation is committed through the connected GitHub API because local `git clone` could not resolve `github.com` and local `.git/index.lock` is read-only in this sandbox.
- Implemented under `tools/rea-app/`: bounded read-only walker, pinned `@babel/parser` 7.29.9 AST adapter, package/entrypoint inventory, ESM/CommonJS import/export graph, `tsconfig` path aliases, syntactic call references, deterministic JSON and Markdown reports.
- Verification: `python -m unittest discover -s tools/rea-app/tests -v` — **8 passed, 0 failed**; `npm --prefix tools/rea-app run test:parser` — **PASS**. Tests ran against synthetic repositories and installed `@babel/parser` 7.29.9 from the host's global Node module tree. No target source was executed or changed.
- Safety coverage: explicit source and output paths; output must be outside source; default caps 5,000 files / 1 MB per file / 20 MB total; secret-name, binary, generated/dependency directory, link, parser-missing and syntax-error cases; deterministic repeat and byte-for-byte source snapshot comparison.
- Blueprint gaps after this MVP: imported calls remain syntactic references without cross-module binding resolution; no value/data-flow analysis; Python is inventory-only; live symlink/junction creation and clean npm install are not verified.
- Failed attempts and recovery: direct clone failed with DNS `Could not resolve host: github.com`; local `git add` failed creating `.git/index.lock` (read-only sandbox). Initial TypeScript 7.0.2 probe exposed its version-only CommonJS export, so the parser changed to pinned Babel AST 7.29.9 (MIT). Windows `os.replace` in the sandbox returned WinError 5, so report writing uses direct writes. Physical symlink and Junction creation were denied (WinError 1314 / access denied); the scanner link check passes using a test double. npm cache is empty, so package installation itself remains unverified.
- Next: resolve unambiguous imported function calls and strengthen multiline ESM fixtures, then rerun the complete suite, commit and compare against `TARGET_BLUEPRINT_V1.md`. Only after core analyzer validation, perform bounded n8n architecture research; do not implement the standalone AX FLOW engine.

## 2026-10-27 KST — blueprint call-evidence gap closed
- Gap-slice code commit: `52c7860b67dd6dc991c46141b2e841bde74d858f` (parent checkpoint `aee0ab1f1a35af70b89fd66bbf905cb25c97dcb7`).
- Blueprint comparison: added `resolved_call_edges` for direct imported calls only when a unique import binding, in-root module edge, and matching export are observed. Each edge cites call, import, and target-export path/line evidence. Multiline ESM and nested package boundaries are included in fixtures.
- Verification: `python -m unittest discover -s tools/rea-app/tests -v` — **8 passed, 0 failed**; `npm --prefix tools/rea-app run test:parser` — **PASS**. Synthetic fixture confirms deterministic reports and source-tree bytes unchanged.
- Test failures and fixes: first gap run selected the package `answer` edge before `add` because output was sorted; the assertion now selects the named `add` symbol. A multiline call is on line 4, not line 5; the evidence assertion was corrected. No product-code defect remained; rerun passed all tests.
- Remaining gaps: value/data-flow analysis, Python AST, physical symlink/junction creation (host denied), npm clean-install due offline registry/cache, Windows packaging, and verification against an authorized real repository. Ambiguous or dynamic calls remain syntactic references.
- Next: bounded n8n functionality/architecture research from official licensing and product documentation, producing only independent behavior notes/contracts. No n8n source, UI, node code or AX FLOW execution engine will be copied or implemented in this stage.

## 2026-10-27 KST — bounded n8n documentation analysis
- Scope/evidence: official n8n product docs and Help Center only; no n8n repository/package source, runtime, UI, or node code inspected or copied. Research covers trigger types and branch order, execution persistence/retries/errors, queue workers, credential encryption, retention, and SUL use boundaries.
- Independent behavior findings: triggers are webhook, polling, and other event/time triggers; one trigger starts each run. Since n8n 1.0, branches complete one at a time in canvas top-to-bottom/left-to-right order. Queue mode separates main trigger/webhook intake from workers; Redis carries execution IDs while the shared database stores workflow/execution state, and all processes share the instance encryption key. Queue mode is not a SQLite deployment target.
- Recovery/persistence findings: manual retry is a new execution that reuses completed-node results and replays the failed node's saved inputs; partial external effects within that failed node may repeat, and a failed sub-workflow action reruns its whole child flow. Error workflows receive execution identifiers only when saved; trigger activation failures use a different payload. Execution retention is configurable and pruning defaults to 14 days or 10,000 finished records, whichever threshold is reached first; running/waiting/new executions are excluded.
- Security/licensing findings: treat the instance encryption key as deployment secret shared by main/workers and back up the database before supported key rotation. The self-hosted Community edition uses SUL; n8n's current FAQ says internal organization authoring is covered, while exposing customer workflow authoring/configuration or hosting/white-labeling requires a commercial license. No product/license conclusion was sought beyond this docs-only study.
- Documentation sources: [execution order](https://docs.n8n.io/build/flow-logic/understand-execution-order.md), [triggers/actions](https://docs.n8n.io/connect/create-nodes/plan-your-node/choose-a-node-type.md), [retry behavior](https://docs.n8n.io/build/understand-workflows/understand-executions/view-all-executions.md), [errors](https://docs.n8n.io/build/flow-logic/handle-errors-gracefully.md), [queue mode](https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/enable-queue-mode.md), [execution data](https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/manage-execution-data.md), [key rotation](https://docs.n8n.io/deploy/host-n8n/configure-n8n/security/rotate-encryption-keys.md), [license FAQ](https://support.n8n.io/article/can-i-use-your-license-for-my-use-case).
- Verification: `python -m unittest discover -s tools/rea-app/tests -v` — **8 passed**; `npm --prefix tools/rea-app run test:parser` — **PASS**. First Python run failed 3 tests because this shell did not set `NODE_PATH` for the globally installed parser; reran with `NODE_PATH=$APPDATA/npm/node_modules/n8n/node_modules`, resolved `@babel/parser@7.29.9`, and all tests passed. No product-code defect.
- Research limitation/failure: direct access to the standalone credentials environment-variable page failed in the docs browser; key-sharing and encryption behavior were cross-checked against the official queue-mode and key-rotation pages. No external n8n test instance or licensing counsel was available/used.
- Remaining REA_APP blueprint limits: Python AST, value/data-flow analysis, real symlink/junction and clean npm-install verification, Windows packaging, and authorized real-repository validation remain open. They are recorded as limits, not regressions. No standalone AX FLOW execution engine has been implemented.
