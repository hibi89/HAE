# HAE — 최종설계 전체 대비 요구사항·코드·검증 추적 (2026-11-13 KST)

> 유형: 실제 GitHub 소스·요구·과거 Actions 증거 대조 1차 감사. **새 테스트 실행이나 상용 수용 아님.**
> 공식 점수: **UNASSESSED** (사용자 승인 요구사항별 100점 가중치가 존재하지 않으며, 최종 E2E 미검증). 과거 엔지니어링 85%는 참고 이력으로만 보존.
> 설계 정본: `main/docs/ECOSYSTEM_CANONICAL.md` (2026-10-28 사용자 확정, 2026-10-29 UX 추가), `feature/axflow-mvp/REQUIREMENTS.md` (R-01..R-13 + Full completion). 사용자 2026-11-13 추가 명시: 실제 LLM 해석→AI/LA 양방향 오류 교정→범용 워크플로 자동 설계가 핵심, 기존 CSV MVP를 최종 범위로 축소 금지.
> 비교 대상 브랜치: `feature/axflow-mvp@8d50927697b18b60163dccf6ff859070a7661901` (문서 HEAD; 코드 파일의 Git blob은 파일별 조회 확인). 과거 Actions 기능 SHA `2384e9d245ca60fc9b2055e9b82c4541b33bd6bd`, [42990527614](https://github.com/hibi89/HAE/actions/runs/42990527614) 전체 **failure**: Ubuntu/Windows 각각 Python 264 PASS / 2 FAIL / 7 SKIP, UI Node 24 PASS. 본 감사에서 신규 실행 **0건**. 정확한 최신 HEAD 기능 E2E 검증 아님.

## 최종 요구 추적표 (가중치: 전체 미승인, 점수 환산 금지)
| ID | 최종설계 수용 범위 | 소스·기존 테스트 근거 | 현재 판정/차단 |
|---|---|---|---|
| HAE-R01 | 한국어 자연어/템플릿으로 비개발자가 노드·JSON 편집 없이 작업 생성, 실제 AI 해석 및 LA 오류 왕복 교정 | `apps/ax-flow/axflow/planner.py:150-225`의 5종 CSV 규칙·`tests/test_planner.py`, `web.py` `/api/preview`는 `planner: bounded local rules` 반환 | **부분 구현**: 규칙 해석만; 실 Qwen/LLM, 범용 자연어, 오류 왕복 미확인 |
| HAE-R02 | 파일 입력·출처·타입/크기 검사, CSV 후 XLSX/PDF 범위 | `web.py` CSV UTF-8 업로드/검사, `tests/test_web.py` 존재 | **부분 구현**: CSV 로컬 검사는 존재, 최종 XLSX/PDF/고객 데이터 품질·권리 미검증 |
| HAE-R03 | 버전/타입 IR, 검증, 허용 커넥터, 복구/수용 영수증 | `planner.py`가 `axflow.ir.v0` 생성, `axflow/engine.py:308` validate, `la_adapter.py` backend 계약 검사 | **부분 구현**: 제한적 IR·로컬 실행, 범용 노드/실 커넥터 계획 미확인 |
| HAE-R04 | 독립 CLI 실행기·원본 보호, GUI 비의존 | `axflow/engine.py` SQLite 실행·`__main__.py` 경로, `tests/test_engine.py` | **부분 구현/과거 로컬 증거**: 범용 고객 워크플로 검증 불가 |
| HAE-R05 | 고객별 OAuth/API 토큰 보안·필요 권한만 요청·안전한 자동 설정 | `planner.py:21-31`은 gmail/sheets/api 차단, `la_adapter.py` scope synthetic-only | **미구현/미검증**: 실 OAuth/Google Sheets/Gmail/시크릿 브로커 |
| HAE-R06 | dry-run, 실패 진단, 재시도/복구, AI/LA 오류 왕복 자동 보완 | `web.py:515-575` preflight/재개 확인, `tests/test_la_history_recovery.py`, 합성 재시도·복구 증거 | **부분 구현**: 검증된 로컬 실행/재개와 범용 AI 수정은 별개; 실 실행 dry-run/auto-repair 미증명 |
| HAE-R07 | 상태/승인/체크포인트/영수증·멱등성 SQLite 원장 | `engine.py` runs·steps, `workflow_catalog.py`, `runlog.py` 및 관련 테스트 | **부분 구현/기존 테스트 증거**: 로컬 범위, 실 고객·전체 회귀 최신 SHA 불확정 |
| HAE-R08 | 승인된 업무용 DB 실제 write/read, 자산 메타데이터, Sheets/PG 확대 | `engine.py` 로컬 CSV→SQLite, `asset_registry.py`, `tests/test_hae_three_customer_flows.py` | **부분 구현**: 합성 SQLite는 가능, Sheets/PG 및 실제 사용 범위 미검증 |
| HAE-R09 | 독립 DBVORA 서비스 연결, 실제 인벤토리/백업/독립 복원 | `dbvora_client.py`, `test_hae_la_dbvora_asset_e2e.py`는 loopback 합성 fixture의 읽기 전용 계약 | **부분/미검증**: 실제 독립 DBVORA 서비스·복원/정합 E2E 미확인 |
| HAE-R10 | 데이터 소유/원본 보존·삭제/이동 동의 | `engine.py` CSV readonly, 자산 파일 SHA/소스 보호 테스트 일부 | **부분 검증**: 모든 실 DB/외부 연동 경로에 대한 안전성 확인 부족 |
| HAE-R11 | 로컬 웹 UI/CLI·설치기·스케줄·운영, 비개발자 사용 | `web.py`, `desktop_launcher.py`, `scheduler.py`, GUI 테스트 파일 | **부분 구현**: 실제 고객 Win10/11 브라우저/패키지/스케줄 장기운영 미검증 |
| HAE-R12 | localhost/Origin/CSRF/경로/권한/송신·프롬프트 공격 방어 | `web.py:173+` local-origin 확인, `la_adapter.py` fail-closed 계약 | **부분 검증**: 실제 LLM prompt injection 및 고객 환경 보안·외부 경계 미검증 |
| HAE-R13 | 실제 성능·오류 복구·Windows/브라우저/상용 증거 | 기존 [Actions 42990527614](https://github.com/hibi89/HAE/actions/runs/42990527614) Python 2 FAIL/OS, Node 24 PASS | **차단**: 릴리스 parity 2 FAIL; 실 고객/성능/납품 미검증 |

## 최종설계의 필수 통합/제품 판정 (별도 체크)
- **HAE→실 모델→LA 자유 플로우 자동 생성/유형 추가·수정/양방향 오류 교정:** 이번 코드에서 확인되지 않음. 기존 `planner.py`가 명시적으로 AI/LLM/Gmail/Sheets 등 요청을 거부. 기존 성공한 CSV 규칙 사례를 전체 생성 기능으로 오인 금지.
- **HAE→LA 승인→SQLite write/재개:** 코드 및 과거 합성 테스트 근거 있음. LA 자체 브랜치 exact SHA 성공 [43124013493](https://github.com/hibi89/HAE/actions/runs/43124013493)은 별도 범위, HAE 최신 브랜치 전체 통과로 승계 금지.
- **SOVIA 사전 위험감사/실행 후 독립 대조:** 합성 사후 adapter와 테스트 존재; 실 독립 사전 Guard·완전성/고객 보안 E2E 미검증.
- **DBVORA 실제 독립 서비스/API·업무 DB 구조/백업 복원:** 합성 loopback 계약 테스트 존재; 실제 독립 E2E 미검증.
- **최종 수용 3개 자동화:** 로컬 CSV→SQLite 부분 증거. Google Sheets→로컬, 허가된 Gmail 보고 및 고객형 3개 파일럿 미검증. 릴리스 HOLD.

## 다음 검증 우선순위 / 사용자가 확정해야 할 사항
1. **최종 설계 훼손 없이** 실 LLM 어댑터의 입력/출력 버전 계약과 오류 왕복 교정 범위를 확정 후, 읽기 전용 fixture/오프라인 검증 먼저. 실 AI 모델 호출·실 외부 전송은 별도 사전 승인.
2. LA 범용 IR 제약/노드 레지스트리, 단계별 수정 및 역호환 테스트 정리. 기존 정상 로컬 엔진은 보존하고 신규 어댑터와 분리.
3. SOVIA 사전/사후 및 DBVORA 독립 로컬 프로세스 합성 통합; 현재 CI 2개 parity FAIL 분리 복구(기존 원본 ZIP 덮어쓰기 금지).
4. 요구 ID별 수용 기준·가중치 **사용자 승인 전** 공식 퍼센트 부여 금지. 기존 85% = 역사 수치; `UNASSESSED`가 0%를 뜻하지 않음. 고객 Win10/11·실 OAuth·권리·출시는 별도 게이트.
5. 이 문서의 정본 SHA/테스트 범위/미확인 사항을 HAE STATUS·HANDOFF와 해총 kmong 원장에 동기화.

**안전/비용/배포:** 소스 수정 0, 새 테스트 0, 비용/권한/시크릿/원본/배포 변경 0. 기존 기능 SHA와 본 문서 커밋 SHA는 구별. 결과는 '항목별 근거 감사 진행'이며 '최종 수치 확정'이 아니다.
