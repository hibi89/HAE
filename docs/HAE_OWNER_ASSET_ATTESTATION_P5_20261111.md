# HAE P5 — owner-selected SQLite / DBVORA contract attestation (2026-11-11 KST)

**Verified code SHA:** `522bd95139ff104fa0d9504ca6e3d1f82428ed47`  
**GitHub Actions exact revision:** https://github.com/hibi89/HAE/actions/runs/42980940727  
**Branch:** hibi89/HAE feature/axflow-mvp  
**Result:** Windows+Ubuntu Python each 219 executed: **210 PASS / 2 FAIL / 7 SKIP / 0 ERROR**; Node UI race **16 PASS**. Overall GH Actions **FAILURE** because original checked-in ZIP/pyz ≠ current source. Customer release **HOLD**.

## Architectural decision

A direct persistent catalog / real DBVORA or Google OAuth integration is a higher-coupling, credential+permission-requiring option. B owner-specified *synthetic-only* SQLite fingerprint and read-only DBVORA p0-01.v1 local API agreement (selected): no remote SaaS account, new dependency or customer data. No persistent provider-neutral asset registry or verified real DBVORA process is claimed.

The HAE owner explicitly selects an absolute offline synthetic SQLite file for `--dbvora-asset-source` and a localhost `--dbvora-url`. Startup otherwise preserves old API. `GET /api/dbvora-asset` checks local file integrity, SHA256, file identity, DBVORA db_id (SHA256 of selected normalized path), exact size scope and size, all table names/column declared null/PK and FK edges, top-level relationships and measured provenance. A second local file fingerprint after localhost network round trip rejects mutations. No unrestricted SQL, no user table rows, no owner path/credentials/SQL text in receipt; errors are bounded `ASSET_ATTESTATION_HOLD`. Receipt keeps `customer_ready:false`, `dbvora_process_identity_verified:false`, `release_gate:HOLD`.

UI has an explicit manual "합성 DB 자산 일치 검증" button, never auto-probes on page load; verifies only bound backend source. Structural map refresh invalidates stale asset evidence and restores button. Node fake DOM catches stale-response race. Existing `/api/dbvora` remains backward compatible and does NOT become trusted solely by health success.

## Evidence

- `tests/test_asset_attestation.py` 15 new synthetic source/protocol, approval and HTTP API cases. DB ID mismatches, size/size-scope drift, table/column/FK/relationship spoofing, provenance missing, unhealthy provider, source mutation while reading, links and lack of consent reject.
- `tests/test_hae_la_dbvora_asset_e2e.py` extended: genuine Lightning Azent user-approved synthetic CSV creates SQLite; selected source gets attested against a **contract HTTP fixture**, including disconnect preserving row state and SHA. This is **not running actual DBVORA**.
- `tests/test_ui_provenance.cjs` displays only safe count and SHA prefix; no path/row injection and old proof clears on failure/refresh. `tests/test_ui_races.cjs` 16 simulated races includes latest-reply-wins + pending-proof cancellation; `test_web.py` expected count updated to 16.
- Versioned distribution unchanged; known package parity tests `test_checked_in_zipapp_matches_current_hae_and_staged_la_sources`, `test_release_zip_matches_shipped_sources_and_executes_real_la_e2e` remain **2 FAIL** on both OS. No test skipped to hide failures. Full pipeline stops at Python, downstream steps not proven.

## Score and release boundary

Previous final-product provisional **73%**. Added +1 R-08 selected asset binding and +1 R-09 source/provenance/FK attestation + user-visible manual verification = **75% provisional**, not a percent of passing tests or customer readiness. Remaining **10%p** to 85 target. Missing: provider-neutral **persistent** registry, real DBVORA server+independently verified backup/restore, authorized Gmail/Sheets OAuth, 3 customer-style pilots, new versioned Windows distribution and actual customer environment. No customer data/OS permissions/paid APIs/OAuth, no original binary overwrite or production deployment.
