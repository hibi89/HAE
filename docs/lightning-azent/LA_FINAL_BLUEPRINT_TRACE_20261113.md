# Lightning Azent — 최종설계 기반 요구·실행 근거 추적 (2026-11-13 KST)

> 최종설계: `hibi89/HAE@main/docs/ECOSYSTEM_CANONICAL.md`(LA 역할 및 9단계 고객 통합), `REQUIREMENTS.md`의 IR/실행/승인/재시도/복구·3개 자동화, 해총 2026-11-13 [OWNER-FINAL-BLUEPRINT-100](https://github.com/hibi89/hackathon-command-center-2026/blob/kmong-productization/docs/strategy/FINAL_BLUEPRINT_COMPLETION_STANDARD_20261113.md). 원본의 n8n 유사 UX는 비개발자가 노드를 직접 연결하는 것이 아니라 AI→LA가 지원 워크플로를 스스로 설계하는 것이다.
> 소스 검토 브랜치 `feature/la-p17-audit-evidence-20261112@14d8c0f44509626f647692d4dc3a09e1f99bd2b6`. 과거 실제 CI 검증 **다른 기능 SHA** `c32e27c8156a4ed27d6f2bca7752e7a4eccf6dc7`, [Actions #43124013493](https://github.com/hibi89/HAE/actions/runs/43124013493) Ubuntu205/Windows206 PASS, 0 FAIL, 2/2 성공 (합성 로컬). 이번 감사에서 신규 코드/테스트 실행 0.
> **공식 완성률 UNASSESSED**: LA 최종설계 전체의 사용자 승인 100점 가중치·새 정확 SHA 전체 통합 E2E 미충족. 종전 85%는 엔지니어링 한정 이력.

## 요구 추적표 (LA-Txx: 감사 식별자이며 새 제품 설계/가중치가 아님)
| 감사 ID | 정본의 최종 수용 요구 | 실제 코드/테스트 | 범위·판정 |
|---|---|---|---|
| LA-T01 | 검증된 타입·버전 IR로 노드/스텝/조건/연결 자동 설계 | `packages/lightning-azent/lightning_azent/contract.py`: `azent.ir.v0`/legacy 버전 검증, 11개 한정 op | **부분 구현**: 기본 literal/field/map/condition/branch/CSV/SQLite 존재, 임의 비즈니스 노드/데이터 커넥터의 자동 설계는 미확인 |
| LA-T02 | 실 LLM 해석 결과 수신, 미지원/오류를 AI에 되돌려 자동 수정 및 재검증 | `contract.py` `prepare_plan()` 지원되지 않는 버전 거부; `hae_bridge.py` 합성 수동 승인 | **미구현/미검증**: LLM 호출·모델 왕복 프로토콜·부분 수정 API를 이번 소스에서 확인할 수 없음 |
| LA-T03 | 안전한 계획 preflight·사용자 승인 후 해당 계획만 실행 | `contract.py:49-67` preflight (실 dry-run 아님); `hae_bridge.py:104-126` 요청 해시·쓰기에 명시 승인 | **부분 구현/과거 합성 CI 근거**: 실 고객 OAuth/외부 전송/승인 브로커는 없음 |
| LA-T04 | 승인한 데이터 흐름의 실제 읽기/변환/DB 쓰기·조회 | `contract.py:14-18` 지원 op, `runtime.py` LAExecutor, `tests/test_hae_to_la_e2e.py` 임시 CSV/SQLite 실제 행 검사 | **로컬 합성 범위 구현/기존 CI**: PostgreSQL/Sheets/Gmail/외부 범용 커넥터 없음 |
| LA-T05 | 스케줄·상태·재시도·재개·중복 방지·정확 영수증 | `runtime.py` execute/resume/schedule/verify_receipts/status/audit, `tests/test_scheduler_runtime_recovery.py` 등 | **부분 구현/과거 CI**: interval/manual, 서비스 장기운영/실 외부 side effect 멱등성 미검증 |
| LA-T06 | SOVIA 실행 전 위험 심사 + LA 행동·승인·요청 간 대조 | `hae_bridge.py` evidence는 `independent_sovia_audit: False` | **미검증**: 실 독립 SOVIA 사전/사후 통합 및 정책 강제 |
| LA-T07 | DBVORA 실제 자산 연결·인벤토리·검증 복원, 역할 분리 | SQLite 사업 DB 실행은 확인; 별도 DBVORA 소스/서버 독립 통합이 LA에 완성됐다는 증거 없음 | **부분/미검증** |
| LA-T08 | 안전한 실패 경계·비밀/원본 보존·고객 Windows 및 릴리스 | `contract.py` external_connectors=[], forbidden shell/network/oauth/cron/webhook/n8n import, CI 성공 SHA 별도 | **부분/미검증**: 실제 고객PC·최신 HEAD 고객 E2E, 보안/인증/서명/배포 부족 |

## 사실과 제한
- 기존 `azent.ir.v0`는 실행 가능한 제한적 step graph를 **검증하고 실행**한다. AI가 고객 요청으로부터 범용 그래프를 **생성**한다는 증거로 해석 금지.
- 로컬 합성 CSV를 사용자 승인으로 임시 SQLite에 쓰고 3행 유지/재개·변조 거부를 검사하는 테스트가 존재하고, 그 기능 SHA의 과거 CI는 성공. **새로운 본 감사에서 테스트를 재실행하지 않았다.**
- `contract.py`는 지원 트리거를 `manual`, `interval`로 제한하며 `scope='synthetic-local-only'`, `external_connectors=[]`, `not_supported`에 oauth/network/webhook 포함. 범용 대외 업무 자동화가 구현됐다고 보고하면 안 된다.
- 기존 내부 85%를 공식 점수로 승격하거나 '0% 완성'으로 하향하지 않는다. 요구별 승인 가중치 및 최신 정확 SHA E2E 후에만 수치 계산.
- 핵심 후속 과제: HAE LLM 인터프리터↔LA 타입 계약/실행 전 변경안 교환, 안전한 단계별 자동 편집과 검증, SOVIA/DBVORA 독립 통합 및 기능/실 브라우저/고객 OS 검증. 외부 모델 호출·비밀/실 사용자 자료 사용은 사용자 별도 승인.

**상태:** 공식 수치 UNASSESSED, 부분 구현 확인; 기존 85% 엔지니어링 이력 보존; RELEASE HOLD/SALE NO-GO. 이 문서만 갱신하며 소스·개인정보·CI·Production 변경 없음.
