# HAE × LA — Graphify 우선 노드 분석 및 지식 기반 자동화 최종설계 확장
> 2026-11-24 KST | 설계 변경만 수행 | 코드 구현/검증/배포 NOT_RUN | RELEASE HOLD

## 결정
사용자 목표: n8n의 노드 구조와 작동 원리를 적법하게 파악하여 증거 기반 백서로 축적하고, HAE 자연어 입력을 타입이 정해진 계획(IR)으로 변환하여 LA가 터미널에서 검증된 기능을 조합·실행하며, 없는 기능은 별도 코드 생성·검증 후 등록하고, 웹 대시보드에서 스텝별 실행·실패·복구를 보여준다.

기존 REA_APP 분석기를 고집하지 않는다. 외부 공개 분석기 **Graphify**를 우선 평가·사용하며 기존 REA_APP은 원본을 보존한 보조·비교 도구로 제한한다. **HAE + LA + SOVIA + DBVORA 네 가지 제품 필수 통합, REQUIREMENTS R-01..R-13/R-A1..R-A3 전체와 기존 보안·승인·라이선스·제품 완성 게이트는 유지한다.** n8n은 연구 대상이지 HAE/LA의 실행 엔진이나 복제 대상이 아니다.

## 분석 도구 결정 및 실증 게이트
- 1순위: https://github.com/Graphify-Labs/graphify (확인 당시 기본 브랜치 v8, PyPI graphifyy v0.9.118, Python >=3.11.5, tree-sitter AST, 그래프·의존·호출관계, graph.json 및 GRAPH_REPORT.md 출력, Apache-2.0 라이선스). 로컬 무료, Python 3.11 기반이라 기존 Windows 환경과 후보 호환. **n8n 프로젝트 규모 실제 성능은 NOT_RUN.**
- 보조: hibi89/HAE의 REA_APP 브랜치 v0.3.0. JS/TS AST·소스 증거·변경영향·8개 보고서 기능이 있으며 기존 기록상 Windows 합성 66 PASS/6 SKIP. 소스 보존, Graphify의 정밀한 노드/버전 입출력 추출이 부족한 경우에만 보완.
- 비채택(상용 경계): https://github.com/abhigyanpatwari/GitNexus ; 확인된 LICENSE는 PolyForm Noncommercial 1.0.0. 상품화 경로에서는 별도 권리 허가 전 사용 금지.
- 후보 승격 조건: 동일한 허용된 JS/TS fixture 및 허용된 n8n 공개 문서/소스 일부로 Graphify와 REA_APP의 노드 발견 정확성, 유형/입출력, 진입점, 증거 URL/라인, 미분석 노드, 실행 시간/피크 메모리, 설치·유지·권리 비용 비교. 실제 결과가 Graphify 우위를 입증해야 기본 도구 확정. 최신 외부 코드/의존성 설치는 잠금파일·해시·라이선스·보안 점검 후 로컬 격리에서만 실행.
- **법적 경계:** Graphify의 Apache-2.0은 분석 대상 n8n 코드의 경쟁제품 재배포·변형 허가를 뜻하지 않는다. n8n의 최신 Sustainable Use License·약관 및 연구 목적 허용 범위를 별도로 검토. 불확실한 소스는 공식 공개 문서/인터페이스 연구에 한정하고 관련 법적 판단 HOLD. n8n 소스, UI, 상표, 커넥터 코드 복사 및 AI 재서술을 통한 우회 금지.

## 아키텍처

### 1. 구조 연구와 노드 백서
- 권리 확인된 조사 대상 repo/ref/SHA 고정 → Graphify 로컬 인덱스 → nodes-base 등의 노드 목록/버전, description metadata, execute 또는 선언형 라우팅, 입력/출력, auth/credential, 외부 API, 데이터 변화, 오류 코드·재시도 등 구조와 호출 그래프의 **정적 증거** 수집.
- 원본 증거 원장에는 repo URL, 정확 커밋, 파일·라인, 접근일, 라이선스 판정, 증거등급을 기록. STATIC_FOUND, DOC_SUPPORTED, SYNTHETIC_EXECUTED, APPROVED_LIVE_VERIFIED 를 분리하며 정적 발견을 실제 작동 검증으로 오인하지 않는다.
- 고객에게 사용하는 **독립 기능 백서**에는 op_id, 목적, input/output typed schema, 설정, permissions/secret, side effects, error_code, retry/idempotency, state/recovery, 테스트벡터, 구현 가능성, 미지원/불확실성을 기록한다. 타사 구현 코드·보호 표현은 재사용하지 않는다.
- 초기 핵심 10~20개 범용 기능 우선. 전체 노드 자동 인덱싱과 모든 노드 기능 동등 재구현을 명확히 분리. 모든 n8n 노드의 깊은 동작 검증에 기간·완료율을 약속하지 않는다.

### 2. HAE 자연어→LA 명령
- HAE AI 플래너는 사용자의 자연어/승인된 파일·비밀보호된 연결상태와 **독립 백서**를 검색하여 사용자에게 DAG 실행계획을 제시한다.
- 정규 IR 필드: schema_version, plan_hash, run_id, steps[{step_id, op_id, op_version, typed_params, predecessors, branch/error_edges, retries, timeout, side_effects}], capability_lockfile_sha, source_file_hashes, consent_scope/version, policy_version, output_contract.
- 자연어·AI 출력·백서는 실행권한이 없다. LA의 결정적 스키마·타입·DAG·범위·권한·버전·하한/상한 검증 후에만 실행 후보. 모호한 요청만 최소 질문. 플로우 재작성/승인변경은 plan_hash 갱신 및 필요 시 재승인.

### 3. LA 재사용/부족 기능 생성/터미널 실행
- 기존 LA의 SQLite, CLI, schedule/resume, receipt, approval gate를 재사용하고 검증된 1st-party 기능 registry를 우선 조회. 각 기능은 immutable op+version+SHA, 출처·라이선스·테스트·지원 OS·제한 사항 기록.
- 기능이 없으면 **별도 제작기**가 독립 백서에서 신규 코드 후보를 생성 → allowlisted dependencies/정적 검증 → 단위/계약/부정 테스트 → 실제 OS 격리된 별도 subprocess에서 한도(시간, 메모리, 파일, 네트워크, DB/인증) 적용한 합성 smoke → 인간 검토·위험/권리/승인 → 버전 등록 또는 실패/보류. 생성 즉시 임의 쉘명령 실행 금지. 격리와 권한 검증이 없으면 코드 생성 결과는 실행 불가/HOLD.
- 실행은 LA의 정형 op CLI만 허용. unrestricted exec/shell/eval 금지. 원본·고객자료 변경·외부송신·이메일·게시·권한·결제는 기존 명시 승인, 비밀 저장소, 감사 게이트 유지. 실패·부분성공·외부 API 응답 불확정에서는 blind retry 금지.
- SOVIA의 실제 사전 계획 검토·사후 행동 감사, DBVORA의 실제 업무 SQLite 스키마·상태·별도 프로세스 백업/검증복원은 **최종 제품 필수 통합**이며 모의 응답만으로 PASS 불가.

### 4. HAE 웹 대시보드
기존 127.0.0.1 Python 로컬 HTTP + HTML/CSS/JS를 사용. 사용자 자연어·파일 입력, 관련 백서/지원 기능 제안, 생성 필요 플래그, DAG 시각화, 각 단계의 planned/approval_required/generation_pending/ready/running/failed/partially_completed/completed/paused/canceled 상태, 실제 LA run_id/step_id/ordered_event/receipt, 재연결 후 readback, 승인과 재실행, SOVIA 감사 및 DBVORA 데이터 자산 패널. 실서비스와 mock·합성 상태를 혼용 금지. localhost Host/Origin/CSRF·파일 경로·비밀 로그 검증 유지.

## 목표 범위와 수용

### 해커톤용 수직 시연 (부분집합, 최종 제품 100% 아님)
1. Graphify가 수집한 허용된 노드 구조를 출처와 함께 백서로 정리하는 실제 재현 가능한 시연.
2. HAE 한국어 입력 → AI/명세 검색 → 버전 고정 LA typed IR → 사용자 승인 → 실제 CLI 실행.
3. 로컬 합성 3종 업무: CSV 필터→SQLite, 분기→보고서, 스케줄→재실행/복구. 10~20가지 독립 기본 기능 중 실제 구현된 것만 지원으로 명시.
4. 누락 op 한 가지의 코드 제작/격리 테스트/인간 승인/등록 또는 안전 거부 흐름.
5. 웹 대시보드 실제 단계 이벤트·오류·영수증, 재접속 후 상태 복구; Windows 브라우저/패키지 및 필수 안전 검증.

### 최종 제품 완료(원래 전체 범위 유지)
기존 R-01..R-13/R-A1..R-A3 + HAE/LA/SOVIA/DBVORA 정본 전체 + 본 지식·기능 제작 확장. 특히 실제 Gmail/Google Sheets/CSV 3개 고객형 업무, 실제 OAuth·비밀, 실제 SOVIA plan/action 감사, DBVORA 독립 연결·백업·격리 복원, 상용 설치/실브라우저, 비밀·인증·DB 무결성/침투·회귀, 외부 권리/고객 파일럿·성능·독립 감사, 사용자 RELEASE GO.

## SWU 후보 / 코드 통합 의존
새로운 설계 작업은 기존 SWU·REQ를 임의 폐기하지 않고 실코드 GAP·allowed_paths·S/C/I/D/U·승인상태를 확인한 뒤 별도 작업으로 분할한다.
- KDB-01 (R-A1~A3): 동일 fixture에서 Graphify/REA_APP 성능·정확성·권리 검사, 분석 어댑터.
- KDB-02 (R-A1~A3): 노드 근거/백서 계약 파서·저장·검색.
- KDB-03 (R-01/R-03): HAE 한국어→백서 검색→typed IR과 실패·모호성 처리.
- KDB-04 (R-03/R-04/R-12): LA registry/version pin/type validator/CLI.
- KDB-05 (R-04/R-06/R-12): 부족 기능 안전 생성/테스트/승인·등록·rollback.
- KDB-06 (R-01/R-06/R-11): HAE 단계 이벤트/승인/오류 UI·API 실제 LA 연결.
- KDB-07 (R-05/R-07~R-09/R-12): 실제 SOVIA·DBVORA·OAuth 통합.
- KDB-08 (R-06/R-11~R-13): P2 독립 검증/Windows·보안·복구·브라우저/상품 수용. 이 항목은 P1 SWU 구현률에 넣지 않으며 별도 P2 큐로 분리.
모든 신규 후보는 작업 설계 단위이며 현재 어떤 기능도 완성으로 새로 인정하지 않는다.

## 일정 재산정: 가정과 불확실성
**가정:** 1인 집중 개발 하루 6~8시간, 기존 REA_APP/HAE/LA 코드 재사용, 무료 로컬 환경, 외부 승인 병목 제외. 측정치가 아니라 초기 계획치이며 Graphify 속도효과 UNMEASURED.

| 단계 | 예상 집중 작업일 |
| --- | ---: |
| Graphify 설치·REA_APP 비교·허용 n8n 구조 인덱싱 | 1–3 |
| 핵심 노드 백서/독립 op 계약·기능 매핑 | 3–7 |
| HAE AI→IR→LA 실제 CLI/3개 합성 자동화 | 5–10 |
| 부족 op 제작기 안전경로·HAE 단계별 화면 | 7–14 |
| 해커톤 P2 로컬/Windows/브라우저·패키지/시연 | 5–10 |
| **해커톤용 부분집합** | **21–44 작업일**, 일정 단축 가능성은 미실측 |
| 외부 API·실 SOVIA/DBVORA·권한·고객형 UI·회귀/보안/독립검수·파일럿 | 추가 45–100+ 작업일 |
| **기존 전체 제품 + 본 확장** | **66–144+ 집중 작업일** (약 3–7개월 이상, 승인·외부 검증 지연 제외) |

n8n 노드의 **목록화** 자체는 범위가 허용되고 분석기가 정상 작동하면 빠르게 진행될 수 있으나, 모든 노드의 정확한 동작/오류/인증 재현 및 상품 수준 구현은 며칠로 단정 불가. 상기 전체 기간에 n8n 모든 노드 기능 동등 복제를 포함하지 않는다. 기존 90–180일 추정과 달리 일부 구성의 신규 동적 코드 생성 요구가 더해졌으므로 확정일자로 취급 금지.

## 기록·상태
문서 변경만: 새 P1 구현 0, 새 P2 PASS 0, 공식 가중 완료율 UNASSESSED. Graphify 설치/벤치마크, 실제 n8n 노드 인덱스·백서 생성, LLM 변환·코드 생성기, 신규 전체 CI/Windows/browser 검증 모두 NOT_RUN. 이전 LA 정확 SHA 합성 Windows/Linux 206/205 PASS 기록과 HAE P85 합성 7 PASS·전체 Python 281 PASS/2 FAIL/7 SKIP 기록은 기존 한정 증거일 뿐 이번 설계 검증 증거 아님. 외부 고객 원본/과금/Production/권한·main 병합은 별도 GO 필요.
