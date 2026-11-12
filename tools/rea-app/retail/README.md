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
