# Next work unit — 2026-10-27 KST (verified checkpoint)

## P18 — REA_APP change-impact report — COMPLETE (2026-10-27 12:49 KST)
- Implementation commit: 150a056f1eb13dd352ef1a1be0ce9fb9324e98e3 on REA_APP, parent 1409d9d383e1515a1c19350252a1c7a6f534d04d.
- Added `rea-app compare BASELINE CURRENT --output-dir REPORTS`. It rejects equal/overlapping roots and outputs inside either source root; applies each scan's existing file/byte caps; hashes indexed files without including their contents in the report; labels added/removed/modified paths; follows resolved in-root JS/TS dependencies from both snapshots with exact import evidence; lists affected package entrypoints.
- Tests from tools/rea-app: `python -m unittest discover -s tests -v` — 14/14 PASS; `npm run test:parser` — PASS; `npm ls --all` confirms the pinned parser dependency tree (Windows Python 3.11.9 / Node 24.21.0). Determinism, same-size edits, added/removed files, transitive impact, entrypoints, source immutability, cap failure and path rejection are covered.
- Initial failure: one new test failed (13/14) because strict path resolution leaked a localized Windows exception for a missing comparison root. Non-strict canonicalization plus explicit directory validation fixed it; the full suite then passed.
- Limits: only indexed paths are compared; skipped paths are disclosed, and impact is bounded static reachability from the JS/TS module graph. It does not infer Python/runtime/dynamic/external-package effects.

## Next authorized step — overall chief review
- REA_APP's synthetic JS/TS acceptance and the permitted n8n docs analysis are complete for this pass. Review the branch evidence and the separate latest shared acceptance matrix before choosing more implementation.
- Keep the independent AX FLOW runner/engine on explicit hold until that review; do not merge REA_APP and feature/axflow-mvp. No site is needed or running.
- Last cross-track matrix: `docs/ACCEPTANCE_MATRIX.md` at `feature/axflow-mvp@62d712053470518376bdab59d4eec53191c46c88`, blob `4a1f223bfa0b73693972cecc11f4a5eda637c837`; heuristic A100/B100/C95/D95/E65 = 91% PARTIAL. This REA_APP work is not yet reflected in it.

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

Completed the permitted structure pass against official n8n documentation and its Help Center. Findings are functional observations for independent design; they do not authorize copying n8n implementation, UI, assets, or connectors.

- Execution order: workflows created from n8n 1.0 complete one branch before the next; canvas position orders the branches. Older workflows may retain the earlier level-by-level behavior.
- Retry and errors: a manual retry is a new execution. Completed nodes reuse saved results, while a failed node reprocesses all its items; partial side effects inside that node may duplicate. Retrying a sub-workflow node can rerun the sub-workflow. Error workflows are configured per workflow and start with Error Trigger.
- Queue mode: the main process enqueues execution IDs in Redis; workers load workflow data from a shared database, run it, then persist results/status. SQLite is not recommended for queue mode, and filesystem binary storage is unsupported there; use external binary storage.
- Code-node isolation: task runners isolate user-provided JavaScript/Python. The docs recommend hardened external mode for production/sensitive data; internal mode runs with the n8n process identity, is being deprecated starting with n8n 3.0, and queue workers need runner sidecars.
- License boundary: the current Sustainable Use License FAQ says customer-configurable automations through an app/API/MCP/AI need a commercial license even when the editor is hidden; OEM embeds keep n8n branding, and internal backend use is a separate Enterprise conversation. This is a product boundary signal, not a legal determination; written review is required before a commercial decision.
- Previously recorded execution retention/pruning and key-rotation findings remain in the earlier checkpoint below; this refresh focused on the current retry, queue, task-runner and license pages.

Sources: [execution order](https://docs.n8n.io/build/flow-logic/understand-execution-order.md), [retry behavior](https://docs.n8n.io/workflows/executions/all-executions/), [error workflows](https://docs.n8n.io/flow-logic/error-handling/), [queue mode](https://docs.n8n.io/deploy/host-n8n/configure-n8n/scaling/enable-queue-mode/), [task runners](https://docs.n8n.io/deploy/host-n8n/configure-n8n/set-up-task-runners/), [SUL FAQ](https://support.n8n.io/article/can-i-use-your-license-for-my-use-case), and [OEM overview](https://n8n.io/oem/).

**Result:** no n8n source or runtime was accessed or copied. Do not repeat broad n8n research without a concrete open question. The standalone AX FLOW engine remains on hold for overall chief review.

## 2026-10-27 KST — REA_APP 0.3.0 / Blueprint A closeout



The REA_APP Blueprint A acceptance audit is complete for the stated synthetic JS/TS scope. Feature commit `991fe3d908377a70a451013262449a8ad001d0d2` adds exported function signature contracts: explicit parameter/return annotations, optional/rest/default-presence flags, export aliases, and definition/export path+line evidence. Corrective UTF-8 commit `0a4b446bda6b78c3e5c7cbda2865cf061a64b6b9` restores `graph.py` after remote verification found that a truncated Base64 output had been included in its content. The corrected full file now matches the local normalized file. ESM and CommonJS cases pass. Reports omit function bodies and actual default values; ambiguous source bindings are omitted. Tool version is `0.3.0`.

Actual verification from `tools/rea-app`:

- `python -m unittest discover -s tests -v` — **10 passed**.
- `npm run test:parser` — **PASS**.
- `python -m rea_app --version` — **rea-app 0.3.0**.
- Python test execution set `NODE_PATH` to the host-installed `@babel/parser@7.29.9`; project-local clean install was unavailable/unverified.
- After repair, GitHub returned valid UTF-8 for `graph.py`; the fetched full file matches the normalized local file. Tests were rerun after this correction.

The permitted n8n architecture/licensing pass is also complete from official documentation only. Its findings and sources are recorded above and in `STATUS.md`; do not repeat broad research. No n8n source/UI/runtime was inspected or copied.

**Historical Blueprint V1 estimate at this closeout: 20%** under an explicit equal-weight A–E gate count. A passes for bounded synthetic acceptance; B (standalone runner), C (customer UI), D (DBVORA integration), and E (security, Windows and end-to-end release validation) remain unimplemented. This percentage describes the whole AX FLOW target, not REA_APP alone. The independent runner remains on explicit user hold until chief review.

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
