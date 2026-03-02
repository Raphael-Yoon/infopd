# infopd — 정보보호공시 관리 시스템 프로젝트 계획서

- **작성일**: 2026-03-02
- **담당팀**: 개발3팀
- **PM**: 이태욱

---

## 1. 프로젝트 개요

### 배경
snowball 시스템 내 정보보호공시 기능(snowball_link11.py)을 참조하여, 완전 독립적인 정보보호공시 전용 시스템을 신규 구축한다. snowball과는 코드·DB·인증 모두 공유하지 않는다.

### 목적
- 정보보호공시 업무를 전담하는 독립 웹 시스템 제공
- 다수 기업의 공시연도별 데이터를 통합 관리
- 로그인 없이 회사+연도 선택만으로 즉시 작업 가능한 간결한 UX

### 제약 조건
- snowball 프로젝트 코드/DB 수정 없음
- 로그인/인증 기능 없음
- 독립 SQLite DB 사용 (`infopd.db`)

---

## 2. 기술 스택

| 구분 | 기술 |
|------|------|
| Backend | Python, Flask |
| Database | SQLite (`infopd.db`) |
| Frontend | Jinja2 템플릿, Bootstrap |
| 파일 업로드 | Flask 내장 (로컬 저장) |

---

## 3. 프로젝트 구조

```
infopd/
├── infopd.py                      # Flask 앱 진입점
├── db_config.py                # DB 연결 및 마이그레이션 실행
├── company_routes.py           # 회사/연도 관리 라우팅
├── disclosure_routes.py        # 공시 작업 라우팅
├── infopd.db                  # SQLite DB (자동 생성)
├── PROJECT_PLAN.md             # 본 계획서
├── requirements.txt
├── migrations/
│   ├── __init__.py
│   └── versions/
│       ├── 001_create_companies.py     # 회사/공시대상 테이블
│       ├── 002_create_disclosure.py    # 공시 관련 테이블 5종
│       └── 003_seed_questions.py       # 질문 초기 데이터
├── templates/
│   ├── base.html               # 공통 레이아웃
│   ├── index.html              # 메인 (회사 목록)
│   ├── company_form.html       # 회사 등록/수정
│   └── disclosure/
│       ├── dashboard.html      # 공시 작업 대시보드
│       ├── work.html           # 질문-답변 입력
│       └── review.html         # 공시 자료 검토
├── static/
│   ├── css/
│   └── js/
├── uploads/
│   └── disclosure/             # 증빙 자료 업로드 경로
└── logs/
```

---

## 4. DB 설계

### prefix 규칙: `ipd_`

#### ipd_companies (회사 기본 정보)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | TEXT PK | UUID |
| name | TEXT | 회사명 |
| created_at | TIMESTAMP | 등록일 |
| updated_at | TIMESTAMP | 수정일 |

#### ipd_targets (공시 대상 = 회사 + 연도)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | TEXT PK | UUID |
| company_id | TEXT FK | ipd_companies.id |
| year | INTEGER | 공시연도 |
| status | TEXT | draft / submitted |
| created_at | TIMESTAMP | |
| UNIQUE(company_id, year) | | 중복 방지 |

#### ipd_questions (공시 질문 — 고정 마스터)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | TEXT PK | 질문ID (Q1, Q2 ...) |
| level | INTEGER | 질문 계층 |
| category | TEXT | 카테고리 (1~4) |
| subcategory | TEXT | 소분류 |
| text | TEXT | 질문 내용 |
| type | TEXT | text / number / boolean / select |
| options | TEXT | 선택지 (JSON) |
| parent_question_id | TEXT | 부모 질문 ID |
| dependent_question_ids | TEXT | 연동 질문 IDs (JSON) |
| required | INTEGER | 필수 여부 |
| help_text | TEXT | 도움말 |
| evidence_list | TEXT | 권장 증빙 목록 (JSON) |
| sort_order | INTEGER | 정렬 순서 |

#### ipd_answers (공시 답변)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | TEXT PK | UUID |
| question_id | TEXT FK | ipd_questions.id |
| company_id | TEXT FK | ipd_companies.id |
| year | INTEGER | 공시연도 |
| value | TEXT | 답변값 |
| status | TEXT | pending / answered |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |
| deleted_at | TIMESTAMP | soft delete |
| UNIQUE(question_id, company_id, year) | | |

#### ipd_evidence (증빙 자료)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | TEXT PK | UUID |
| answer_id | TEXT FK | ipd_answers.id |
| question_id | TEXT | |
| company_id | TEXT FK | ipd_companies.id |
| year | INTEGER | |
| file_name | TEXT | 원본 파일명 |
| file_url | TEXT | 저장 경로 |
| file_size | INTEGER | |
| file_type | TEXT | |
| evidence_type | TEXT | |
| uploaded_at | TIMESTAMP | |

#### ipd_sessions (공시 세션)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | TEXT PK | UUID |
| company_id | TEXT FK | |
| year | INTEGER | |
| status | TEXT | draft / submitted |
| total_questions | INTEGER | |
| answered_questions | INTEGER | |
| completion_rate | INTEGER | % |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |
| submitted_at | TIMESTAMP | |
| UNIQUE(company_id, year) | | |

#### ipd_submissions (제출 기록)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | TEXT PK | UUID |
| session_id | TEXT FK | ipd_sessions.id |
| company_id | TEXT FK | |
| year | INTEGER | |
| submission_data | TEXT | JSON |
| submitted_at | TIMESTAMP | |
| confirmation_number | TEXT | |
| status | TEXT | |

---

## 5. 화면 흐름

```
[메인 — 회사 목록]
  ├─ 회사+연도 카드 목록 (진행률 표시)
  ├─ [새 회사 등록] 버튼
  └─ 카드 클릭 → [공시 작업 대시보드]

[회사 관리]
  ├─ 회사명 입력
  ├─ 공시연도 추가/삭제
  └─ 회사 삭제 (연동 데이터 포함)

[공시 작업 대시보드]
  ├─ 4개 카테고리별 진행률
  ├─ 카테고리 선택 → [질문-답변 입력]
  └─ [공시 자료 검토] 버튼

[질문-답변 입력]
  ├─ 질문 목록 (조건부 표시)
  ├─ 답변 저장 (실시간)
  ├─ 증빙 자료 업로드/삭제
  └─ 유효성 검증 (투자액, 인력 비율 등)

[공시 자료 검토]
  ├─ 전체 답변 미리보기
  └─ 제출 처리
```

---

## 6. 단계별 구현 일정

| 단계 | 내용 | 담당 | 상태 |
|------|------|------|------|
| 1 | 프로젝트 뼈대 + 서버 기동 | 임태준 | 완료 |
| 2 | DB 마이그레이션 구성 | 임태준 | 완료 |
| 3 | 회사/연도 관리 기능 | 임태준 + 양필조 | 완료 |
| 4 | 공시 작업 로직 이관 | 임태준 | 완료 |
| 5 | 공시 자료 생성/검토 | 임태준 | 완료 |
| 6 | 전체 UI 구성 | 김종규 | 진행 |
| 7 | 통합 테스트 | 정래훈 | 대기 |

---

## 7. 유효성 검증 규칙 (link11 동일)

- 정보보호 투자액(B) ≤ 정보기술 투자액(A)
- 정보보호 전담인력 ≤ 정보기술부문 인력
- 필수 질문 미답변 시 제출 불가

---

## 8. 참조

| 파일 | 용도 |
|------|------|
| `snowball/snowball_link11.py` | 기능 명세 참조 (수정하지 않음) |
| `snowball/migrations/versions/030~038` | 질문 데이터 및 스키마 참조 |
