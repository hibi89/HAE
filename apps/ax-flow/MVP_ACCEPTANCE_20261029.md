# HAE Synthetic MVP — Executed Acceptance Record (2026-10-29)

## Scope and acceptance outcome

The bounded, local-only synthetic HAE → Lightning Azent (LA) → explicit approval → SQLite → execution receipt/audit workflow has **passed direct runtime acceptance** in an isolated Linux Python 3.11.2 environment.

This is **not** a general-purpose AI automation platform, customer-data authorization, Windows release certification, or proof of external connector exactly-once semantics.

## Source revisions actually tested

- HAE `feature/axflow-mvp`: `46d8fa64da8843445b34de29358828017abc6cf3`
- Lightning Azent `feature/lightning-azent`: `9cba6424dadf3fadb0ccd6ed10040e322c4a62fa`
- SOVIA Sovereign `feature/p2-la-plan-observation-reconcile-20261028`: `e9fb619a7510f56bca7ec7f972378859a7d49a12` (SOVIA plan/observation/PII offline modules)
- DBVORA `feature/p0-db-map`: `7f9a1c0d0f0e31f68fb600e47d04ccff1e22faaf` (SQLite inventory API modules)

The test environment assembled these source-owned modules into an isolated temporary filesystem and used temporary, synthetic-only SQLite fixtures. No production database or secrets were loaded.

## Executed tests

| Acceptance | Actual observed output |
| --- | --- |
| `python smoke_http.py` with real LA staged | `6/6 PASS` · exit 0 |
| `python -m unittest discover -s tests -p test_la_adapter.py -v` | `5/5 PASS` · exit 0 |
| Full HAE tests with SOVIA + DBVORA sources and local API dependencies | `Ran 124 tests ... OK (skipped=3)` · exit 0; 121 passed |
| Real cross-repository P2 HTTP integration | `1/1 PASS` · exit 0, included in full HAE suite |
| Full Lightning Azent independent suite with fixture files | `Ran 68 tests ... OK` · exit 0 |

Direct HTTP acceptance exercised:
1. Read-only plan preview, denial without explicit write approval, then successful SQLite import
2. Redacted, persisted LA execution audit
3. A second independent run against an already-created SQLite runtime/business ledger
4. Incomplete-run recovery after renewed approval, with no duplicate business rows
5. Rejection of recovery requests for already-completed runs
6. Persistence of run status and LA audit through HTTP server restart

Cross-repository P2 additionally exercised SOVIA offline reconciliation, DBVORA's real read-only SQLite API, configured-service failures, a refused business write and safe resume, and persisted status/audit.

## Deliberately unverified or environment-blocked

- Three **Windows-specific** tests were skipped on Linux: NTFS junction replacement, Windows CSV open share mode, and MAX_PATH refusal. Windows launcher execution and real Windows user acceptance remain unverified.
- GitHub Actions runs on this branch previously failed **before any runner step executed** (job steps empty); they are not evidence of test failure or test pass. CI remains a deferred, nonblocking platform check.
- SOVIA and DBVORA are optional components and were tested in a dedicated cross-repository configuration. The default core-only installation requires neither.
- Real customer records, remote provider credentials/API writes, deployment hardening, and signed Windows packaging were outside this synthetic MVP acceptance.

## Reproduction

From `apps/ax-flow` with Python 3.11+, real LA package on `PYTHONPATH`:

```shell
python smoke_http.py
python -m unittest discover -s tests -p test_la_adapter.py -v
python -m unittest discover -s tests -v
```

For the optional cross-repository test, set `HAE_INTEGRATION_ROOT` to a folder containing `packages/lightning-azent`, `SOVIA` (the three required offline modules) and `DBVORA` (the local read-only API package), with FastAPI and Uvicorn installed. On Windows, `run-integrated.ps1 -Smoke` runs the real HTTP acceptance and the LA adapter suite but still requires an actual Windows execution to confirm launcher and NTFS behavior.

**Gate result:** The defined, synthetic local HAE+LA core MVP passed actual integration; the extended Linux cross-repository integration passed. Windows-specific and release-readiness gates remain open.
