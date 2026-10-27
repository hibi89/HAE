# REA_APP P30 — Gate R parent-directory link guard (2026-10-27 KST)

## Scope / provenance
Private repository `hibi89/AX_FLOW`, branch `REA_APP`; code parent HEAD `20c4f5b6f4631d86436bd8c16ece953b06472650`.
The original `verify_gate_r.py` (Git blob `309510bd01aa01dc8ee6b2defb5498aebc67b0e1`) and `tests/test_verify_gate_r.py` (Git blob `c8db5c2957cc365d6e3c4c6cfcc70d5f1351d7fc`) were recreated in isolated local Linux/Python 3.13.5 and matched exact Git object hashes before editing. No external app source or customer data was used.

## Reproduced failure
The prior `check_source()` checked symlink status on each manifest *file* but not the `rea_app/` and `tests/` parent *directories*. Moving an otherwise identical directory and replacing its original path with a directory symlink left all child Git hashes identical and the verifier wrongly accepted it. The new synthetic regression has two subcases, one per directory. **Before fix: 1 new test failed, 2 failed subcases**, correctly detecting the oversight; 7 existing tests remained green.

## Fix and design options
- A: Continue final-file symlink checks alone. Zero code change, but linked directory traversal remains accepted: rejected.
- B: **Selected**: fail closed with `Path.lstat()`, `stat.S_ISDIR`, and Windows reparse-point attribute before opening any protected source; constant number of checks, Python standard library only, zero paid service/dependency and minimal maintenance.
- C: Copy whole source into an independent sandbox before testing. Stronger isolation against mutable ancestors but higher I/O and implementation/maintenance cost; deferred pending full integration runner.

Added a new regression with `rea_app/` and `tests/` directory-link subcases and updated the verifier's reviewed test SHA. Existing analyzer graph, scanner, CLI, user data and AX FLOW/HAE code untouched.

## Executed evidence
- Reconstructed old source and test matched exact original Git blobs; local prepatch verifier self-suite: **7/7 PASS**.
- New test against old verifier: **8 total tests, 2 failed subcases** (both unexpected acceptance); confirms actual reproducer.
- Fixed source plus new test: Python 3.13.5/Linux `python -m unittest discover -s tests -p test_verify_gate_r.py -v` — **8/8 PASS, zero skipped/fail/errors**.
- Exact edited local Git blobs `91e81f6bf31820f7d690e0837ac7170403c212d4` (verifier) and `d6b7bc8d56ff0ddd8f4d74958d62ac666ca6058a` (test) were compared with independently created GitHub blobs and matched exactly.

**Limits:** This verifies just the verifier module and its self-test, not the full 14-file Python analyzer, genuine installed `@babel/parser@7.29.9` Node suite, nor actual Windows junction operation. `lstat` prechecks do not eliminate races from attacker-writable ancestors between check and test execution. Gate R remains **PARTIAL**. Do not label the simulated parser metadata self-tests as real Babel parser runs.

## Next
Run `cd tools/rea-app && python verify_gate_r.py` in an authorized byte-identical complete checkout with approved installed Babel 7.29.9; capture 14/14 source, all Python PASS/FAIL/SKIP, real Node parser PASS, OS/versions/HEAD. Explicitly test Windows junction when permissions permit. Do not initiate private-repo paid GitHub Actions without approval, access restricted n8n source, or make HAE release claims.
