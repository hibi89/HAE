# REA_APP P95 target — actual file-deletion race repairs, safe Python zipapp

**Checked 2026-11-12 20:50 KST.** Private product `hibi89/HAE@feature/rea-app-kmong-owner-delivery-20261112`. Code/tests and their latest remote Git blobs checked at `ccfb96fc4b5f5fe424d97020119ccc6f0c28a313`.

## 1. Goal, original and product definition
REA_APP frozen P53 Python/JS/TS read-only static analysis + independent offline owner review/ZIP and candidate `.pyz`, targeting 95% owner-approved product completeness. Preserve original REA_APP branch, reports, private customer data and pre-existing output. Release remains explicitly HOLD pending entire source parser/Windows/customer gates.

## 2. Technical designs considered and decision
A. Continue automatic rollback by checking output inode/bytes before deletion: works on ordinary failures but a path can be replaced **between validation and unlink**, particularly at shared output paths; cannot credibly guarantee no deletion of another writer's data without OS-specific openat/handle-based atomic operations across Windows and POSIX.
B. **Never automatically delete output paths on a failed write or verification.** Preserve partial artifacts, require manual review, return fail-closed HOLD and refuse overwrite on retry. Zero additional dependencies, simpler cross-platform safety, no original input modification, explicit trade-off that partial outputs remain. **Selected B.** No real customer data or network operations needed.

## 3. Root cause and observed failure before correction
- Actual local temporary-directory proof: after `owner_delivery.build` wrote two review files, the output folder was renamed and replaced with a symlink to a completely unrelated directory containing `review.json`, `review.html`, `manifest.json`. On synthetic I/O error, old cleanup followed the replacement path and **deleted all three unrelated files** before raising `NotADirectoryError`.
- Actual separate ZIP writer proof: after exclusive `O_EXCL` archive creation, a test replaced the archive path with another writer's file before an injected `zipfile.ZipFile` failure. Old `archive.unlink(missing_ok=True)` **deleted the unrelated writer's file**.
- Even the prior `candidate_cli._rollback_owned` byte/inode checks were vulnerable to a check-then-unlink race, so it was not suitable as the last line of safety.
These are verified reproductions with synthetic temporary data, not assertions about an observed customer incident.

## 4. Implementation and failure behavior
- `retail/owner_delivery.py`: replaced unconditional output-file and directory removal on write failure with `DeliveryError` describing preserved partial directory. Never traverses another directory for automatic deletion on this path.
- `retail/package_delivery.py`: replaced unconditional failed-archive unlink with controlled `DeliveryError`, preserving any replacement or partial archive.
- `retail/candidate_cli.py`: removed automatic `_rollback_owned` and its check-then-delete race; validation errors return explicit HOLD and leave generated output untouched. Updated module description.
- `retail_qa/test_owner_write_rollback_safety.py`: two regression cases cover substituted directory plus partial original-folder preservation. Uses native `mklink /J` if run on Windows, ordinary disposable symlink on Linux; **the Windows branch itself has not been run**.
- `retail_qa/test_zip_write_failure_safety.py`: two real temporary filesystem failure cases cover replacement ZIP and partial archive preservation.
- Updated existing candidate/win-path tests to require fail-closed preservation, source immutability and no overwrite.

## 5. Local execution evidence, exact hashes and output
- Linux Python3.13.5: `python -m unittest discover -s retail_qa -p 'test_*.py' -q` **62 discovered, 60 PASS, 0 FAIL, 0 ERROR, 2 native Windows SKIP**; `python -O -m unittest discover -s retail_qa -p 'test_*.py' -q` **same 60 PASS + 2 SKIP**; `python -m compileall -q retail retail_qa` PASS.
- Git Blob checks against exact locally executed files:
  - `owner_delivery.py` `3ccff1d7d06079c7cfc3b59ed688bfbc2018f71c`
  - `package_delivery.py` `c2f6c5123edcea41387b951b24b5fbfdb22dcc39`
  - `candidate_cli.py` `5dd0d01b79c537291b721c48263ed1ce9b7a6b2b`
  - `test_owner_write_rollback_safety.py` `cc252b4db01b860833014f8215872f4ac0603639`
  - `test_zip_write_failure_safety.py` `71474154eadb1f059a739f6da17636796210272c`
  - `test_candidate_cli.py` `748ea908a58e1e7652c97def64cde053c8d05561`
  - `test_windows_reparse_guard.py` `6618be87b691f3a6fd4c80320d00d2b3e9a679a1`
- Updated **unsigned** offline Python zipapp `REA_APP_P95_offline_review_SAFE_20261112.pyz`: **10,388 bytes, SHA-256 `92001c97f721ac4a4131687a8f964d0a0d6a25c499c7ed4d6be549346b89ba4c`**. Two clean builds byte-identical; source SHA manifest verifies all three retail modules. Real independent subprocess invocation with synthetic reports produced a verified source-bound four-member buyer ZIP. Input report SHA unchanged. Second invocation into existing paths correctly exited 2/HOLD. This artifact is not a Windows EXE or approved commercial product.
- Prior protected Git source audit: original P53 `verify_gate_r.py` manifest 25/25 blobs matching Git trees. This proves source identity but **not executed P53 Gate R**.

## 6. Repositories, branches, versioning and rollback
Private `hibi89/HAE` feature `feature/rea-app-kmong-owner-delivery-20261112`, last function+test SHA `ccfb96fc4b5f5fe424d97020119ccc6f0c28a313` before docs; old feature source base `d8970cba645e375808b9683c1679e573d9a263cb` is a rollback reference. Frozen original analyzer `REA_APP@2fe581b683f6a49779e71058cddbfd165871593a` not edited. Central `hibi89/hackathon-command-center-2026@kmong-productization` completion roster retained.

## 7. Environment, triggers, cost and production
Explicit offline CLI only. Python>=3.11 distribution candidate, native Linux test 3.13.5. No API charges, npm install, hosted CI, new project, secrets, third-party transfer, production URL or Vercel deployment. Production **N/A**. Manual retry requires a fresh output path or deliberate owner review/cleanup; no overwrite.

## 8. Security, customer data, originals and backups
All injections use disposable synthetic data, no customer code. Failed writes intentionally leave partial files for review; report sources unchanged. This is an important preservation improvement, **not a promise against every filesystem race or sudden power loss**, and no ZIP or manifest is digitally signed. The previous package artifact with SHA `18dd72be46ee4c37be60ad9d96ca73c469001747f0c7fe209a20e99e4a928dae` is superseded; use the new safe candidate only for internal review. User must not treat it as commercial release.

## 9. P95 acceptance blockers and next steps
**P95 not achieved. REA_APP 85% provisional, RELEASE HOLD.**
1. Full original authorized P53 source checkout with exact installed `@babel/parser@7.29.9`: execute original `verify_gate_r.py` and `retail_qa/p53_acceptance.py` to prove actual 6/8 JS/TS analyzer reports → ZIP E2E. Current sandbox has neither full checkout nor npm access; previous full harness exits **2 BLOCKED**, not PASS.
2. Execute `retail_qa/strict_windows_gate.py` on actual Windows10/11 with native junction and real Edge/Chrome `file://` buyer tests, all tests unskipped and SHA evidence; currently two Windows tests SKIP on Linux.
3. Customer rights/licence/NOTICE/privacy, supported Python packaging, customer support and real buyer acceptance, explicit owner release approval. If a paid Windows CI runner is needed, seek prior authorization before triggering it.

## 10. Evidence time and completion decision
2026-11-12 20:50 KST; proven: two destructive races reproduced on temporary data and eliminated, 60 Linux scoped PASS with two Windows SKIP, seven source/test Git blobs matched, reproducible safe `.pyz` and synthetic buyer ZIP. **Unverified: original parser/Babel runtime Gate R, native Windows execution, buyer/commercial acceptance.** No unearned change to 85% final-product score or other 15 products.
