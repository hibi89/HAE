# REA_APP P95 target — Windows reparse-point safety guard (2026-11-12 KST)

## 1. Goal / requirements / stack
Strengthen the REA_APP offline customer-delivery companion against Windows NTFS directory junctions and other reparse-point paths. Preserve the original REA_APP v0.3.0/P53 frozen analyzer and independent P85 evidence. Python >=3.11 standard library, local-only explicit commands; no network/credentials.

## 2. Alternative designs and decision
- **A — rely on Path.is_symlink()**: simplest and zero added code, but Windows directory junction/reparse attributes are not guaranteed to appear as a conventional symlink. Incomplete fail-closed behavior.
- **B — metadata-based single guard**: use `lstat` and `stat.FILE_ATTRIBUTE_REPARSE_POINT` (fallback 0x400) plus conventional `Path.is_symlink()` with propagation of permission errors. Apply identically to source files, all parent directories, output target paths, ZIP input/output and rollback. **Selected B**: low-cost, no dependency; Windows runtime still requires native verification.

Trigger/data flow: owner reads P53 three v1 JSON reports from explicitly approved local root → emits fixed aggregate review files → source-verifies and creates canonical ZIP → verifies ZIP against original reports → conditional rollback on failure. New validation applies before external filesystem writes; no implicit retries, cloud service or customer-source modification.

## 3. Actual implementation
Modified only the independent retail companion (not the frozen analyzer):
- `tools/rea-app/retail/owner_delivery.py`: `_is_link_or_reparse` checks actual `lstat` attribute flag plus symbolic links. Missing *new output targets* are permitted; access errors propagate. Protected source file `_regular_file`, source directory with ancestors, and destination path/parents.
- `tools/rea-app/retail/package_delivery.py`: both new ZIP output path and existing ZIP verification reject symlink/reparse-point ancestors.
- `tools/rea-app/retail/candidate_cli.py`: rollback refuses to traverse/delete a delivery directory that has become a link/reparse point; preserve suspicious content for manual review.
- New `tools/rea-app/retail_qa/test_windows_reparse_guard.py`: nine portable regressions: simulated Windows NTFS flag, safe missing new name, permission denied, linked source ancestor, linked source file, linked output ancestor, ZIP output ancestor, ZIP verification ancestor and rollback replacement preservation.

## 4. Exact validation (local executed)
Private product branch `hibi89/HAE@feature/rea-app-kmong-owner-delivery-20261112`; feature+QA commit `043938bdb8ca4c3802de16622898f4ed93d30004`. Four GitHub source blobs were verified to match the exact executed local bytes:
- `owner_delivery.py` `97f7e731a9b1ffa49dc90d18aee2fb747c5a61f7`
- `package_delivery.py` `d14dd51481dbae0bc8da8c46f0a24137bb3a51ce`
- `candidate_cli.py` `a77d86e07e8c8a66c07679f2ed29bfe3ea6c3b62`
- `test_windows_reparse_guard.py` `780c647b87704ccb4676efd953147ab9ac16e4c4`

Linux Python3.13.5, `cd /mnt/data/rea_app_recovery && python -m unittest discover -s retail_qa -p 'test_*.py' -v` **50 PASS / 0 FAIL / 0 SKIP** (previous 41 + new 9); `python -O -m unittest discover -s retail_qa -p 'test_*.py' -q` **50 PASS / 0 FAIL / 0 SKIP**; `python -m compileall -q retail retail_qa` PASS. These runs exercise actual local files/subprocesses and simulated reparse metadata; **not physical native Windows junction handling**.

Original `python retail_qa/p53_acceptance.py` **exit 2 BLOCKED** (missing authorized full `tools/rea-app/rea_app/cli.py` and `babel_parser_adapter.cjs` checkout). Container DNS does not resolve github.com; isolated source files came from authenticated GitHub connector, not a full private repo clone. Node22.16/npm10.9 available but pinned @babel/parser7.29.9 not installed; no dependency download attempted.

## 5. Completion / stop
**REA_APP = 85% provisional engineering unchanged; P95 NOT ACHIEVED; RELEASE HOLD/SALE NO-GO.** Scoped security correctness improved, but these 50 synthetic/Linux checks alone do not prove original P53 static-analyzer Gate R, true P53 6/8-report E2E, native Windows junction / physical file:// or buyer installation. Do not count source simulator as actual Windows verification.

## 6. Repositories / branch / SHA / paths
Private `hibi89/HAE@feature/rea-app-kmong-owner-delivery-20261112` functional SHA `043938bdb8ca4c3802de16622898f4ed93d30004`; original `REA_APP@2fe581b683f6a49779e71058cddbfd165871593a` and P53 reviewed `1ae3dac263a1a5c866434c8418fe7dbb1d3f1d48` preserved. Product status/handoff docs updated separately; central `hibi89/hackathon-command-center-2026@kmong-productization` roster 16 preserved.

## 7. Deployment / environment
Vercel/Production **N/A** (offline product). Tested Linux/Python3.13.5. Production Windows10/11, offline file:// Edge/Chrome, GitHub CI, executable wheel/installer and business acceptance **NOT VERIFIED**. No paid CI triggered.

## 8. Originals, backup, security
Original analyzer and other branches untouched; synthetic test data only, no customer code/secrets uploaded or packaged. Source commit preceding this change is rollback point; no force push, merge, access/visibility, payment or remote deployment changes. ZIP SHA remains unsigned integrity, not provenance/signing.

## 9. Next gates / authorization
1. On authorized full private checkout, execute source-pinned `python verify_gate_r.py`, full QA and `python retail_qa/p53_acceptance.py` against installed exact Babel parser, then audit actual 6/8 generated report→buyer ZIP and source-immutability proof.
2. On real Windows10/11, create disposable actual NTFS junction and reparse fixtures in temp folders, run all retail 50 tests and physical Edge/Chrome `file://` buyer ZIP extraction and offline review; compare PASS/FAIL/SKIP.
3. Rights/NOTICE/privacy, signed or characterized distribution, customer pilot, support/refund and owner commercialization approval; assess 95% only with evidence. Paid CI/dependency install/real customer data and launch still require approval.

## 10. Timestamp and validation scope
2026-11-12 KST. GitHub commit and four exact source blobs confirmed; Linux standard + optimized-mode scoped 50/50 PASS, original P53 integration exit2 BLOCKED, physical native Windows and hosted CI UNVERIFIED. No 95% or release claim.
