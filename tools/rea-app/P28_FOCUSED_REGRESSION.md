# REA_APP P28 — actual focused Python regression on exact GitHub source bytes

**Date:** 2026-10-27 KST. **Status:** FOCUSED PASS / FULL GATE R STILL PARTIAL.

## Scope and provenance
Source repository: private `hibi89/AX_FLOW`, branch `REA_APP` observed before testing at `9359f7a8631667934bb33415adc240f928f9cb3e`.
Source manually reconstructed inside isolated `/mnt/data/rea_validation/` from the GitHub connector because the container has no working DNS route to `github.com` and no mounted authenticated full private clone. Nothing was fetched from or copied from n8n.

Before executing, confirmed Git's blob framing `SHA1(b"blob " + decimal_length + b"\0" + raw_bytes)` for every file:

| Exact source / test file | Verified Git blob SHA |
|---|---|
| `rea_app/scanner.py` | `857bec57be22aba53e0d3063a25a1272cc5633ef` |
| `tests/test_scan_open_races.py` | `0601539e0a57807441fa31373339c689b2aa7439` |
| `tests/test_scan_sensitive_exclusions.py` | `3f40479907fe923137f9c018a57b2d3df08ba023` |
| `verify_gate_r.py` | `309510bd01aa01dc8ee6b2defb5498aebc67b0e1` |
| `tests/test_verify_gate_r.py` | `c8db5c2957cc365d6e3c4c6cfcc70d5f1351d7fc` |

**Method:** The scanner's GitHub file carried a trailing CRLF after its final LF; the local transfer was corrected until its SHA matched exactly. These are **five byte-identical GitHub files**, not a fresh clone of the complete repository.

## Exact runnable command and observed output
- OS: Linux container, Python 3.13.5. Node 22.16.0 available; `@babel/parser` not installed; private GitHub cannot be cloned.
- In `/mnt/data/rea_validation`:
  `python -m unittest discover -s tests -v`
- **Observed: 11 tests executed, 11 passed, 0 failures, 0 errors, 0 skipped** (0.021 s).
- P23 race conditions: replaced-file identity rejection PASS; swapped symlink rejection PASS.
- P24 sensitive path exclusions: no credential-file open PASS; private-directory pruning PASS.
- P25/P27 source provenance checker: known blob check, accept exact fixture, reject tamper, reject unreviewed script, reject symlink, reject Babel version mismatch and accept exact 7.29.9 in mocked subprocess PASS.

## Non-claims and remaining Gate R work
**This does NOT prove the full REA_APP analyzer suite**. The full source tree includes `rea_app/graph.py`, `rea_app/cli.py`, `rea_app/impact.py`, Babel adapter and `tests/test_cli.py`, none of which were run in this focused reconstruction. The genuine Node Babel 7.29.9 parser test was not run because the package is not installed. Windows behavior, including junction limitations, is not proven by Linux tests.

Next acceptance action: retrieve the remaining byte-accurate GitHub source files in an authorized checkout or construct a complete hash-matched local source tree; ensure installed `@babel/parser@7.29.9`, then run `python verify_gate_r.py` (14/14 manifest, complete Python suite and genuine Node parser test). Report full PASS/FAIL/SKIP without extrapolating focused results. Do not start paid GitHub Actions/CI without owner consent, and do not use n8n source without licensing review.
