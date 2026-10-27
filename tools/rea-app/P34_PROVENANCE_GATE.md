# REA_APP P34 — Gate R evidence provenance hardening
Date: 2026-10-27 KST. Repo `hibi89/AX_FLOW`, branch `REA_APP`.

## Finding
P33's evidence collector accepted success-shaped output from any local `verify_gate_r.py` while checking only Git HEAD/branch. In its synthetic fixture, the verifier was untracked and simply printed PASS markers; the collector marked this PASS. That is sufficient for a false-positive evidence record.

## Alternatives
A. Leave output-marker-only checks: inadequate provenance, rejected.
B. Pin the reviewed Gate R verifier's Git blob, reject modified/untracked/staged files under `tools/rea-app` using local `git status --porcelain --untracked-files=all -- .`, and require exact status-line patterns including `exit 0`. **Selected**, standard library and local Git only, no additional cost.
C. Move to remote signed/CI attestations: deferred; private CI may cost money and requires separate authorization.

## Code and verification
- `tools/rea-app/run_gate_r_evidence.py` now pins verifier blob `396654c47b25cfbc0279b4dcdc2f8872c7e20891`; if legitimate verifier source changes, re-review it and deliberately update the pin and tests. Also records the actual blob and scoped clean-worktree status in evidence JSON.
- `tools/rea-app/qa/test_run_gate_r_evidence.py` now creates real local disposable Git repos and commits a synthetic verifier with a corresponding synthetic runner pin. It separately exercises dirty verifier, clean-but-mismatched verifier SHA, untracked new script, incorrect branch, bad output counters and exit suffix, nonzero result, missing marker, protected output location, and repeated runs.
- **Actual Linux Python 3.13.5 local isolated test run: 11/11 PASS, zero skipped/failures/errors.** Tested exact Git blob bytes: runner `50475a1b827c4ad077cfc5b54765fa4624bd6157`; QA test `767ffc7a835608651cc96ccf9cf1fe410435503c`. Those were confirmed by independent GitHub-created blobs and published in code commit `4e0ce299ebd01fa20c541358ffeaf4f593f56f11`.

## Limits and next gate
No full 15-file REA_APP analyzer/CLI/graph/impact Python suite, genuine installed Babel 7.29.9 Node parser suite, or actual Windows junction tests ran here. Gate R remains **PARTIAL**. Git cleanliness check is scoped to `tools/rea-app`, and checks before verifier execution; it is not immutable filesystem attestation. Collector records output locally, not to a remote service; review before sharing.

Next: at authorized complete exact checkout with pinned Babel already installed, run `cd tools/rea-app && python run_gate_r_evidence.py`. Require complete 15/15 source match, real Python PASS and Node PASS, clean Git state, reviewed verifier SHA and exit 0. Only then review Gate R release status. No paid CI, customer data, restricted n8n source, or deployment change in P34.
