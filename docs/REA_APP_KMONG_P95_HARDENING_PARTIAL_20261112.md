# REA_APP P85→P95 hardening slice — partial evidence, 2026-11-12 KST

## 1. Goal / requirements / stack
Strengthen the Python3.11+ offline summary/ZIP handoff toward a commercial P95 validation gate while preserving the frozen P53 v0.3.0 analyzer. Existing P85 is a provisional engineering estimate, not customer readiness.

## 2. Design alternatives and decision
- A: modify original analyzer / full private Windows packaging. Better eventual E2E but higher regression risk and requires exact original Gate R, pinned Node/Babel and Windows.
- B: minimal optional companion changes + security negative tests. No API charges or database; shorter safe path, preserves original functionality. **Selected B for this slice.** Neither can certify P95 without original and buyer acceptance.
- Trigger: explicit local CLI owner build/verify/pack/verify-zip. Data: three approved source report files → computed aggregate JSON/HTML → four-member ZIP; verify reopens originals and recomputes exact outputs when --bundle is supplied. Without --bundle, checks unsigned internal shape only. No external data transfer.
- Recovery: immutable Git parent SHA, refuse overwrite, no customer source write, duplicate/path guards, release HOLD. No exactly-once guarantee for concurrent local filesystem attackers.

## 3. Implemented (feature branch only)
- `tools/rea-app/retail/owner_delivery.py`: reject duplicate nested JSON keys and unexpected output directory entries before owner verify.
- `tools/rea-app/retail/package_delivery.py`: source-free ZIP check now enforces exact schema fields, fixed HOLD/assurance/limitations, 16 bounded integer metrics, canonical JSON, regenerated fixed HTML, 64-character lower-hex source digest format and expected digest keys. **Unsigned ZIP remains forgeable**; only --bundle source-linked recomputation protects against self-consistent substituted reports.
- `tools/rea-app/retail_qa/test_customer_delivery.py`: six regression cases for unexpected files, duplicate keys, changed HTML with rehashed receipt, falsely changed release status, malformed source digest and negative metrics. Existing 23 cases preserved.

## 4. Tests and evidence
- Product code+test remote GitHub SHA `c3f83af41240d0aefd6d9b26611b70068871ada9` (three sequential non-force commits).
- GitHub HEAD exact file blob IDs after writes: owner `810bceeffb3b605b911592adeec1f4f7e0c8be2c`; package `cba4d26b1d67b0e5cce69efe7ef220cd21836aab`; tests `40e054f2d43f70aee4f348c8ad149dc7be915d58`.
- Isolated local Python3 scoped mirror of newly inserted JSON/receipt logic: **10 PASS / 0 FAIL**; this is NOT import/execution of a complete checked-out GitHub source tree.
- Prior original P85 23/23 tests and Chromium 9-row synthetic evidence refer to an *older source SHA*. At current code SHA full `python -m unittest discover -s retail_qa -v` **NOT RUN** (29 test cases authored, not 29 passed).
- GitHub combined statuses 0 and PR workflow runs 0 at code SHA. Authenticated private checkout unavailable because container `git ls-remote` failed DNS for github.com. Original Gate R/QA, exact wheel, actual physical Windows/Chrome/Edge file://, real bundle, customer license/rights, production all **NOT VERIFIED**.

## 5. Status and stop rule
**P95 NOT ACHIEVED / P85 provisional retained; RELEASE HOLD / SALE NO-GO.** Engineering scope improved but no defensible +10pp acceptance score. Do not reinterpret standalone smoke as end-to-end success.

## 6. Repository / branch / SHA / paths
Private `hibi89/HAE@feature/rea-app-kmong-owner-delivery-20261112`, exact changed code SHA `c3f83af41240d0aefd6d9b26611b70068871ada9`. Original `REA_APP@2fe581b683f6a49779e71058cddbfd165871593a` and pinned P53 analyzer unaffected. Public hub `hibi89/hackathon-command-center-2026@kmong-productization` should record 85 unchanged with this evidence.

## 7. Production/environment
No Vercel / Production URL (N/A). Linux local scoped simulation, no paid GitHub runner or live customer files. Python3.11+ expected but unchanged repository imports/test runner not executed in this turn.

## 8. Originals / backups / security
No user source, paid API, secret, token, external upload, permission change, licensing alteration, deployment, branch merge or force update. Rollback through prior Git commits; keep analyzer freeze.

## 9. Next prioritized acceptance gates
1. Obtain authorized executable private checkout or existing approved runner; execute exactly `cd tools/rea-app && python -m unittest discover -s retail_qa -v`, original `python verify_gate_r.py` and `python -m unittest discover -s qa -v`, validate SHA/Windows skip counts.
2. Generate actual six/eight-report synthetic P53 bundle → owner build/verify → ZIP pack → verify with original bundle; inspect bytes, preserve originals, smoke direct file:// on real Windows10/11 Edge/Chrome.
3. Rights/NOTICE/privacy/signing/support and owner-approved buyer pilot; only then evaluate P95 score. CI billing and real customer data need prior approval. Do not ship on preliminary results.

## 10. Updated and verification scope
2026-11-12 KST. Remote source patches committed; isolated algorithm checks run; original integrated Python, Windows, CI and customer acceptance unverified. This record is P95-target progress, not a P95 completion certificate.
