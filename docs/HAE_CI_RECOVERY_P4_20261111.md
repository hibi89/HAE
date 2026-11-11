# HAE P4: Windows/Linux CI regression repairs and DBVORA protocol-fixture E2E

**Date:** 2026-11-11 KST  
**Repo/branch:** hibi89/HAE / feature/axflow-mvp  
**Exact code SHA:** `14c8a7b75b079c8904792cbf3eaae7d1eeded60b`  
**Code CI:** https://github.com/hibi89/HAE/actions/runs/42976273517  
**Result:** overall FAILURE (distribution source parity), not release approved.

## Repro and concrete counts

Existing GitHub Actions stages pinned LA source and UGREEN bridge, uses Node UI race harness and `cd apps/ax-flow && python -m unittest discover -s tests -v`. Source `14c8a7b75b079c8904792cbf3eaae7d1eeded60b` Windows 204 test executions: 195 PASS, 2 FAIL, 7 SKIP, 0 ERROR. Ubuntu identical. Newly added synthetic real HAE/LA SQLite-to-DBVORA-protocol fixture and disconnected-service checks **2/2 PASS on both runners**. This is not real DBVORA service startup: local mock responds with contract `p0-01.v1` inventory derived from actual synthetic SQLite produced by LA in the same test.

Earlier 4f19b367 run #42972148842: Windows 202 tests with 7 FAIL, 13 ERROR, 7 SKIP; Ubuntu 202 tests with 3 FAIL, 7 SKIP. New run #42975404586 before new E2E: Windows and Ubuntu 202 tests, only 2 FAIL 7 SKIP. Fixed Windows temporary SQLite file connection not closing (13 WinError32), source-replacement and junction/link tests incorrectly comparing 8.3 aliases, Win32 HANDLE expected path mismatch, and transient port availability false negatives. Actual original no-follow/HANDLE validation and restart bind gate preserved.

## Two release-blocking failures (not waived)

- `test_checked_in_zipapp_matches_current_hae_and_staged_la_sources` — source contains new modules (schema, business, LA bridge) absent from checked-in historical zipapp.
- `test_release_zip_matches_shipped_sources_and_executes_real_la_e2e` — current source vs archived release files differ, including run-bundled.cmd CRLF/LF and source parity.

Do not disable tests, call full suite PASS, overwrite previous release, publish installer or create new release candidate without explicit owner approval. Existing build/CI are reproducible, GitHub historical SHA enables revert. A separate versioned candidate with SHA-manifest and native Windows validation is the recommended release remedy when permitted.

## Coverage boundary and progress gate

- Genuine HAE + Lightning Azent engine generated approved synthetic SQLite business rows; no customer data or actual DBVORA backend used.
- Mocked local DBVORA HTTP `GET /health` + `GET /api/inventory` returned real *synthetic* SQLite metadata; HAE `/api/dbvora` response excludes raw rows/path, GET read-only source SHA unchanged.
- Simulated unhealthy DBVORA returns `INVALID_HEALTH`, preserves LA SQLite row count, SHA and `/api/status`; no automatic write retry.
- Google OAuth/Gmail/Sheets, real DBVORA, customer Win10, signed installer, 3 practical customer workflows, production are NOT VERIFIED.
- Final-product progress **73% provisional**, target **85% unmet**; RELEASE HOLD. Public hub is a metadata-only score mirror, not a source copy.
