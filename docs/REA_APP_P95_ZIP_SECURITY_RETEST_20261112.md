# REA_APP P95 target: ZIP integrity and race-hardening verified — 2026-11-12 KST

## 1. Goal / confirmed requirements / stack
Continue existing P85→P95 retail-readiness track for frozen REA_APP P53 v0.3.0. Python >=3.11 companion consumes locally authorized source-map/change-impact/functional-contracts v1 reports and packages a no-network static Korean review. Preserve source and original analyzer.

## 2. Decision / design alternatives
A. Modify P53 source/ship integrated Windows buyer installer: best eventual distribution, but large freeze-regression/CI/privilege/license cost; original private checkout and native Windows unavailable here.
B. Patch independent retail companion with exact-byte ZIP validator and pre-write source-checked snapshot: small, zero API/hosting cost, keeps P53 frozen and report schemas intact. **Selected B** for concrete integrity blockers.

Data flow: authorized local report bundle → owner build/verify (read-only originals) → four fixed-name ZIP entries → canonical ZIP byte comparison and optional source-pinned verify-zip. Changes are fail-closed; files created with exclusive mode; no remote upload or global exactly-once promise.

## 3. Reproduced defects and fixes
- **ZIP trailing payload bypass**: after valid pack, append `FORBIDDEN_SECRET_OUTSIDE_ZIP_CENTRAL_DIRECTORY`. Previous `verify_zip` erroneously returned success because ZIP parsers tolerate bytes after central directory. Fix: recreate canonical ZIP (fixed entry names, metadata, compression level, timestamp) in memory and compare **whole archive bytes**, blocking hidden appendages, modified headers/comments and noncanonical member metadata.
- **Preflight-to-pack race**: `owner.verify` checked original delivery, but `pack` re-read review bytes later. A simulated swap after preflight made former `pack` return success while manifest referred to different bytes. Fix: re-read three original source reports after capturing exact ZIP member bytes, recompute aggregate review/HTML and expected manifest, and require exact byte equality before creating archive.
- **P53 schema compatibility guard**: added a bounded synthetic test of extended `graph.py` / `impact.py` / `contracts.py` v0.3.0 summary keys and owner ZIP round-trip. This is a schema-shaped test, not a real Babel-generated bundle.

## 4. Exact SHA / executed tests
- GitHub private product branch `hibi89/HAE@feature/rea-app-kmong-owner-delivery-20261112`, function + QA **SHA `31011f67eb8cacd56a5533e4602531ad38c47483`**.
- Independently reconstructed **three exact source files**, Git blob SHAs matched GitHub:
  - `retail/owner_delivery.py`: `810bceeffb3b605b911592adeec1f4f7e0c8be2c`
  - `retail/package_delivery.py`: `42ec1e1241cf5423669518d4ca45a81cebb6ded2`
  - `retail_qa/test_customer_delivery.py`: `e12e21a18dc6c3a5148e7cad3c0a3d632d545c68`
- Linux Python3.13.5 **`python -m unittest discover -s retail_qa -p 'test_*.py' -v` → 32 PASS / 0 FAIL / 0 SKIP (3.697s)**, `python -m compileall -q retail retail_qa` PASS.
- Before race fix: **31 pass / 1 FAIL** (intentional new regression reproduced). After fix 32/32 PASS. Before trailing-byte fix, crafted ZIP incorrectly passed source-linked verification; after fix regression PASS.
- Browser: real Chromium via Playwright attempted `file://` → **net::ERR_BLOCKED_BY_ADMINISTRATOR**. Direct file navigation NOT VERIFIED. Prior static `set_content` 9 rows at P85 older code SHA remains historical only.
- GitHub Actions combined statuses/PR workflow runs at preceding ZIP code SHA: 0/0. Hosted CI at final SHA not executed. Native Windows customer file://, original full Gate R/QA, pinned Babel and real P53-generated bundle NOT RUN.
- Original graph/impact/contracts v1 source-code shapes inspected read-only through authenticated GitHub connection. No source copied into public hub.

## 5. Status and release boundaries
**85% provisional remains; 95% NOT ACHIEVED; RELEASE HOLD / SALE NO-GO.** Concrete security + scoped verified code progress, but no complete original app regression, Windows buyer packaging, third-party license/NOTICE, customer pilot or approval. No claim of installed wheel/production validation.

## 6. Repository / branch / rollback
Private `hibi89/HAE` branch `feature/rea-app-kmong-owner-delivery-20261112`; tested source `31011f67eb8cacd56a5533e4602531ad38c47483`. Previous retail source security patch `a909341800bcdc160228889a6ea444e69330469d`; frozen original `REA_APP@2fe581b683f6a49779e71058cddbfd165871593a`; no merge/main/source-analyzer edits. Git history provides revert baseline.

## 7. Production / environment
No Vercel or Production applicable. Local Linux Python3.13.5 synthetic tests only; current sandbox disallows direct file:// Chromium navigation and cannot resolve github.com for private git clone. Connected GitHub file reads/writes and source blob identity checks succeeded. No paid runner.

## 8. Original source, security and privacy
Only synthetic fixtures. No real customer source, secrets, n8n code, data migration, permissions, license or visibility settings, paid CI, outside transmission, original branch edits, or deployment. Unsigned SHA receipts provide integrity only (not origin authentication). Canonical ZIP validation does not replace an owner signature or private source re-verification.

## 9. Next ordered gates and owner approvals
1. Full authorized private checkout on a supported machine/CI. Run `cd tools/rea-app && python verify_gate_r.py && python -m unittest discover -s qa -v && python -m unittest discover -s retail_qa -p 'test_*.py' -v` at exact code SHA, compare latest P53 source manifest and skip count.
2. Create actual synthetic P53 v0.3.0 `bundle --with-diagram` from two input source folders; run owner build/verify and ZIP pack / source-linked verify; inspect source bytes unchanged and ZIP contents.
3. Physical Windows10/11 Chrome/Edge `file://`, Python 3.11 install/package, rights/NOTICE, buyer support and owner-approved mock pilot; only then review 95 acceptance. Costs, customer data, rights/licensing and release need separate approval.

## 10. Timestamp / evidence scope
2026-11-12 KST. The 32 PASS apply to an exact-Git-blob-matched **retail three-file subset** rather than the full HAE/REA_APP checkout or GitHub-hosted CI. This document is a verified partial security gate, not a P95 completion claim.
