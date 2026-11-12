# REA_APP P95 target — corrupted ZIP fail-closed + deterministic Python zipapp candidate

**KST:** 2026-11-12. **Product:** `hibi89/HAE` / `feature/rea-app-kmong-owner-delivery-20261112`.
**Code/test checkpoint:** `53bc6edab84c4d2f78a35fe5fbb0e2be0d55f1e9`. **Final product rating: 85% provisional, 95 NOT certified, RELEASE HOLD.**

## 1. Product goal / confirmed scope / stack
Complete an offline, owner-approved buyer review workflow for REA_APP v0.3.0/P53 without touching its frozen original JS/TS static analyzer. Python >=3.11, stdlib-only retail companion, local synthetic report input, no cloud/network or customer-source redistribution.

## 2. Alternatives considered and decision
- **A: Windows EXE/PyInstaller now**: easier for buyers without Python but adds external build dependencies, antivirus/signing burden, binary provenance and native Windows acceptance. Not appropriate while original P53 and physical Windows remain blocked.
- **B: standard-library deterministic Python `.pyz`**: one file, zero new dependencies, tiny artifact and explicit source manifest; requires local Python >=3.11, not an EXE. **Implemented B** for internal validation only.
- The corruption repair does not need an alternative redesign: catch actual `zlib.error` and `EOFError` within the pre-existing bounded `zipfile` reader and convert to the existing `DeliveryError`/HOLD contract.

## 3. Data flow, security and implementation
Explicit local input `source-map.json`, `change-impact.json`, `functional-contracts.json` → source hash & schema validation → aggregate owner review HTML/JSON → deterministic four-member review ZIP → source-bound independent verification.
- Previously, flipping a byte inside the compressed `review.json` stream caused uncaught `zlib.error` and CLI exit 1/traceback. Now `package_delivery.verify_zip` catches compressed-stream corruption and returns controlled `HOLD` / exit 2. No reports modified.
- New `retail/build_zipapp.py` packages exactly `__main__.py`, `candidate_cli.py`, `owner_delivery.py`, `package_delivery.py`, `MANIFEST.json` into a reproducible standalone `.pyz`, with fixed member ordering/metadata and SHA-256 manifest bound to the three included source files. No original P53 parser, customer source/reports, secrets, model or API keys.
- Existing output targets are refused; output path symlink/Windows reparse ancestor checks retained; no unknown dependencies or paid service. Failure leaves any suspicious partial file for manual inspection rather than deleting somebody else's file. Unsigned manifest is integrity evidence, not cryptographic signing or customer approval.

## 4. Actual tests / exact SHA
- Before fix: **2 tests authored; 1 FAIL + 1 ERROR**. Real compressed ZIP byte corruption reproduced uncaught `zlib.error` and subprocess traceback/exit 1.
- After fix: Linux Python3.13.5 `python -m unittest discover -s retail_qa -p 'test_*.py' -q` **56 PASS / 0 FAIL / 0 SKIP**; `python -O -m unittest discover -s retail_qa -p 'test_*.py' -q` **56 PASS / 0 FAIL / 0 SKIP**; `python -m compileall -q retail retail_qa` **PASS**.
- New ZIP corruption tests **2**, real `.pyz` creation/runtime/byte reproducibility/preservation tests **4**. Actual zipapp invoked in a separate temporary directory; original synthetic reports unchanged, buyer ZIP independently verified, rerunning into preexisting destination correctly blocked.
- Direct offline zipapp built at 2026-11-12 KST: SHA256 `18dd72be46ee4c37be60ad9d96ca73c469001747f0c7fe209a20e99e4a928dae`; 5 members; ~12 KiB on disk (precise bytes should be checked on the target runtime); `python candidate.pyz --help` works.
- GitHub remote source Blob IDs equal exact locally executed files:
  - `retail/package_delivery.py`: `00304bc15b478118e0cdb70f2ed848f75c73ad23`
  - `retail_qa/test_corrupt_zip_deflate.py`: `a13e558930c41aea5a31115945bd04803b89b859`
  - `retail/build_zipapp.py`: `7dd3a6a842acc3aeb3744cc1e4c08fed96caa2af`
  - `retail_qa/test_zipapp_delivery.py`: `20ec7458b552ca2cec81c8d93eb1fb1e8e717d37`
- Full original P53 Gate R, exact Babel7.29.9, true P53-generated 6/8 bundle, GitHub-hosted CI, actual Windows10/11 junctions and Edge/Chrome file:// **NOT RUN**. Local container lacks complete original private checkout and cannot connect to GitHub/npm; the existing full-gate harness exits **2 BLOCKED**. No claim that 56 scoped tests constitute full customer acceptance.

## 5. Completion / release state
**85% provisional unchanged / 95 target NOT met / RELEASE HOLD / sale NO-GO.** This is measurable defect repair and offline packaging improvement, not a final market-ready program or signed Windows installer. Do not promote based on test-count increase alone.

## 6. Repository / branch / source / rollback
Private `hibi89/HAE@feature/rea-app-kmong-owner-delivery-20261112` at source checkpoint `53bc6edab84c4d2f78a35fe5fbb0e2be0d55f1e9`. Frozen original `REA_APP@2fe581b683f6a49779e71058cddbfd165871593a` unchanged. Previous patch `043938bdb8ca4c3802de16622898f4ed93d30004` is rollback baseline; no force push, merge, new repo or global Git identity modifications.

## 7. Commands / environment / production
At authorized source checkout:
```bash
cd tools/rea-app
python -m unittest discover -s retail_qa -p 'test_*.py' -v
python retail/build_zipapp.py --archive NEW_PATH/rea-app-review-candidate.pyz
python NEW_PATH/rea-app-review-candidate.pyz --bundle REPORTS --delivery NEW_REVIEW_DIR --archive NEW_REVIEW.zip
python retail_qa/p53_acceptance.py
```
No Vercel/Production URL (N/A offline-only). The tested `.pyz` is Python-based, not a self-contained EXE. Distribution, signing, personal customer data and paid CI require separate approval.

## 8. Originals / privacy / backup
No original analyzer branch, customer source, authentication, permissions, billing, licensed n8n code or production changed. Synthetic fixtures only. Local artifact stored in temporary working space for test, not treated as permanent user release. Source commit and matching Blob IDs provide rollback/integrity references.

## 9. Next actions / gates
1. Obtain an authorized **complete** private P53 checkout/runner with installed pinned Babel7.29.9; run `verify_gate_r.py`, original QA and `p53_acceptance.py` to verify actual 6/8 reports → packaged buyer review, source preservation and deterministic output.
2. Real Windows10/11 Python3.11 + Edge/Chrome offline file:// + native NTFS junction, ZIP extract/run and archive hardening; review customer rights/NOTICE/signing/support/pilot.
3. Only then evaluate actual 95 score and owner-approved paid/commercial release. Do not imply original P53 or buyer P95 is verified from local 56 tests.

## 10. Time and proof boundary
2026-11-12 KST. Functional code + 56 scoped Linux tests and exact Git Blobs **VERIFIED**. Full original Gate R, native Windows, CI and buyer outcome **BLOCKED/UNVERIFIED**. Central Kmong roster should retain REA_APP 85 provisional and other products' values unchanged.
