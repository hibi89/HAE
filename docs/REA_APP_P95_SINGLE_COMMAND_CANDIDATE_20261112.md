# REA_APP P95 target — single-command candidate acceptance (2026-11-12 KST)

## 1. Goal, confirmed product scope and technology
Keep frozen REA_APP v0.3.0/P53 analyzer intact. Improve the optional private Python3.11+ offline buyer-review companion so a user can generate and validate a reproducible summary-only customer candidate with one command. Existing 85% provisional engineering estimate is not a sales-readiness score; target remains 95%.

## 2. Two approaches considered and decision
- A: add integrated installer/GUI and modify frozen analyzer. Benefit: direct end-user flow; cost: larger regression surface, Babel and native Windows acceptance, OS/signing work. Deferred until full source+Windows runtime available.
- B: zero-dependency standalone `candidate_cli.py` orchestrating existing owner build, verification, canonical ZIP, source-backed verification and final SHA256. Benefit: lower cost and less maintenance, preserves frozen original and earlier standalone interfaces. **Implemented B.**

Trigger and data: explicitly selected local P53 report folder → validate v1 schemas/limits/consistency → prepare new review folder → recheck source SHA/aggregate HTML/JSON → deterministic four-file ZIP → source-bound ZIP verification → owner report verification → SHA256. No HTTP, API, customer source execution or external upload. Failure is HOLD; no automatic retry of ambiguous operations.

## 3. Implemented
- New `tools/rea-app/retail/candidate_cli.py`: `--bundle` existing private original reports, `--delivery` new output directory, `--archive` new ZIP; returns nonzero on failure. Never overwrites preexisting destinations. Checks both outputs before generating, checks original reports before writing, and final ZIP bytes after verification. Produces only SHA256/HOLD console status; unchanged data remains local.
- On failure, conditional rollback deletes only exact matched inode+content of new outputs. If another writer changes a file, **stop and preserve it** for manual inspection. This is conservative best effort, not crash-atomic output nor a security signature. No merge into frozen CLI.
- New `tools/rea-app/retail_qa/test_candidate_cli.py`: 7 tests of CLI success and source immutability, rerun refusal, preexisting output and ZIP preservation, malformed bundle rejection, controlled post-pack rollback, race replacement preservation, nested output prohibition.
- P85 existing `owner_delivery.py`, `package_delivery.py` and all previous QA preserved.

## 4. Exactly executed evidence
Product feature branch `hibi89/HAE@feature/rea-app-kmong-owner-delivery-20261112`, function/tests SHA **`78f0906cb0e713733c1543728e75ed3641e9b2d2`**.
- Linux Python3.13.5 `cd /mnt/data/rea_app_recovery && python -m unittest discover -s retail_qa -p 'test_*.py' -v`: **39 PASS / 0 FAIL / 0 SKIP** (~5.9s).
- `python -m compileall -q retail retail_qa`: **PASS**.
- Five execution-source Git Blob SHAs exact-match remote repository at source SHA: owner `810bceeffb3b605b911592adeec1f4f7e0c8be2c`, package `42ec1e1241cf5423669518d4ca45a81cebb6ded2`, original QA `e12e21a18dc6c3a5148e7cad3c0a3d632d545c68`, candidate CLI `bdc5b7d13ee93ac5f01acb2344e951527e0e7668`, new QA `2c8bd9196ebe93a6ae1dcaba787f1d5f53964ce6`.
- Scope: real filesystem operations, subprocess single-command execution, deterministic ZIP and source-backed verify on **synthetic schema-shaped** report fixtures. Not a real Babel-created P53 analysis output. No claim that original P53 Gate R+QA passed at current feature commit.
- Direct Chromium `file://` navigation has returned `ERR_BLOCKED_BY_ADMINISTRATOR` in this sandbox; no real native Windows browser test. GitHub Actions/CI, wheel install, locked Babel install and signed customer distribution **NOT RUN**.

## 5. Completion and stop
**REA_APP final-product 85% provisional retained; 95% NOT CERTIFIED; RELEASE HOLD / SALE NO-GO.** Security hardening and usability improved, but full original engine, actual P53-generated source report E2E, Windows buyer package and license/customer pilot remain unverified.

## 6. Repositories, branches, SHA and paths
Private product `hibi89/HAE`, branch `feature/rea-app-kmong-owner-delivery-20261112`, code `78f0906cb0e713733c1543728e75ed3641e9b2d2`. Original `REA_APP@2fe581b683f6a49779e71058cddbfd165871593a` unchanged, P53 function `1ae3dac263a1a5c866434c8418fe7dbb1d3f1d48` preserved. Relevant paths above and `docs/REA_APP_P95_ZIP_SECURITY_RETEST_20261112.md`.

## 7. Production URL, runtime and deployment
Production/Vercel N/A. Local Linux Python3.13.5 scoped; new command `python tools/rea-app/retail/candidate_cli.py --bundle PRIVATE_BUNDLE --delivery NEW_REVIEW_DIR --archive NEW_REVIEW.zip`. No additional dependencies or paid runner. Native Windows/Node20+ not verified at new SHA.

## 8. Backups, privacy and restrictions
Source reports read-only, no customer source paths in ZIP, no token/secrets/customer data transmission. Original analyzer, `REA_APP`, `main`, LA branches, permissions, billing, domain, deployment and releases unchanged; all feature commits recoverable by normal Git history. **No commercial/legal approval**.

## 9. Next steps / acceptance gates
1. Access authorized executable full private checkout and run P53 `python verify_gate_r.py`, original QA, plus 39 retail QA on **the same exact code SHA**, with native Windows runner where permitted. Do not assume hosted CI is free.
2. Build real P53 six-/eight-report bundle from synthetic source snapshots with exact pinned Babel; run new one-command candidate flow and verify source SHA, deterministic ZIP, no source mutation and failure recovery.
3. Test `file://` buyer unpack on physical Windows10/11 Chrome/Edge, Python3.11 compatibility, privacy NOTICE/license/rights, signing/support and buyer pilot before P95 re-evaluation or commercial GO.

## 10. Evidence date and verification scope
Updated 2026-11-12 KST. Five-file exact Git blob match and **39/39 Linux scoped synthetic tests**; no original whole checkout, real Babel, native Windows, CI or customer acceptance proof. 95% target remains unmet.
