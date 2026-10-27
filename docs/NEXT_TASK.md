# Next work unit — 2026-10-27 KST (ACTIVE fast-track)

## P16 — REA_APP clean install and lockfile verified
- Added the lockfile for pinned `@babel/parser@7.29.9`; setup now uses `npm ci`.
- From `tools/rea-app`: `npm ci --ignore-scripts --no-audit --no-fund` PASS, Python **11/11 PASS**, `npm run test:parser` PASS, and `npm ls --all` confirms the resolved dependency tree.
- Offline install first failed with `ENOTCACHED` for `@babel/types@7.29.11`; the tarball was missing from the local cache. Online public registry install then succeeded with scripts and audit disabled; no credentials were used.
- Actual filesystem junction remains unverified because the host denied creation; the synthetic reparse-attribute test passes. Overall tracker remains **77% / PARTIAL**.

## REA_APP parser verification checkpoint (2026-10-27 KST)
- Re-ran the bounded analyzer against synthetic fixtures after installing the pinned public `@babel/parser@7.29.9` required by this branch's README. `python -m unittest discover -s tests -v`: **10/10 PASS**; `npm run test:parser`: PASS. Checked the analyzer/parser implementation files against `REA_APP`; local and remote source blobs matched exactly.
- The regression now copies only the Python package and parser adapter to an isolated temporary tool root to prove missing-parser fail-closed behavior. It no longer assumes that clearing `NODE_PATH` hides a package installed beside the real adapter.
- Failure causes/resolution: first run lacked `node_modules`, so five Python checks and the Node assertion reported parser unavailable; local npm cache was empty. Installed the exact public pinned package using `--ignore-scripts --no-audit --no-fund --package-lock=false` (four packages, no lockfile; `node_modules` is git-ignored). With it present, the missing-parser test exposed its incorrect isolation assumption; corrected and reran Python 10/10 plus Node successfully.
- Test-only commit on `REA_APP`: `b815e72f3f0c9e0e1aad117b7db7b6cad9f84bc1`. No analyzer behavior changed.
- Blueprint A remains **MVP_VERIFIED** for the supported synthetic JS/TS scope. Overall A–E estimate stays **77% / PARTIAL** due unrelated UI, restore, security, installer and customer/release gates.
- n8n's allowed official-source structure review is recorded on `feature/axflow-mvp` at `8e8f89b5f797fdf77790a2fea57d6d7ad7b344a6`; no source/assets were copied.

**Next:** REA_APP synthetic acceptance is reconfirmed. Do not expand source-analysis scope speculatively.

## P13 complete — Windows reparse attribute test added (Python 11/11)
A unit test covers the scanner's Windows reparse attribute set/clear branch; Python 11/11 and Node parser assertions pass. Test commit: `98c6d6b399804b9041862caeb3124a0faa1146a0`. README now records the environment limit. A real junction fixture under the temp directory was denied by Windows with **Access denied**; no elevation was tried. The first PowerShell probe had a syntax error and executed no operations. The actual filesystem gate remains open; attribute-level coverage is not a substitute.

Overall status remains **77% / PARTIAL**. Continue with a permission-free Blueprint gap. Do not bypass browser URL-confidence or external approval gates. Continue only with a concrete permission-free A–E gap; keep the standalone AX FLOW engine paused pending overall review. The P10 AX FLOW and n8n review evidence is on `feature/axflow-mvp`.


**Owner decision supersedes 21-week plan:** first 2 weeks REA_APP + own n8n-like runner; next 3 weeks AX FLOW + parallel DBVORA integration. Read docs/FAST_TRACK_5_WEEK.md, docs/TARGET_BLUEPRINT_V1.md, docs/CODEX_EXTRA_HIGH_ORDER.md before any implementation.

## Codex first authorized implementation unit (MVP D1–D3, REA_APP branch)
1. Verify hibi89/AX_FLOW current HEAD and read HANDOFF/STATUS/AGENTS/REQUIREMENTS/docs + actual code.
2. Build read-only bounded source walker and parser-accurate JS/TS import/export graph with file/line provenance under tools/rea-app. Python AST optional. Use a permissible local AST parser (TypeScript compiler API/Tree-sitter) with pinned version; no code copied from n8n.
3. Design small synthetic JS/TS fixture, run CLI end-to-end, return deterministic JSON+Markdown. Fail closed on huge/binary/secret/symlink/file escape cases. Never execute inspected code or mutate the source root.
4. Fix test failures; report **actual** commands, PASS/FAIL/SKIP, exact commit SHA and target blueprint gaps. Avoid asking owner to do work Codex can do itself. No blanket “finished” claim from skeleton.
5. D4–D6 permitted n8n study and original behavior contracts; D7–D14 independent executor remains a planning target only and is on hold until chief review. Do not implement the standalone AX FLOW engine before that review.

## Chief review gate
Compare every completed small module against docs/TARGET_BLUEPRINT_V1.md, identify high-priority missing features, and allow Codex to implement immediately within approved scope. First design decisions preselected for speed (bounded Python CLI + AST parser adapter, native JSON IR, SQLite, local-first). Escalate new paid costs/licensing, public visibility, user secrets, real external API/DB operations or destructive effects only.

## DBVORA parallel work
AX FLOW-side feature/dbvora-integration branch only. Check independent DBVORA source/API/Windows gate before committing adapter claims. No dependency on a nonexistent universal API; safe read-only SQLite inventory first. Preserve separate runtime and business SQLite.

## Safety
The active 2026 hackathon deadlines overlap Week 3; don't override submission priorities. 5-week target is conditional, no automatic background execution. Update STATUS/HANDOFF when actual implementation/test results change.

## 2026-10-27 KST — MVP checkpoint
The first REA_APP CLI MVP is implemented and its 8 Python integration tests plus the Node parser-adapter assertions pass on synthetic input. The physical symlink/junction test is limited by this Windows sandbox's link-creation permissions; the scanner's link branch is covered with a test double. The clone/DNS and local `.git` write failures, parser version adjustment, output-write workaround and exact GitHub commit SHA are recorded in `STATUS.md` and `HANDOFF.md`.

The blueprint call-evidence gap is closed for a supported subset: direct imported calls are linked only with a unique in-root module edge and matching export. Multiline ESM and nested package boundaries pass in synthetic tests. Remaining coverage limits are recorded in `STATUS.md` and `HANDOFF.md`.

Next work unit: perform bounded n8n architecture and licensing research using official product documentation, then summarize independent behavior contracts for trigger/step execution, persistence, credentials, retries and errors. Do not copy n8n source/UI/node code or implement the standalone AX FLOW engine during this stage.

## 2026-10-27 KST — n8n documentation findings and gate

Completed this docs-only pass against official n8n documentation and the n8n Help Center:

- **Graph execution:** webhook, polling, and other event/time triggers start runs; a single run is started by its eventing trigger. Workflows created from n8n 1.0 finish branches one at a time in canvas top-to-bottom/left-to-right order; workflow settings can change the execution order.
- **Queue architecture:** main intake handles triggers/webhooks and enqueues execution IDs in Redis; workers load workflow data from the shared database, run it, write results/status to the database, and notify main via Redis. Main, workers, and webhook processors share `N8N_ENCRYPTION_KEY`. Queue mode is not a SQLite deployment target.
- **Recovery:** manual retry is a new execution that reuses results from completed nodes. The failed node receives saved input and processes all its items again, so a partial side effect within that node may duplicate; retrying a sub-workflow node reruns that sub-workflow. Error workflows receive a different payload for trigger activation errors; execution ID/URL require a saved execution.
- **Persistence:** execution save settings are configurable. Pruning defaults to enabled and removes finished records when they exceed 14 days or 10,000 records; new/running/waiting executions are excluded. The database must be backed up before supported encryption-key rotation.
- **Commercial boundary:** the official current SUL FAQ says internal organization authoring is permitted in Community, while customer-facing automation authoring/configuration, hosted service or white-label use requires a commercial license. Treat this as a product-boundary signal only; get written guidance from n8n before any commercial integration decision.

Sources: [execution order](https://docs.n8n.io/build/flow-logic/understand-execution-order.md), [trigger/action types](https://docs.n8n.io/connect/create-nodes/plan-your-node/choose-a-node-type.md), [retry](https://docs.n8n.io/build/understand-workflows/understand-executions/view-all-executions.md), [errors](https://docs.n8n.io/build/flow-logic/handle-errors-gracefully.md), [queue mode](https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/enable-queue-mode.md), [execution retention](https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/manage-execution-data.md), [key rotation](https://docs.n8n.io/deploy/host-n8n/configure-n8n/security/rotate-encryption-keys.md), [SUL FAQ](https://support.n8n.io/article/can-i-use-your-license-for-my-use-case).

Verification on synthetic fixtures: `python -m unittest discover -s tools/rea-app/tests -v` — **8 passed**; `npm --prefix tools/rea-app run test:parser` — **PASS**. One first test command omitted `NODE_PATH`, causing 3 expected parser-unavailable failures; setting it to the installed global Babel parser location made the entire suite pass. A standalone credentials environment-variable docs page was inaccessible; encryption-key evidence was cross-checked from queue-mode and key-rotation docs. No n8n source or runtime used.

**Hold point:** before any independent AX FLOW runner/engine work, chief review must compare the passing REA_APP scope and remaining blueprint gaps. Current REA_APP limits: Python AST, value/data-flow, physical symlink/junction and clean npm install validation, Windows packaging, and authorized real-source validation. The next task is to decide which of these merit a bounded follow-up; do not start the standalone engine before review.

## 2026-10-27 KST — REA_APP 0.3.0 / Blueprint A closeout

The REA_APP Blueprint A acceptance audit is complete for the stated synthetic JS/TS scope. Feature commit `991fe3d908377a70a451013262449a8ad001d0d2` adds exported function signature contracts: explicit parameter/return annotations, optional/rest/default-presence flags, export aliases, and definition/export path+line evidence. Corrective UTF-8 commit `0a4b446bda6b78c3e5c7cbda2865cf061a64b6b9` restores `graph.py` after remote verification found that a truncated Base64 output had been included in its content. The corrected full file now matches the local normalized file. ESM and CommonJS cases pass. Reports omit function bodies and actual default values; ambiguous source bindings are omitted. Tool version is `0.3.0`.

Actual verification from `tools/rea-app`:

- `python -m unittest discover -s tests -v` — **10 passed**.
- `npm run test:parser` — **PASS**.
- `python -m rea_app --version` — **rea-app 0.3.0**.
- Python test execution set `NODE_PATH` to the host-installed `@babel/parser@7.29.9`; project-local clean install was unavailable/unverified.
- After repair, GitHub returned valid UTF-8 for `graph.py`; the fetched full file matches the normalized local file. Tests were rerun after this correction.

The permitted n8n architecture/licensing pass is also complete from official documentation only. Its findings and sources are recorded above and in `STATUS.md`; do not repeat broad research. No n8n source/UI/runtime was inspected or copied.

**Overall Blueprint V1 completion: 20%** under an explicit equal-weight A–E gate count. A passes for bounded synthetic acceptance; B (standalone runner), C (customer UI), D (DBVORA integration), and E (security, Windows and end-to-end release validation) remain unimplemented. This percentage describes the whole AX FLOW target, not REA_APP alone. The independent runner remains on explicit user hold until chief review.

**Failure record:** The first feature commit's `graph.py` blob was corrupted because its large Base64 text exceeded the command-output limit and the truncation warning was accidentally included in the payload. GitHub UTF-8 verification caught the problem. Re-uploading the file in small chunks fixed it. The local test suite did not detect remote blob encoding, so source fetch verification remains part of commit acceptance.

**Unverified environment items:** clean npm install, physical symlink/junction creation (Windows host denied permission; scanner rejection path has test-double coverage), Windows packaging, and authorized non-synthetic source validation. These do not block bounded synthetic A acceptance. No external auth, customer source, paid service or deploy is authorized or needed for the next review gate.

**Next safe step:** chief review decides whether and when to authorize the independent engine. Until then, do not begin B. Any additional work should stay within a separately prioritized REA_APP verification gap; do not broaden the n8n study without a concrete open question.

## 2026-10-27 KST — REA_APP bounded data-flow checkpoint

Implemented and committed as `1e43893146bdbd46b030e56e84e1d4959c07ab35` (parent `f25abdc6d7424677ead023e445a3baa401e19f63`): `value_flow_edges` now cover same-scope direct aliases, call results assigned to simple names, identifier call arguments and identifier returns. Every edge includes exact source/use/call/return lines. Duplicated or reassigned bindings are omitted. This is a conservative syntax-level subset; control-flow, runtime semantics and cross-module value flow remain out of scope. Tool version is 0.2.0.

Verification from `tools/rea-app`: with `NODE_PATH` pointing to the host-installed Babel parser, `python -m unittest discover -s tests -v` — **9 passed**; `npm run test:parser` — **PASS**; `python -m rea_app --version` — **rea-app 0.2.0**. One failed invocation used a repo-root test path while already in the package directory; rerunning the documented `-s tests` command passed. Full result and rollback are in `STATUS.md` and `HANDOFF.md`.

### Blueprint A acceptance audit

- Synthetic JS/TS source scan through the real CLI: covered by integration tests.
- Dependency, entrypoint, imported-call and bounded local value-flow evidence: covered with exact relative paths and lines; observed syntax is labeled separately from inferred entrypoint metadata.
- Repeatability and read-only behavior: JSON/Markdown byte-identical across reruns and synthetic source snapshots unchanged.
- Resource/safety limits: file-count and total-byte caps fail closed; per-file caps, binary/secret/dependency skips, output-outside-root and parser-missing behavior are tested. Physical link creation is restricted by this Windows host; a test double exercises the scanner's rejection branch.
- Language limits are explicit: JS/TS receives AST parsing; Python and other files are inventory-only. No universal source-reconstruction claim.

**Remaining environment/coverage limits:** clean npm dependency install (registry/cache unavailable), physical symlink/junction test (host permission), Windows packaging and authorized non-synthetic source validation. These do not block the synthetic supported-scope MVP. Keep the runner/engine paused until chief review; no n8n source or code was reused.
