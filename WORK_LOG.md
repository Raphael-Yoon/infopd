# infosd 작업 로그

---

## 2026-03-04

### 변경 내역
- [UI] CISO/CPO 상세 현황(Q2-2-1) `table` 타입 입력 UI 구현 — 고정 2행(CISO/CPO), 6개 컬럼
- [UI] 인증 보유 현황(Q3-1-1) `table` 타입 동적 행 추가/삭제 UI 구현
- [UI] `checkbox` 타입 렌더링 신규 구현 (복수 선택, JSON 배열 저장)
- [DB] Q4 계열 전체 options 일괄 설정 (Q4-1-1, Q4-1-2, Q4-1-4, Q4-1-5, Q4-1-7, Q4-1-8)
- [DB] 전체 질문 `evidence_list` 일괄 설정 (15개 항목 — 투자액, 인력, 인증, 교육, 지침, 취약점, 훈련, 보험)
- [UI] 작업 화면 상단 네비게이션 바 제거 (하단 footer로 통합)
- [DB] Q27(주요 투자 항목) sort_order 수정: 28 → 7 (Q1-2 이전 정렬 위치 조정)
- [버그] `_is_question_active()` group 타입 부모 처리 순서 버그 수정 → 진행률 100% 정상화
- [버그] sidebar 진행률 계산 SQL → Python 로직으로 교체 (status 컬럼 의존성 제거)
- [UI] 투자액 합계 단위 KRW → 원 변경
- [DB] 2025년 테스트 투자액 데이터 현실화 (Q2: 5억, Q4: 5천만, Q5: 3천만, Q6: 2천만)
- [설정] CLAUDE.md 팀원 배경·경력 상세 추가, 사용자 존댓말 규칙 명시
- [설정] 작업 로그 관리 지침 추가 (CLAUDE.md 섹션 7)

### 변경 파일
- `templates/disclosure/work.html`: table/checkbox 타입 렌더링, nav 바 제거, 단위 수정
- `disclosure_routes.py`: `_is_question_active()` 버그 수정, sidebar 진행률 로직 교체
- `infosd.db`: Q4 options, evidence_list, sort_order, 테스트 데이터 업데이트
- `CLAUDE.md`: 팀원 배경 추가, 작업 로그 지침 추가
- `WORK_LOG.md`: 신규 생성
