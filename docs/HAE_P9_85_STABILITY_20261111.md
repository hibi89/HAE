# HAE P9: 85% provisional milestone stability audit (2026-11-11 KST)

- **Product:** HAE Humanized Automation Ecosystem, local-first Python3.11+Lightning Azent.
- **Branch:** `hibi89/HAE@feature/axflow-mvp` (private)
- **Tested feature SHA:** `2384e9d245ca60fc9b2055e9b82c4541b33bd6bd`
- **Remote GitHub-hosted CI:** https://github.com/hibi89/HAE/actions/runs/42990527614
- **Result:** Ubuntu and Windows each **273 Python tests = 264 PASS, 2 FAIL, 7 SKIP, 0 ERROR**. Node22 simulated browser asynchronous race tests **24 PASS** each (prior 22). Entire GitHub workflow **FAILURE**, as original shipped zipapp+ZIP parity tests remain failing. **RELEASE HOLD**, 85% provisional product engineering estimate **unchanged**.

## P9 owner interface safety

A: lock input controls while saved-workflow GET is pending; small implementation, poor offline latency UX and can block owner editing when a local server is unresponsive. B (chosen): an incrementing `catalogLoadVersion` that invalidates older GET results on each new recipe click or manual task/CSV edit/upload; **constant memory, zero added API calls/cost, no persistence/security policy changes**.

The HAE UI now drops outdated saved-workflow load responses, including one that would otherwise overwrite the owner's edited task/CSV fields, or a newer selected saved recipe. The successful latest load still **requires a fresh preview and explicit write approval**. Node tests `testSavedWorkflowLateReplyDoesNotOverwriteManualEdit` and `testSavedWorkflowNewestClickWinsOutOfOrderReplies` added. Prior first test SHA `6e15df1` failed because mocked list DOM children were read before pending async tasks settled; test fixture `35c5145` added a `setImmediate` flush, and both platforms later reported UI24 PASS.

## Windows LA HTTP CI fault isolation

At `35c5145`, standalone Windows `test_la_adapter.LightningAzentAdapterTests.test_http_flow_uses_real_lightning_backend_and_matches_axflow` timed out after 5s during HTTP POST after the backend had persisted SQLite. The HTTP server's response attempted to write to an aborted socket (`WinError 10053`), then temp folder teardown raced active SQLite handles (`WinError 32`). This is a bounded test timing/cleanup defect; it is *not evidence* of an actual customer service outage or data corruption.

At SHA `2384e9d245ca60fc9b2055e9b82c4541b33bd6bd`, `tests/test_la_adapter.py` reserves 20s for explicitly localhost synthetic HTTP assertions, registers TempDir cleanup before server cleanup using `unittest.TestCase.enterContext`, so LIFO teardown shuts down the server before deleting DB files. GitHub Windows standalone LA targeted 5 tests PASS, then entire Windows 273 Python ran with 0 unexpected ERROR. Equivalent Ubuntu run also passed newly touched tests. Original real HAE/Lightning Azent runtime source is preserved.

## Remaining release gates

The only two tests still failing each OS are:
1. `test_checked_in_zipapp_matches_current_hae_and_staged_la_sources`
2. `test_release_zip_matches_shipped_sources_and_executes_real_la_e2e`

Both stem from original checked-in `hae-integrated.pyz` and `HAE-Windows-offline.zip` being older than current source. Tests stay enabled; original binaries are unchanged and **must not be overwritten or replaced without owner approval**. New source-matched, differently named release candidate requires explicit user authorization. No claims for customer Windows10/Edge/Chrome, real DBVORA FastAPI service, actual Gmail/Sheets OAuth, real customer pilots, installer, secrets, or commercial acceptance. Vercel Production **N/A** for a local app.

**Product completion: 85% provisional remains exactly 85%. No new arbitrary scoring increase.**
