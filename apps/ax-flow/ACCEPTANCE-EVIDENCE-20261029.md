# HAE + Lightning Azent: real bundled acceptance evidence (2026-10-29)

## Scope and provenance

- Git branch: `feature/axflow-mvp` at source commit `dc252b22266ad4e5d95f7a16c0cddfac2371ef58`.
- Distribution: `apps/ax-flow/hae-integrated.pyz` obtained from that GitHub branch using its Base64 contents endpoint and reconstructed byte-for-byte.
- Distribution size: **341,524 bytes**.
- Git blob SHA-1: `1a30f209b8fbc8ab85e25741df847458b4a1b6fc` (matches downloaded GitHub blob).
- SHA-256: `a8b114e63083b291561bfea9f55694aa7e5aff002c46d1414d1d6ce510269eb6`.
- ZIP integrity: 26 entries, `ZipFile.testzip() == None`.
- Actual execution environment: **Linux, Python 3.13** (NOT native Windows).
- Inputs: bundled **synthetic** CSV in an isolated temporary directory; no customer SQLite or credentials accessed.

## Commands and actual observed results

```text
python apps/ax-flow/launch_integrated.py --verify
HAE + LA offline bundled HTTP/SQLite acceptance: 7/7 PASS

python apps/ax-flow/launch_integrated.py --data-dir /tmp/hae-la-smoke-20261029 --smoke --no-browser
HAE + Lightning Azent ready: http://127.0.0.1:8765/
HAE offline Windows bundle readiness: PASS

python -m unittest discover -s apps/ax-flow/tests -p test_start_hae.py -v
Ran 13 tests in 0.766s
OK

HAE_DATA_DIR=/tmp/hae-la-verify-userdata HAE_PORT=18473 HAE_NO_BROWSER=1 python apps/ax-flow/start_hae.py --verify
HAE launcher: integrated
HAE + LA offline bundled HTTP/SQLite acceptance: 7/7 PASS
```

### Seven real HTTP + SQLite gates

1. Real Lightning Azent backend health responds HTTP 200.
2. Preview is read-only and requests approval.
3. Denied approval responds HTTP 403 without SQLite writes.
4. Approved execution persists 2 synthetic CSV records.
5. Durable LA audit reports approval and events without leaking source record content.
6. Second approved execution persists 4 total distinct rows and a distinct run ID.
7. Server restart restores status and LA audit from SQLite.

### Acceptance boundary

**Linux integrated synthetic MVP E2E: PASS.** This constitutes execution evidence, not a claim that a user ran anything on their machine. **Native Windows cmd invocation, Windows filesystem-specific tests, browser UI acceptance, and complete commercial-product hardening remain unverified.** GitHub Actions jobs were failing before acquiring runners (runner ID 0, zero steps), so their status is not presented as test evidence. 100% here refers only to the seven-gate synthetic core integration contract, not the entire planned HAE product.

## Reproduce on a Windows machine

```cmd
HAE-Start.cmd --verify
```

Requires Python 3.11+ and the matching `apps\\ax-flow\\hae-integrated.pyz`. This invocation is expected to run entirely with temporary synthetic data; successful local execution must be independently observed.
