> **2026-11-12 native Windows P95 technical gate:** `python retail_qa/strict_windows_gate.py` (from `tools/rea-app` in a clean authorized checkout of `feature/rea-app-kmong-owner-delivery-20261112`) runs original 25-blob P53 Gate R, exact Babel7.29.9, real 6-/8-report→source-bound ZIP, **actual** Windows NTFS junction and Edge/Chrome `file://`, then standalone `.pyz`. No automatic downloads. Current Linux local run: **56 PASS / 2 native SKIP**, strict command returns **BLOCKED**, so **85% provisional / 95% NOT CERTIFIED / RELEASE HOLD**. [Gate details](../../../docs/REA_APP_P95_NATIVE_WINDOWS_FULL_GATE_20261112.md).

> **2026-11-12 P95 partial:** Corrupt DEFLATE streams now fail closed with `HOLD`/exit 2 rather than an uncaught `zlib.error`. New reproducible, Python3.11+ standard-library `.pyz` internal candidate bundles only three retail modules, entrypoint and unsigned source-SHA manifest (not original P53 analyzer or customer data). Exact-Git-blob Linux synthetic validation: **56 PASS / 0 FAIL / 0 SKIP**, also 56 PASS under `python -O`. Real P53 Gate R/Babel, native Windows file:// and sale approval remain **BLOCKED / UNVERIFIED**; product **85% provisional, P95 NOT CERTIFIED / RELEASE HOLD**. [Verification](../../../docs/REA_APP_P95_CORRUPT_ZIP_AND_PYZ_20261112.md).
>
> Offline internal build from `tools/rea-app`: `python retail/build_zipapp.py --archive NEW_DIRECTORY/rea-app-candidate.pyz`. Execute only with Python3.11+: `python NEW_DIRECTORY/rea-app-candidate.pyz --bundle PRIVATE_REPORTS --delivery NEW_REVIEW --archive NEW_REVIEW.zip`. **This is not a Windows EXE and is not approved for commercial distribution.**

> **2026-11-12 P95 Windows path-security update:** Source reports, source/output parents, delivery file creation, ZIP pack/verify and conditional rollback now reject NTFS reparse-point (including junction) attributes plus ordinary symlinks. Exact GitBlob-matched Linux/Python3.13.5 **50/50 scoped PASS** (also 50/50 under `python -O`); Windows reparse flags were **simulated**, actual native Windows and full P53/Babel Gate R have not run. Product remains **85% provisional / P95 NOT CERTIFIED / RELEASE HOLD**. [Evidence](../../../docs/REA_APP_P95_REPARSE_SAFETY_20261112.md).

> **2026-11-12 full P53 acceptance gate prepared (not run):** In an authorized complete repo checkout with pinned @babel/parser 7.29.9 already installed, run `cd tools/rea-app && python retail_qa/p53_acceptance.py`. It first invokes the original `verify_gate_r.py` source/Python/Node guard, then produces actual 6-/8-file synthetic P53 bundles and source-bound customer ZIPs twice to test determinism and privacy. In this sandbox the command **exits 2 BLOCKED**, as the original P53 analyzer tree is unavailable. New preflight tests plus prior local retail tests **41/41 PASS**; native Windows, genuine original P53 E2E and commercial acceptance are NOT VERIFIED. **85% provisional / P95 NOT CERTIFIED / RELEASE HOLD.** [Detailed evidence](../../../docs/REA_APP_P95_P53_GATE_HARNESS_20261112.md).

> **2026-11-12 P95 candidate acceptance update:** New `candidate_cli.py` performs the pre-existing four offline checks as a single explicit command, with no overwrite and conservative rollback limited to self-created byte+inode-matched outputs. Linux Python3.13.5 exact Git Blob 5/5 scoped **39 PASS/0 FAIL/0 SKIP** at code SHA `78f0906cb0e713733c1543728e75ed3641e9b2d2`. Original Gate R/Babel bundle, real Windows file:// and buyer/legal acceptance are still unverified; **85% provisional / P95 NOT CERTIFIED / RELEASE HOLD**. See `docs/REA_APP_P95_SINGLE_COMMAND_CANDIDATE_20261112.md`.
>
> Example from this directory: `python candidate_cli.py --bundle PATH_TO_PRIVATE_BUNDLE --delivery PATH_TO_NEW_OWNER_REVIEW --archive PATH_TO_NEW_REVIEW.zip`. A successful command means the offline candidate is verified against retained local reports, **not** approved for customer sale. On a suspected concurrent modification, manual inspection may be required; no crash-atomic guarantee.

> **2026-11-12 P95 safety retest:** whole ZIP is now compared against canonical deterministic bytes (hidden appended bytes prohibited); after owner preflight, `pack` revalidates the exact member bytes against fresh source report hashes/recalculated review. Linux exact-Git-blob scoped suite **32/32 PASS** at code SHA `31011f67eb8cacd56a5533e4602531ad38c47483`, not a full original Gate R/Windows/real buyer validation. Commercial progress remains **85% provisional / P95 NOT CERTIFIED / RELEASE HOLD**. [Evidence](docs/REA_APP_P95_ZIP_SECURITY_RETEST_20261112.md).

> **2026-11-12 P95 hardening in progress:** ZIP without `--bundle` now validates the strict, fixed-format review JSON ↔ generated HTML and HOLD fields in addition to unsigned hashes. **It still cannot prove provenance/authenticity**; use `verify-zip --bundle` against the owner's retained original reports. Six extra regression tests are committed, but the 29-case suite and original Gate R have not been run at the new feature SHA. Status remains **85% provisional / RELEASE HOLD**. See `docs/REA_APP_KMONG_P95_HARDENING_PARTIAL_20261112.md`.

# REA_APP offline owner delivery — engineering P85 candidate

This is an **optional** zero-network, Python 3.11+ companion for REA_APP v0.3.0's **existing** six/eight-report bundle. The original analyzer, source-pinned Gate R, pinned Babel/Node dependency, and frozen CLI remain unchanged. No analyzed source code, raw reports or source paths are included in the customer ZIP.

## Prerequisite

1. With legal permission for both source snapshots, run the original pinned REA_APP bundle to produce source-map.json, change-impact.json, and functional-contracts.json; correct parser syntax errors first.
2. Keep the original bundle folder private on the owner's PC. Choose **new** folder and ZIP paths outside the bundle and outside customer source roots.
3. Python >=3.11; no internet, npm installation, API, local server, credentials or paid service required for the standalone handoff.

## Owner commands

Run from tools/rea-app/retail:

~~~bash
python owner_delivery.py build --bundle PATH_TO_PRIVATE_BUNDLE --delivery PATH_TO_NEW_OWNER_REVIEW
python owner_delivery.py verify --bundle PATH_TO_PRIVATE_BUNDLE --delivery PATH_TO_NEW_OWNER_REVIEW
python package_delivery.py pack --bundle PATH_TO_PRIVATE_BUNDLE --delivery PATH_TO_NEW_OWNER_REVIEW --archive PATH_TO_NEW_REVIEW.zip
python package_delivery.py verify-zip --bundle PATH_TO_PRIVATE_BUNDLE --archive PATH_TO_NEW_REVIEW.zip
~~~

The buyer reads review.html offline. Optional verify-zip without --bundle only tests internal **unsigned** SHA consistency, not true origin/authenticity. Owner-side --bundle checks exact source-report SHA and recomputes review contents. SHA is not a signature.

## Output and safety

Owner review: review.html (fixed Korean labels, numeric counts, CSP, no JS), review.json (aggregate counts only), manifest.json (SHA-256 of three selected reports plus outputs). ZIP contains those three files plus a fixed README.txt. Repeated outputs have byte-stable ZIP member metadata.

Unknown schemas, malformed counts, inconsistent snapshots, syntax errors, changed reports, modified outputs, overlap, symlinks, oversized files, extraneous/duplicate ZIP names, and existing output targets fail closed. Originals remain read-only. No external requests, account changes, production deployment, or data upload.

## Tests

~~~bash
cd tools/rea-app
python -m unittest discover -s retail_qa -p 'test_*.py' -v
~~~

These are independent companion tests, **not** substitutes for the frozen original Gate R+QA. Full source+wheel Gate R, actual Windows10/11 Chrome/Edge file navigation, third-party rights, customer sale, signing, installer and support remain separate gates. Sale/release remains **HOLD**.
