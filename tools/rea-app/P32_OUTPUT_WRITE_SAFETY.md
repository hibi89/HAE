# P32 — Safe report replacement

Date: 2026-10-27 KST. Branch: REA_APP.

Original `_write_report` used `Path.open("w")` and followed an existing report-file symlink. A disposable synthetic fixture demonstrated overwrite of the linked target file.

Two designs compared:
- Precheck `is_symlink` before opening: smaller, but race-prone and may truncate existing reports on failure.
- Selected: write a UTF-8 temporary file in the same output directory, flush/fsync, close, then `os.replace` the destination link entry; clean temporary file on error. Standard library and no additional cost.

Verification: Linux Python 3.13.5, four focused tests PASSED: linked target unchanged, normal report update, injected replacement error retained original and cleaned temporary file, UTF-8 Korean text remained exact. New test is `tests/test_report_write_safety.py` and its blob matches local executed bytes.

Not verified: full analyzer Python tests, real Babel parser, Windows native junction behavior, mutable output parent races or atomic replacement of both JSON/Markdown reports as a pair. Gate R stays PARTIAL. The updated offline verifier expects 15 reviewed source/test blobs.

Next: on authorized exact checkout with @babel/parser 7.29.9 installed, run `cd tools/rea-app && python verify_gate_r.py` and capture 15/15 source, full Python PASS/FAIL/SKIP and genuine Node parser results. No customer files or third-party restricted source tested.
