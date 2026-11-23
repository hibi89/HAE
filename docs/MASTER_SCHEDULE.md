# AX FLOW — active 7-day hackathon integration sprint

**CURRENT USER-DIRECTED TARGET (2026-10-27 KST):** **3–5 days preferred (by Oct 31), 7 days maximum requested review (Nov 2)** for a **supported-scope local AX FLOW + SQLite + DBVORA hackathon-reusable MVP**. The earlier 5-week plan is archived in Git history. This is an aggressive target, not validated ability to ship a complete universal commercial product in seven days.

Read [SPRINT_7_DAY_HACKATHON.md](SPRINT_7_DAY_HACKATHON.md) for **day-by-day implementation, acceptance gates, three hackathon reuse boundaries and known remaining work**. Preserve [TARGET_BLUEPRINT_V1.md](TARGET_BLUEPRINT_V1.md) as full target definition; it is not replaced with a smaller scope in order to inflate completion. The older [FAST_TRACK_5_WEEK.md](FAST_TRACK_5_WEEK.md) is historical superseded planning only.

| Dates | Delivery gate | Scope |
|---|---|---|
| Oct 27–29 | D1–3 core | independent workflow engine, SQLite runtime + business data, replay/restart/status, 3 distinct flows |
| Oct 30–31 | D4–5 integration MVP | supported natural language/templates → validated workflow → safe auto-test, minimal GUI, DBVORA read-only SQLite schema map |
| Nov 1–2 | D6–7 release decision | clean Windows browser/CLI, crash/permission/security/DB offline E2E, pinned hackathon integration examples |

**Do not silently replace the original complete-product gates** (OAuth/actual provider auth, robust repair, full DBVORA backup/restore, commercial security and installs). Missing full-gate features remain explicit backlog after limited hackathon MVP. DBVORA real independent source/tests do not become verified just because AX FLOW adapter exists. No forced use in UGREEN official Markdown-only ZIP, no invented PayPal payment functionality, no distraction from KIC PDF submission. All actual project status and tests must remain SHA-bound and measured.


## 2026-11-24 최신 계획 보정 — Graphify 기반 HAE/LA 설계 확장

기존 2026-10-27의 7일 해커톤 MVP 일정은 **역사적 목표**이지 현재 전체 설계의 잔여 시간 추정으로 재사용하지 않는다. 새 사용자 지정 방향은 [Graphify 기반 지식 자동화 최종설계](GRAPHIFY_KNOWLEDGE_AUTOMATION_BLUEPRINT_20261124.md)를 따른다.

| 구간 | 비실측 집중 작업일 |
|---|---:|
| Graphify 우선 후보/REA_APP 비교·권리·로컬 노드 정적 인벤토리 | 1–3 |
| 노드 백서·독립 op 계약 | 3–7 |
| HAE 한국어→typed IR→LA CLI 수직 통합 | 5–10 |
| 누락 op의 안전 생성·테스트·등록 + HAE 실행 대시보드 | 7–14 |
| 해커톤 시연 로컬 P2/Windows/브라우저·패키지 | 5–10 |
| **해커톤 부분집합** | **21–44 작업일** |
| 실제 외부 계정·SOVIA/DBVORA·권한/보안·고객 파일럿·독립 검증 | **추가 45–100+ 작업일** |
| **최종 전체 확장 제품** | **66–144+ 작업일, 약 3–7개월 이상** |

이 작업일은 1인 하루 6–8시간 집중, 기존 코드 재사용, 무승인/비용/법적 병목 제외 조건의 **추산**이며 속도 향상 효과 UNMEASURED. n8n 모든 노드 실제 동작 동등 구현은 포함하지 않는다. 설계 외 작업/테스트는 NOT_RUN이고 본 파일 변경은 RELEASE 승인이나 main 병합이 아니다.
