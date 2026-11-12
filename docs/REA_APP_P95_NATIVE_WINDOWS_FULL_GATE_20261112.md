# REA_APP P95 target — native Windows full-acceptance gate prepared

**2026-11-12 KST.** Private GitHub repo: `hibi89/HAE`; branch: `feature/rea-app-kmong-owner-delivery-20261112`. Source/test implementation SHA `3889f932f15d11d1497f69e458ecb978072427c8`.

## 1. Product goal and stack
REA_APP v0.3.0/P53 original static analyzer (read-only Python >=3.11, Node, pinned `@babel/parser@7.29.9`), independent zero-network customer review/ZIP and Python `.pyz` companion. Explicit user target: **95%**, but completion must depend on execution proof, not number of test cases.

## 2. Approaches compared and choice
A. Hosted GitHub Actions with `windows-latest` + dependency installation: feasible genuine Windows test but may incur private-runner minutes and external dependency pulls; user has not separately approved paid CI or changes to workflow triggers. **Not started**.
B. Native Windows local strict gate using a full authorized existing checkout: no new CI/hosting charge or permission change; minimal single command; explicitly fails if source, Babel, native browser or NTFS junction unavailable. **Implemented B**.
No original parser, existing Gate R, production config, credentials, cloud project or main branch changed.

## 3. New code and execution path
- `tools/rea-app/retail_qa/test_windows_native_acceptance.py`: **2 actual Windows-only tests**, not simulations. One creates a disposable NTFS junction via `cmd /c mklink /J`, asserts the real reparse attribute and owner-side rejection, verifies the target is preserved, removes just the junction. The other creates synthetic local P53-shaped v1 reports, generates owner HTML, launches installed Edge/Chrome headlessly at its actual `file://` URL with a fresh temporary browser profile, verifies HOLD text, CSP and non-disclosure of a synthetic private filename, rehashes original reports.
- `tools/rea-app/retail_qa/strict_windows_gate.py`: single-command orchestrator checks physical Windows, Python >=3.11, complete source tree, expected feature branch, clean tracked checkout and exact Git SHA. Discovers **at least 58** retail cases including both required native test IDs; fails if any error, failure or skip. Calls existing `p53_acceptance.perform()`, which first runs the frozen `verify_gate_r.py` source/entire Python suite/exact Babel7.29.9 test gate and then genuinely generates six- and eight-report P53 bundles, produces/independently validates source-pinned retail ZIPs, checks non-disclosure, source immutability and deterministic reruns. Finally builds/runs an actual `.pyz` on Windows and emits a proof JSON with Git SHA. Does not install dependencies, transmit data or auto-publish. Even on technical PASS, return verdict is `TECHNICAL_GATE_PASS_RELEASE_STILL_HOLD` until commercial rights/customer acceptance.
- Both scripts use only Python standard library and pre-existing repo code. There is no new runner/workflow, purchase, deployment or secret.

## 4. Executed verification and exact Git blob parity
- Local sandbox: **Linux Python3.13.5**, not native Windows.
- `python -m unittest discover -s retail_qa -p 'test_*.py' -q`: **58 discovered / 56 PASS / 0 FAIL / 0 ERROR / 2 SKIP** (native Windows tests skipped explicitly).
- `python -O -m unittest discover -s retail_qa -p 'test_*.py' -q`: **same 58 / 56 PASS / 2 native skips**.
- `python -m compileall -q retail retail_qa`: PASS.
- Test loader verified **both exact native test IDs** are in the 58-case discovery suite.
- `python retail_qa/strict_windows_gate.py`: **exit 2 BLOCKED**, correctly reports physical Windows required. No native Windows PASS claimed.
- GitHub code/test blob ID equals locally executed exact source:
  - `test_windows_native_acceptance.py` = `34e865419c53cb9d148c501220f7a22d4cee1e6f`
  - `strict_windows_gate.py` = `3dca25d093b6d437c3386ea8feaa091fc00027d3`
- Preceding remote source audit showed original protected Gate R manifest **25/25 exact SHA matches** and unexpected executables 0; this is provenance, not real Gate R execution.

## 5. Status, blockers and no-go
**Final-product 85% provisional retained; 95% NOT ACHIEVED, RELEASE HOLD.** A full authorized source checkout cannot be mounted in the current Linux sandbox due DNS restrictions; exact pinned Babel package missing. Existing P53 E2E harness remains BLOCKED in this sandbox. Physical Windows native NTFS junction, Edge/Chrome file://, actual Python3.11 runtime, full original P53 Gate R and genuine P53→ZIP integration remain **NOT EXECUTED**. No GitHub Actions/CI runs on this branch were triggered.

## 6. Repositories, branches, source and rollback
Private `hibi89/HAE@feature/rea-app-kmong-owner-delivery-20261112`, implemented SHA `3889f932f15d11d1497f69e458ecb978072427c8`. Original `REA_APP@2fe581b683f6a49779e71058cddbfd165871593a` / frozen P53 source preserved; Git ancestry provides rollback. Central hub `hibi89/hackathon-command-center-2026@kmong-productization` must retain product 85% and leave other 15 products untouched.

## 7. Reproduction / native environment / production
On a real Windows10/11 machine with an authorized clean checkout of the above feature branch, Python3.11+, Git, Node/npm and **already installed exact `@babel/parser@7.29.9`**, run:
```powershell
cd tools/rea-app
python retail_qa/strict_windows_gate.py
```
No download/install is performed by that command. If the correct Babel parser is not installed, it fails closed. A successful output is a **technical synthetic acceptance**, not proof of all customer rights or real-world client environments. Vercel/Production not applicable; retail artifact is an unsigned Python `.pyz`, **not a self-contained Windows EXE**.

## 8. Security, originals and backups
All tests use disposable synthetic source/reports and temp directories. Junction cleanup removes only the junction, not its target; reports are verified unchanged. Browser uses an isolated profile and offline `file://` review. No customer files, account tokens, production writes, original parser modifications, Git history rewrite, access/visibility changes, paid runner, licence override or app deployment. SOURCE_BLOBS hash comparison from prior audit preserved.

## 9. Next priorities / approvals
1. Execute the committed one-command strict gate in authorized native Windows full checkout with pinned Babel and save SHA-bound JSON/stdout; fix any actual regressions and rerun. **This is the decisive P95 technical blocker**.
2. Complete licence/NOTICE, redistribution/distribution format, customer support and controlled buyer-style acceptance; obtain owner release approval. Commercial usage remains HOLD until those conditions are actually satisfied.
3. If physical local Windows cannot be used, request **explicit approval for potential paid GitHub Actions Windows runner and external public npm package installation** before implementing/dispatching an alternative CI workflow.

## 10. Evidence / verified boundary
2026-11-12 KST. Verified local Linux: 56 PASS, 2 native SKIP; strict Windows preflight exit 2; GitHub SHA source parity. Original Gate R runtime/Node and P53 6/8 generation, actual Windows NTFS/file:// and end-buyer acceptance **UNVERIFIED**. Do not mark 95% based on this preparation.
