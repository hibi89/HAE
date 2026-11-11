# HAE P6 — independent SHA-pinned SQLite recovery-chain verifier

**Date:** 2026-11-11 KST  
**Repo:** `hibi89/HAE@feature/axflow-mvp`  
**Exact tested source SHA:** `3db947023f9034ab9e6257ce503a4872c23c7b31`  
**CI evidence:** https://github.com/hibi89/HAE/actions/runs/42982504012  
**Result:** GitHub-hosted Windows+Ubuntu, each Python **233 executed = 224 PASS / 2 FAIL / 7 SKIP / 0 ERROR**. Node22 UI race **16 PASS**. Both Actions jobs **FAILURE** only due checked-in old release ZIP/pyz source-parity tests.

## Safety design

Option A: integrate self-initiated backups/restores into a network GET/DBVORA inspection. Maintenance coupling and accidental side effects are unacceptable. Option B (selected): a separate, explicitly invoked **read-only synthetic-only** CLI, verifying *already created* owner-selected closed SQLite source/backup/restore paths. Cost zero external services, bounded to 32 MiB per source, streaming/hash-based local processing.

Function: `axflow.business_recovery_chain.verify_synthetic_restore_chain`. Pins exact provided source & backup SHA256 and requires three different ordinary nonlinked source files with no SQLite sidecars, corrupted DB or unsupported objects. Uses existing `schema_inventory.inspect_offline_schema` for read-only integrity/FKs and stable provenance, then independently streams SQLite `iterdump` statements into length-prefixed SHA256 to detect row content changes even if schemas are identical, followed by second scan and stable file stat/identity checks. Never returns SQL/rows/absolute paths/dumped content; errors return `RecoveryChainError` with fixed path-free diagnostic. Receipt says `independent_restore_verified:true` only after success; `dbvora_real_process_verified:false`, `customer_ready:false`, `release_gate:HOLD`.

Usage (for **explicitly owner-approved synthetic files only**; source/backups must already exist):

```
cd apps/ax-flow
python -m axflow.business_recovery_cli --source ABS_SOURCE --backup ABS_BACKUP --restored ABS_RESTORED --source-sha256 64_HEX --backup-sha256 64_HEX --synthetic
```

This verifier **does not generate backup/restore files** or connect to HTTP. Separate existing `backup_business_state` / `restore_business_state_pinned` have explicit fresh-path no-clobber rules; tests invoke them on disposable synthetic fixtures only.

## Executed tests

- New `tests/test_business_recovery_chain.py` **13 tests**: good recovery + no plaintext, deterministic read-only repeat, invalid/no-consent SHA pins, duplicate/relative/linked paths, same-schema altered restored row, mutated backup, schema divergence, SQLite sidecar, corrupt restored file, injected source-write race, CLI success/failure no path leak.
- Extended `tests/test_hae_la_dbvora_asset_e2e.py` +1: HAE browser-like HTTP preview→explicit approval→genuine independent Lightning Azent engine creates synthetic business SQLite→HAE DBVORA **contract fixture** inventory source attestation→business offline backup to **new** path→SHA-pinned restore to different **new** path→independent recovery-chain schema/rows proof→durable workflow status and unmodified source SHA. This is *real LA engine*, not actual independent DBVORA process.
- Initial symlink bypass caused 1 Ubuntu failure at source `fcbbfb7`, corrected via supplied path preservation before scanner check `a7c4fb4`. Initial integration E2E checked a non-existent SQL `name` column and 1 table count; corrected at `3db947023f9034ab9e6257ce503a4872c23c7b31` to LA real `csv_records.payload_json`, `row_number`, at least one table. Final Windows/Ubuntu E2E PASS.
- Two inherited release blockers: `test_shipped_package.*zipapp_matches_current_hae_and_staged_la_sources` and `test_release_zip_matches_shipped_sources_and_executes_real_la_e2e`. No skip, no overwrite or unauthorized new candidate.

## Completeness and next gates

HAE prior product score75; verified independent synthetic recovery chain and true LA-to-backup-restore integration +2%p **77% provisional**, **85% target still 8%p away**. This *does not* establish real DBVORA backend integration, production customer data recovery, signed/characterized packaging or Google OAuth/Sheets/Gmail. Original release archives unchanged, customer secrets/permissions unmodified, Vercel N/A, **RELEASE HOLD**.
