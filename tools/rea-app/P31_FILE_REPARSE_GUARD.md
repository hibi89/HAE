# REA_APP P31 — reject untrusted file types and Windows file reparse points (2026-10-27 KST)

## Goal, source and reproducibility
Repository `hibi89/AX_FLOW` private, branch `REA_APP`; reviewed base HEAD `ab8ff4f29cad65fdb581dd8dd9e6ab99da56a31b`, original verifier blob `91e81f6bf31820f7d690e0837ac7170403c212d4`, original test blob `d6b7bc8d56ff0ddd8f4d74958d62ac666ca6058a`. These files were already present in local isolated `/mnt/data/rea_gate_r_probe`; each was independently checked as an exact Git blob match before the change. New isolated test workspace `/mnt/data/rea_gate_r_p31`. No unrelated source or customer inputs.

## Reproduced issue
Existing `check_source` verified a manifest file with `Path.is_file()` and `Path.is_symlink()` but did not inspect Windows `st_file_attributes` for file reparse points. A synthetic test replaced `lstat()` metadata on a hash-correct file to represent (1) `S_IFREG` with `FILE_ATTRIBUTE_REPARSE_POINT` and (2) nonregular `S_IFDIR`. On the unmodified verifier the added regression failed **two subcases**: both unexpected acceptances.

## Alternatives and selected minimal correction
A. Keep `is_file/is_symlink`: no overhead, fails this synthetic attribute guard. Rejected.
B. **Selected**: use `Path.lstat`, `stat.S_ISREG`, and `FILE_ATTRIBUTE_REPARSE_POINT` exclusion for every reviewed file, before reading it. No new dependencies, no remote calls, minimal code and cost.
C. Fully materialize immutable source into a hardened isolated worktree and validate race-free handles. Higher I/O/maintenance, out of scope for this surgical patch.

## Actual test evidence
- Python 3.13.5 / Linux. Baseline P30 exact-source verifier self-suite: **8/8 PASS**.
- Added regression on original source: nine tests executed; **2 failing subcases** inside one added test, seven existing tests passing.
- Patched code + regression: `python -m unittest discover -s tests -p test_verify_gate_r.py -v`: **9/9 PASS, 0 errors, 0 skipped**; synthetic reparse and nonregular subcases rejected. The tests simulate Windows metadata; they **do not** demonstrate actual Windows junction/file-reparse behavior.
- Locally executed new verifier Git blob `e88665699d00b3f8c21c5ddddba880fc01f79d5f`; new regression Git blob `f1e9745e3139050e6ef10bf331c91f6431790136`. GitHub created the exact same blobs. The verifier's reviewed 14-file manifest now pins the new test Git blob. No analyzer scanner, graph, impact, CLI or Node parser code changed.
- Full REA_APP analyzer Python suite and genuine `@babel/parser@7.29.9` Node parser are **not run** in this environment: authenticated private checkout unavailable via container DNS and pinned npm package absent. REA_APP Gate R remains PARTIAL, not RELEASED. Check-then-read file races and mutable ancestor-directory attacks remain outside the static integrity guarantee.

## Next Gate R
On authorized complete exact GitHub checkout with installed pinned Babel parser, run `cd tools/rea-app && python verify_gate_r.py`. Require `SOURCE VERIFIED: 14/14`, full Python tests with PASS/FAIL/SKIP totals, actual dependency verification and real Node parser pass. Carry out physical Windows reparse fixture separately as permissions allow. Do not initiate paid/private Actions without approval.
