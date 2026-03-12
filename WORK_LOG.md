# infosd 작업 로그

---

## 2026-03-12

### 변경 내역
- [UI] work.html: 정보보호부문 투자액(B) Q4/Q5/Q6 inv-card에 증빙 업로드 섹션 추가
- [UI] work.html: number 타입 금액 0원 시 증빙 섹션 자동 숨김 — `toggleEvidenceByValue()` JS 함수 구현
- [UI] work.html: 입력 필드 배경색 흰색 버그 수정 (`background: var(--bg-main)` 명시, Chromium autofill 대응)
- [UI] work.html: I-2 display_number 뱃지를 inv-grid-title에 추가
- [UI] work.html: 인력 항목(Q10/Q28/Q11/Q12) 컴팩트 2×2 그리드로 통합 렌더링
- [UI] work.html: I-3 투자비율(B/A), II-4 인력비율(D/C) ratio-bar 자동계산 표시 추가
- [UI] work.html: table 타입 "+ 행 추가" 버튼 onclick → data-cols + JSON.parse 방식으로 수정 (이중 따옴표 충돌 버그 수정)
- [UI] work.html: table 타입 증빙 섹션 항상 표시 (number 타입만 0원 조건 적용)
- [UI] index.html: 기업 삭제 시 확인 메시지 문구 강화 (복구 불가 안내 추가)
- [작가팀/UI] infosd 전체 질문 문구 및 도움말 개선 (작가팀 최종 검토 반영)
- [UI] dashboard.html/review.html: UI 디자인 미세 조정 및 레이아웃 최적화
- [백엔드] disclosure_routes.py: confirm 시 number 타입 0원 항목 필수 증빙 검증 제외 로직 추가
- [DB] Migration 011: display_number 전체 재정렬 — 정보보호공시 서식과 1:1 매핑 (I, I-1, I-2-가 … II-6 등)
- [DB] Migration 012: Q10(총 임직원) evidence_list 수정 — IT 인력 현황표/조직도 → 4대보험 가입자 명부/간이세액징수 신고서
- [DB] Migration 013: Q29(CISO/CPO 활동내역) evidence_list 추가 — CISO/CPO 활동 근거 서류 (회의록, 보고자료 등)
- [테스트] test_unit_infosd.py: 신규 7개 테스트 케이스 추가 (26개 → 33개)
  - table 타입 JSON 배열 저장 검증 (Q27)
  - 카테고리 1 투자 inv-grid + I-3 ratio-bar DOM 렌더링
  - 카테고리 2 인력 컴팩트 그리드 + II-4 ratio-bar DOM 렌더링
  - 투자비율/인력비율 자동계산 JS 표시 확인
  - table 타입 Q29 증빙 PDF 업로드·삭제
  - number 타입 금액 기반 증빙 섹션 토글
- [테스트] unit_checklist_infosd.md: 섹션 8~12 추가 (7개 시나리오)

### 변경 파일
- `templates/disclosure/work.html`: UI 개선 다수 (투자·인력 그리드, ratio-bar, 증빙 토글, 버그 수정)
- `templates/index.html`: 기업 삭제 확인 메시지 수정
- `disclosure_routes.py`: confirm 증빙 검증 로직 보완
- `migrations/versions/011_display_number_realign.py`: display_number 재정렬 마이그레이션 (신규)
- `migrations/versions/014_writer_team_final_review.py`: 작가팀 문구 개선 마이그레이션 (신규)
- `migrations/versions/012_fix_q10_evidence_list.py`: Q10 evidence_list 수정 마이그레이션 (신규)
- `migrations/versions/013_q29_evidence_list.py`: Q29 evidence_list 추가 마이그레이션 (신규)
- `test/test_unit_infosd.py`: 신규 테스트 케이스 7개 추가
- `test/unit_checklist_infosd.md`: 테스트 시나리오 섹션 8~12 추가

---

## 2026-03-05

### 변경 내역
- [DB] Migration 009: IT 감사팀 QA 점검 결과 반영 — 질문 완전성 보완 8건
  - Q13 문구: '지정 현황' → '지정 여부'
  - Q14 CISO/CPO 테이블: 임명일(appointed_date) 컬럼 추가
  - Q19 교육 실적 테이블: 실시일자(edu_date), 실시횟수(count) 컬럼 추가
  - Q20: yes_no → checkbox (지침서/절차서 개별 확인)
  - Q23 SBOM: number → select (4단계 현황 선택)
  - Q24 C-TAS: help_text 상호배타 안내 추가
  - Q27 주요투자 항목: textarea → table (항목명+금액+비고)
  - Q29 CISO 활동 내역: textarea → table (활동유형+내역+횟수)
- [DB] Migration 010: 작가팀 문구 검토 결과 반영 — 질문 표현 통일 5건
  - Q7 어조 통일: '있으신가요?' → '있나요?'
  - Q9 후행 공백 제거
  - Q13 질문형 전환: '지정 여부' → '지정되어 있나요?'
  - Q26 어법 오류 수정: '준비금 가입' → '배상 준비금을 적립하고 있나요?'
  - Q26 help_text 용어 통일: '적립금' → '배상 준비금'
- [설정] infosd.py: auth_routes 블루프린트 및 require_login 미들웨어 제거 (개발 편의)
- [테스트] test_unit_infosd.py: 전체 26개 시나리오 자동화 테스트 구현
- [테스트] unit_checklist_infosd_result.md: 테스트 결과 체크리스트 생성

### 변경 파일
- `migrations/versions/009_audit_qa_improvements.py`: IT 감사팀 QA 반영 마이그레이션 (신규)
- `migrations/versions/010_writer_qa_wording_fix.py`: 작가팀 문구 수정 마이그레이션 (신규)
- `infosd.py`: auth_routes 제거, 불필요 import 정리
- `infosd.db`: 마이그레이션 009·010 적용
- `test/test_unit_infosd.py`: 26개 유닛 테스트 시나리오 구현
- `test/unit_checklist_infosd_result.md`: 테스트 결과 리포트 (신규)

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
