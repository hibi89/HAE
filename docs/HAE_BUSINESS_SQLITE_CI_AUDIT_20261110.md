# HAE Business SQLite P1/P2 — Exact-SHA CI Acceptance & Outstanding Regression (2026-11-10 KST)

## HAE 제품 진척 판정

**최종 상품 완성률 잠정 65% → 70% (+5%p)**. 이는 다음 두 기능이 실제 HAE GitHub 소스에 병합되고, 신규 테스트를 Windows/Linux GitHub CI의 Python 3.11에서 실행한 근거를 반영한 **제품 범위 추정**입니다. 상용 고객 준비/전체 테스트 PASS/실 DBVORA 백업 연동이나 OAuth 구현 완료를 의미하지 않습니다. **RELEASE HOLD**.

- P1 +2%p: `axflow.business_state_backup.inspect_business_state`, 32 MiB 이하 소유자 지정 닫힌 일반 SQLite 데이터베이스의 무결성·외래키·테이블수/원본 SHA만 읽기 전용 확인. 원본 데이터/테이블명/파일경로/비밀번호는 반환하지 않음. 실제 업무 DB나 고객 자료는 미사용.
- P2 +3%p: 기존 검증된 HAE `state_backup.py`의 SQLite backup 및 경합시 덮어쓰기 방지 코드를 독립 `business_state_backup.py`로 재사용. SHA 지정 복원 `restore_business_state_pinned`은 **반드시 새 경로**로만 복원, 잘못된 SHA/기존 파일/지원하지 않는 WAL/가상 테이블/손상/링크 등 FAIL CLOSED. 별도 `python -m axflow.business_db_cli`는 `--synthetic`와 쓰기 작업의 `--ack-new-file`을 필수화. 외부 송신/클라우드/프로덕션/데이터 자동 이동/고객 인증 없음.
- 기반 `hibi89/HAE@feature/axflow-mvp`, GitHub **기능 추가 SHA `2bccfecd6248217b56980600a56e7da14046169b`**, G81 pinned public UGREEN bridge contract assertion 수정 후 기능+테스트 검증 **`7cc7b36559df19a488eb333ce12c69349797a76d`**. `main` 및 Lightning Azent `feature/lightning-azent` 수정 없음.

## GitHub Actions exact source / evidence

- [Run 42738240787](https://github.com/hibi89/HAE/actions/runs/42738240787) source `7cc7b36559df19a488eb333ce12c69349797a76d`, actual GitHub-hosted Windows/Linux runners, staged independent LA SHA `9cba6424dadf3fadb0ccd6ed10040e322c4a62fa` + public UGREEN bridge SHA `3cab98b6dadf97dcab32b77f8b33ff7dafb2b462`.
- New `tests/test_business_db_cli.py` 8 test cases + `test_business_state_backup.py` 16 cases: **Linux 24 PASS, 0 FAIL, 0 SKIP** and **Windows 23 PASS, 0 FAIL, 1 SKIP** (POSIX-only atomic hardlink conflict fixture). Verified by individual named log lines, not merely the counts from a separate equivalent local prototype.
- HAE→LA→SQLite HTTP acceptance step **6/6 PASS**; pinned public FlowPilot bridge stage **PASS** on both OS after correcting stale legacy expectation `hae_http_audit_verified` vs the documented `hae_http_connected:True`, `actual_la_execution_verified:True`, and scope `HAE_LOOPBACK_HTTP_AND_LA_AUDIT_REPORT`. Independent SQLite row read and explicit approval/no write on altered source remain intact.
- **Full Python suite failed**, not certified: Linux **Ran 185, 3 FAIL, 7 SKIP**; Windows **Ran 185, 11 FAIL, 7 SKIP** (includes Windows POSIX-only skip). Therefore overall Actions conclusion **FAILURE**, not SUCCESS. Steps after full Python testing were not reached. No customer release evidence.
- Linux failing tests: (1) checked-in `hae-integrated.pyz` does not include the newly introduced two business modules (packaged artifact remains a prior snapshot); (2) checked-in `HAE-Windows-offline.zip` has legacy CRLF versus currently checked-out LF bytes for `run-bundled.cmd`; (3) launcher occupied-port test expects `is in use` while actual safe error says `is unavailable`. Do not claim shipped artifact source parity or replace user distribution ZIP on this branch without explicit release process.
- Windows additional issues: pre-existing runtime backup injected source-change/parent junction/replacement race tests; Windows `Path.resolve` 8.3 vs long path display fixture comparisons in `test_start_hae.py`; no-UTF8 Windows runner console print of Korean temporary path in `launch_integrated.py` and `build_hae_windows_bundle.py` (cp1252 `UnicodeEncodeError`); a mocked `Path.is_symlink` test fails on Windows while **actual Windows junction rejection test PASSED**. These are separate regression fixes, **not validated Windows customer-readiness**.
- Previous run [42737941402](https://github.com/hibi89/HAE/actions/runs/42737941402) failed earlier in bridge test due stale key. Corrected with minimum test change on `7cc7b36559df19a488eb333ce12c69349797a76d`; no provider source/schema change and no retry of unsafe POST.

## Failure report / stop and pivot

**시도:** HAE 실제 Python 3.11 Windows/Linux CI 2개 기능 SHA, legacy bridge contract aligned. **근거:** newest run new business tests green but complete Python suite red. **대안:** (1) preserve shipped artifact and treat release parity as HOLD while advancing independent source proof (chosen now); (2) after separately approved release candidate, build checksum-verified self-contained ZIP from exact source and re-run full Windows acceptance; (3) isolate Windows-specific reparse-point/path/encoding regressions and repair with fault-injection tests. **사용자 선택사항:** no request needed for continuing isolated fixes, but release ZIP overwrite/publish/Cloudflare, customer data/OAuth or additional paid runner permissions require separate prior approval.

## Next completion gates

1. Preserve existing `hae-integrated.pyz`, `HAE-Windows-offline.zip`; do not silence packaging mismatch or claim commercial artifact certification. Rebuild only in a separate *new* versioned release-candidate path if explicitly approved.
2. Fix narrow Windows source path alias/reparse and UTF8 console handling, test with actual Windows runner. Correct stale port error test without disabling occupied-port detection.
3. Run native full HAE+LA synthetic HTTP/SQLite + Node UI, packaging and `--verify` at exact SHA; new business DB feature 24 Linux/23 Windows actual PASS must remain preserved.
4. Full product R-05/R-08/R-09: OAuth/Google Sheets+Gmail approved real providers, DBVORA supported-source restore, backup provenance UI, security/pilot/installer/Windows customer certification remain unverified/blocked. No automatic public account, real business DB access or outside customer consent.

**Rollback/source:** `hibi89/HAE@feature/axflow-mvp` baseline `42d8de5d56f74ec0fa1908f16e162b538fe704e3`; feature SHA `2bccfecd...`; corrected test SHA `7cc7b36559df19a488eb333ce12c69349797a76d`. Current Linux/Windows runner evidence 2026-11-10 KST, synthetic only, RELEASE HOLD. New docs-only SHA is confirmed only after push.
