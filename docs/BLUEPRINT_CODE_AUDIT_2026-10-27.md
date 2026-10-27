# AX FLOW code vs frozen blueprint — Chief GPT-6 review (2026-10-27 KST)

**Scope / truth:** Compared `docs/TARGET_BLUEPRINT_V1.md`, `REQUIREMENTS.md`, `docs/ACCEPTANCE_MATRIX.md`, `docs/ARCHITECTURE.md` with real source on `feature/axflow-mvp`. This is **source inspection, not a new end-to-end PASS**. The shared matrix remains unchanged on this feature branch. Existing 91% is a historical heuristic for the limited synthetic slice, **not complete-product readiness**.

Baseline: before P49 `4f6135027ce325f7bcaad57de935ef6ad1401990`. P49 source change `9fe52ceea79d2251c953b0c17dcb33ce5cab0010`, new regression `3704eb86b2ca758432b4b104907637a61aabf150`. The branch SHA advances as audit/handoff documents are saved; always recheck remote HEAD.

## Required blueprint vs observed implementation

| Original gate / requirement | Direct code evidence | Verdict on inspected source (not independently run) | Residual gap |
|---|---|---|---|
| R-A1/R1: authorized read-only REA_APP JS/TS source map | `REA_APP` has `tools/rea-app/rea_app/`, `babel_parser_adapter.cjs`, synthetic tests; source is **separate branch** | Code present; previously reported tests, no fresh independent full run | source-permission/Windows junction limitations; no arbitrary-language completeness |
| F1: typed/validated versioned IR | `apps/ax-flow/axflow/engine.py` `validate`, `planner.py` | Implemented for strict `axflow.ir.v0` subset | No arbitrary connector contract/compiler |
| F2: local deterministic executor, status, resume, interval | `engine.py`, `__main__.py`, `runlog.py`, `scheduler.py`, `state_backup.py` | Implemented for synthetic subset; historical crash/replay/unit evidence | No long-running Windows service, external side-effect replay, customer pilot |
| F3: business storage distinct from runtime | `engine.py` local `records` / `csv_records`; `sqlite_put/get/import` | SQLite implemented; write requires explicit approval | No generalized dataset registry, Sheets/Postgres |
| F4: natural-language → configured testable plan | `planner.py` bounded EN/KR rules; `web.py` `/api/preview`, `/api/run`; browser `index.html` | Limited templates/import/filter/normalization/lookup; UI hides JSON in details | **Preview validates IR but does not preflight CSV contents/execution**; no bounded AI repair, general model, XLSX/PDF |
| F5: OAuth and scoped provider connectors | no OAuth secret broker / Gmail-Sheets implementation in present AX FLOW package | **NOT IMPLEMENTED** | Real provider consent and explicit external action authorization needed |
| D1: separate read-only DBVORA map | `dbvora_client.py`, `web.py /api/dbvora`, UI map | Limited one-selected SQLite inventory API, contract normalization/offline | No asset enrollment registry, durable app-to-app authentication, customer service deployment |
| D2: DBVORA source backup/restore | `state_backup.py` handles only **AX FLOW runtime ledger** | **NOT IMPLEMENTED as DBVORA restoration** | DBVORA independent source restore tests, authorization and no-mutation verification |
| F6: customer GUI | `web.py`, `static/index.html/app.js` | Local bounded synthetic browser interface exists | No customer authentication / broader permissions editor |
| F7: secure local boundary, fail-closed | path and Host/Origin checks, size bounds, SQLite idempotency; P49 disables proxy auto-routing | Partly implemented, no independent audit | cross-system auth, denial controls, prompt injection, real OAuth, live security review |
| F8: Windows and customer packaging | `tools/package_axflow.py`, `tests/test_package.py` | zipapp / historical Windows synthetic tests | customer installer/signing, clean machine, product demo and restore gates |
| B1: pricing/pilots/legal | planning documents only | **NOT STARTED** | 3 controlled pilot workflows, legal/licensing review, support metrics |

## Implementation-to-blueprint mismatches found

1. **P49 proxy policy (code patched + new test, full tests pending):** `DbvoraClient` restricted base URL to `127.0.0.1` but `urllib.request.build_opener(_NoRedirect)` still inherited `http_proxy` from the environment when one is configured. That could route a supposed local metadata request through an unapproved proxy. Updated to `build_opener(ProxyHandler({}), _NoRedirect)`. This does not change allowed destination, provider contract, redirect blocking, request schema, or source DB. A standard-library **isolated reproduction** demonstrates before/after proxy behavior **2/2 pass**; **actual repository tests on new HEAD NOT RUN**. A new `tests/test_dbvora_client.py` test asserts no environment proxy lookups with an existing synthetic loopback fixture.
2. **F4 preflight/dry-run semantics (open):** `POST /api/preview` only calls `plan_request` and saves a preview token. File existence, CSV parsing and transform errors are discovered on `POST /api/run` after write approval. UI says `검증 후 실행`. This is IR-only validation, **not a full dry run**. Implement a strictly read-only fixture preflight with bounded CPU/file budget, unchanged source, no runtime/business DB side effect and explicit stale-file handling before claiming dry-run PASS.
3. **Upload/executor size mismatch (open):** `web.py MAX_UPLOAD_BYTES=512*1024` and UI says 512 KiB; `engine.py MAX_CSV_BYTES=262144` rejects a CSV over 256 KiB. A 300 KiB UTF-8 upload may stage successfully but fail execution. **Do not silently shrink advertised support or raise core memory limits without separate design/acceptance review**. Choose one consistent documented limit after approval; enforce at the earliest safe boundary, with boundary tests.
4. **No general end-user auto configuration:** only selected CSV tasks are parsed, unsupported instructions fail closed. This respects MVP scope, not the full AI-first design.
5. **Documentation evidence is stale:** `docs/ACCEPTANCE_MATRIX.md` still starts at P45 77/77 while P46/P47 historically reported 80/81. P48/P49 code adds new tests with no full-run evidence. Do not promote completion percentage, or retroactively reinterpret old tests as new SHA proof.

## Reviewed design alternatives and decision

**Local DBVORA HTTP transport:** A) keep default urllib proxy auto-discovery — minimal code, but violates local-only invariant under environment proxy; B) explicitly install `ProxyHandler({})` with existing redirect blocker — no new dependencies, no API/cost change, minimal two-line fix; C) bypass HTTP using direct SQLite/DBVORA source — easier proxy isolation but breaks independent repo and least-privilege boundary. **B selected**, least code/maintenance, preserves existing interface. No changed privilege, provider, billable service, customer DB or public access.

**For F4 future preflight:** A) dry-run plan by invoking the writing engine on disposable SQLite clones — closer to execution but adds clone/state complexity and accidental side-effect risks; B) validate supported CSV/parser/transforms with read-only bounded checker and source SHA gate, then execute separately on approved action — cheaper, safer for current limited scope, but not proof of external workflow correctness. **Recommend B** as next proposed bounded design; independent end-to-end evidence must still be collected. No implementation/approval presumed by this document.

## Next priority / verification

1. **P49 VERIFY FIRST:** In real connected `apps/ax-flow/` Python 3.11+ checkout, run `python -m unittest discover -s tests -v`, `python -m compileall -q axflow tests`, `node --check axflow/static/app.js`, `node --test tests/test_ui_provenance.cjs`. Specifically confirm P48 numeric preview/no-write and P49 proxy no-env and DBVORA local response. Record counts/OS/SHA and correct any observed regression. No configured Actions CI exists.
2. **P50 design review:** implement read-only CSV preflight + bounded SHA-backed approval only after source/resume and upload constraints are resolved. Preserve existing tests, local-only/no external action.
3. **P51 consistency:** upload/engine limit harmonization with user-approved scope, fail-before-stage or bounded-engine extension, boundary tests.
4. **Later full product gates:** authorized OAuth connector; DBVORA verified independent restore; customer auth/install, independent security, three pilots. These cannot be marked done from synthetic source inspection.

## Handoff / execution limits
- Repository `hibi89/AX_FLOW`, private, source branch `feature/axflow-mvp`; `REA_APP` and DBVORA independent.
- Vercel/Production: N/A, this is synthetic local app. No real customer files, credentials or external service used.
- Git history is rollback. No changes to `docs/TARGET_BLUEPRINT_V1.md`, original acceptance criteria, other product branches, or business databases.
- Exact final SHA and user identity must be read from GitHub after writing handoff; unsigned Git commits do not imply signed Windows binaries.
