# REA_APP P37 — POSIX FIFO swap guard, focused regression (2026-10-27 KST)

## Change
- Issue: [#1](https://github.com/hibi89/AX_FLOW/issues/1); owner continuation `ㄱ` selected previously recommended zero-dependency option A.
- `rea_app/scanner.py`: add `getattr(os, "O_NONBLOCK", 0)` to source open flags, preserving `O_NOFOLLOW`, `fstat` regular-file and inode checks, strict snapshot validation and all prior source exclusion rules.
- `tests/test_scan_open_races.py`: new bounded (3-second subprocess) synthetic FIFO replacement test and unchanged regular JS/TS file regression.
- Review: option A minimal `O_NONBLOCK` on supported POSIX with negligible normal-file overhead (selected); option B descriptor-relative isolated filesystem snapshot with higher complexity (defer); option C no fix and possible infinite wait (rejected). No customer permissions, data, paid service, repo rename, other product code or Vercel settings altered.

## Provenance and test evidence
- Previously reviewed remote scanner original Git blob `09bf5df2ade638be69ea1dc26d6383af8c23a20d` and test blob `0601539e0a57807441fa31373339c689b2aa7439` were reconstructed **byte-for-byte** in isolated Linux Python 3.13.5, with independent Git blob SHA match.
- Adding the regression before applying the fix led to **3 passed, 1 failed by `subprocess.TimeoutExpired` at 3 seconds**, demonstrating a real hang in `walk_source` when an ordinary input is swapped to a FIFO just before `os.open`.
- After one small scanner change: `PYTHONPATH=<temp>/rea_p37 python -m unittest discover -s tests -p 'test_scan_open_races.py' -v` → **4/4 PASS**.
- Reconstructed existing GitHub-byte-matched sensitive exclusions test `3f40479907fe923137f9c018a57b2d3df08ba023` and snapshot integrity test `a309e31b5b6c015d993fe39da90fcf93088261f0`. Run `PYTHONPATH=<temp>/rea_p37 python -m unittest discover -s tests -p 'test_scan_*.py' -v` → **11/11 PASS, no fail/error/skip**. Executed against patched scanner matching remote Git blob.
- Updated/published changed scanner blob **`ac3b5960378924c29e24c87cc58b67c315818c8a`**, updated race-test blob **`59aa669caadcbb31fc5a96629002196728c31a80`**; exact byte hashes verified against executed local copies.
- `verify_gate_r.py` now pins these two blobs; verifier blob **`8482322aef918c22787062aac5d4ca8549a20ea9`**; `run_gate_r_evidence.py` pins that verifier blob, runner blob **`51b4c8b6de26d4720911a766aeb5962649ecafe2`**. Remote full tree 16/16 pinned file IDs match, zero extra analyzer/test executable files.
- New code commit `6f44fba8dab2e14b8f50b4bc9309d3112d23e2ff`; race test `1e5fc9bec55a53788cc9d3a68cf696666026313e`; verifier `9ae065be61e15c2a9d5829d74032b9750408a721`; runner `8a9cf035eecad14ad105853f38cb681a66005120`.

## Scope and remaining gates
- Actual test environment Linux/Python **3.13.5**; observed Node runtime 22.16.0, `@babel/parser` returns **NOT_INSTALLED** here. **No complete 16-file Python graph/CLI/impact suite, genuine Babel@7.29.9 suite, Windows native FIFO/reparse/junction, hostile ancestor swap, production/browser or customer run completed.** Gate R remains **PARTIAL**.
- The source remains a local CLI; Vercel production N/A. No source upload to third parties, n8n source use or credential collection. Existing Git history is rollback.
- Next safe gate: on authorized clean complete `REA_APP` checkout with already approved exact `@babel/parser@7.29.9`, run `cd tools/rea-app && python run_gate_r_evidence.py`; capture source 16/16, full Python PASS/FAIL/SKIP, Node parser PASS and exit 0, clean branch SHA and Windows caveats. Do not label narrow 11/11 as full Gate R signoff. Avoid repeating blocked anonymous private clone or creating potentially paid CI without authorization.
