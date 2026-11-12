# PRIVATE HAE/LA → PUBLIC SOVIA P41/P43 first-party synthetic local integration (2026-11-12 KST)

## Privacy and architecture
Public SOVIA must remain independent and cannot be shipped with PRIVATE HAE/LA engine code, raw audit events, SQLite or real customer file names/targets. A single normalized plan SHA does NOT prove the SOVIA plan corresponds to the same LA run; external human authentication/consent and provenance are future owner gates.

Architecture A would copy private run data/code to public or modify frozen LA core/schema; rejected for confidentiality, migration and P18 ZIP inventory constraints. Architecture B is isolated PRIVATE feature branch source-only producer modules: read first-party verified **actual synthetic** LA SQLite receipts, pseudonymize event/step metadata, use independently verified pinned PUBLIC SOVIA consumer *inside private CI only*. Selected.

## Exact delivered components
- `packages/lightning-azent/sovia_projection_private.py` outside frozen `lightning_azent/` source directory. Requires explicit `synthetic_acknowledged=True`, first-party HAEBridge and actual `bridge.evidence()`, which checks read-only business SQLite receipts, terminal audit event, plan/run binding, and scoped write receipts. Produces SOVIA P40 exact schema and only integer aggregate counts; `source_authenticated=false`, `approval_authenticated=false`, `stream_completeness_verified=false`. Caller-supplied SOVIA fingerprint is only an assertion.
- `packages/lightning-azent/sovia_semantic_projection_private.py`: restricts to synthetic csv_read/sqlite_import_csv, checks one-to-one actual `step_completed` audit events by source step+operation, no duplicates/missing/skipped/failed, creates sanitized SOVIA `sovia.plan_review.v1` and 1.0 observed data with step001/step002 aliases, fabricated time/agent/target, and a deliberately independent SOVIA allowed_tools policy that flags write even when LA synthetic write was explicitly approved by test harness. No actual run ID, file name, original event time, source payload or private approval digest exported.
- `tests/test_sovia_projection_p41.py` 9 tests, `tests/test_sovia_semantic_projection_p43.py` 5 tests, and `verify_sovia_p41_roundtrip.py` pins public SOVIA P40 source SHA `63c9a329de71470089e0a866e802a20ce9a48ad6` within private CI. End-to-end local synthetic HAE natural language plan → explicit synthetic write flag in test → real LA SQLite → actual audit event → public SOVIA owner review and minimal cross-check, 2/2 observed event aliases, policy risk preserved, missing actual step denied.

## Executed evidence
- PRIVATE exact functional/test SHA **`7b27c4926ee353d537a1526d8b4d2919b9f86eeb`**, [GitHub Actions #43215726885](https://github.com/hibi89/HAE/actions/runs/43215726885): **2/2 SUCCESS** Windows+Ubuntu Python3.11, 128 LA PASS each, 91 HAE original PASS each, Windows backup targeted1 PASS, 0 failures/skips in LA/HAE suites, P18 original deterministic zipapp built+verified. Cross-repo synthetic terminal: `REAL_SYNTHETIC_LA_SQLITE_STEPS_TO_SOVIA_AUDIT_PASS`. No source or customer data committed/exported to public GitHub; only public SOVIA source fetched by a pinned checkout in private CI.
- Initial P41 #43212701824 **FAILED 8 old P18 ZIP source inventory cases** due adapter in fixed module directory; moved outside module directory and previous 11-member packaging preserved. Intermediate P43 #43215548711 **FAILED 1 test** when extra step was appended after terminal, making prior LA terminal guard reject first; fixed test to add terminal clone after duplicate to exercise independent P43 duplicate rejection. Exact final run green; do not retry old failed approach.
- Public SOVIA P42 separate v0.15 functional SHA `a6991d062e657073fd5c5df077c87db9aa390515`, [Actions #43214296725](https://github.com/hibi89/SOVIA_sovereign/actions/runs/43214296725) 4/4 green with real hosted Windows CMD source-only candidate. Public ZIP contains **no PRIVATE HAE/LA runtime**.

## Acceptance and scope
**SOVIA 95% provisional technical after P41/P43 and P42; LA's own complete product score stays 85% provisional, HAE score unchanged.** SOVIA 95 is not release readiness. Actual commercial real-LA source authentication, user identity, source authority, privacy/retention rights, physical owner Win10/11/Defender, signed installer, customer false-positive pilot, support and explicit seller GO unverified. All historical original/base branches preserved; no production/Vercel or chargeable external AI. No private branch merge or release.

Owner-approved local test from exact private branch and public P40 checkout:
```sh
python -I -B packages/lightning-azent/verify_sovia_p41_roundtrip.py --public-source PATH_TO_PINNED_PUBLIC_SOVIA_P40_SOURCE
python -B -m unittest discover -s packages/lightning-azent/tests -v
```
Run only with synthetic, disposable files and actual appropriate local permissions.

**As of:** 2026-11-12 KST. Exact tested code SHA above, docs HEAD distinct; user input/data and real credentials never used.
