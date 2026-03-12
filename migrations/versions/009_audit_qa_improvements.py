"""
009_audit_qa_improvements.py

감사팀(IT 감사팀) 점검 결과 반영 — 질문 완전성 보완
대상: Q13, Q14, Q19, Q20, Q23, Q24, Q27, Q29

1. Q13 문구: '지정 현황' → '지정 여부'
2. Q14 CISO/CPO 테이블: 임명일(appointed_date) 컬럼 추가
3. Q19 교육 실적 테이블: 실시일자(edu_date), 실시횟수(count) 컬럼 추가
4. Q20 지침·절차서: yes_no → checkbox (지침서/절차서 개별 확인)
5. Q23 SBOM: number → select (건수 단독 기재의 공시 한계 개선)
6. Q24 C-TAS: options에 상호배타 메타 추가 + help_text로 UI 가이드
7. Q27 주요투자 항목: textarea → table (항목명+금액 구조화)
8. Q29 CISO 활동 내역: textarea → table (활동유형+내역+횟수 구조화)
"""
import json


def upgrade(conn):
    # ── 1. Q13 문구 수정 ─────────────────────────────────
    conn.execute(
        "UPDATE isd_questions SET text='최고책임자(CISO/CPO) 지정 여부' WHERE id='Q13'"
    )

    # ── 2. Q14 CISO/CPO 테이블 — 임명일 컬럼 추가 ───────
    q14_options = {
        "columns": [
            {"key": "type", "label": "구분", "type": "select",
             "choices": ["CISO", "CPO"], "width": "80px"},
            {"key": "name", "label": "성명", "type": "text", "width": "100px"},
            {"key": "position", "label": "직위", "type": "text", "width": "120px"},
            {"key": "appointed_date", "label": "임명일", "type": "date", "width": "115px"},
            {"key": "is_officer", "label": "임원 여부", "type": "select",
             "choices": ["임원", "비임원"], "width": "90px"},
            {"key": "is_concurrent", "label": "겸직 여부", "type": "select",
             "choices": ["전담", "겸직"], "width": "80px"},
            {"key": "concurrent_role", "label": "겸직 시 주요 직무",
             "type": "text", "width": "180px"}
        ],
        "fixed_rows": ["CISO", "CPO"]
    }
    conn.execute(
        "UPDATE isd_questions SET options=? WHERE id='Q14'",
        (json.dumps(q14_options, ensure_ascii=False),)
    )

    # ── 3. Q19 교육 실적 테이블 — 실시일자·실시횟수 추가 ─
    q19_options = {
        "columns": [
            {"key": "name", "label": "교육명", "type": "text", "width": "180px"},
            {"key": "edu_date", "label": "실시일자", "type": "date", "width": "115px"},
            {"key": "count", "label": "실시횟수(회)", "type": "number", "width": "90px"},
            {"key": "target", "label": "교육 대상", "type": "text", "width": "120px"},
            {"key": "method", "label": "교육 방식", "type": "select",
             "choices": ["집합", "온라인", "혼합"], "width": "100px"},
            {"key": "hours", "label": "교육 시간(h)", "type": "number", "width": "90px"},
            {"key": "attendees", "label": "이수 인원(명)", "type": "number", "width": "90px"}
        ],
        "dynamic_rows": True
    }
    conn.execute(
        "UPDATE isd_questions SET options=? WHERE id='Q19'",
        (json.dumps(q19_options, ensure_ascii=False),)
    )

    # ── 4. Q20 지침·절차서 — yes_no → checkbox ────────────
    q20_options = ["정보보호 지침서 수립·관리", "정보보호 절차서 수립·관리"]
    conn.execute(
        """UPDATE isd_questions
           SET type='checkbox', options=?, text='정보보호 지침 및 절차서 수립·관리'
           WHERE id='Q20'""",
        (json.dumps(q20_options, ensure_ascii=False),)
    )

    # ── 5. Q23 SBOM — number → select ────────────────────
    q23_options = [
        "전사 도입 및 운영 중",
        "일부 시스템 도입 중",
        "도입 검토 중",
        "미도입"
    ]
    conn.execute(
        """UPDATE isd_questions
           SET type='select', options=?,
               text='공급망 보안(SBOM) 관리 현황',
               help_text='소프트웨어 구성 요소 명세서(SBOM) 도입 및 운영 현황을 선택하세요.'
           WHERE id='Q23'""",
        (json.dumps(q23_options, ensure_ascii=False),)
    )

    # ── 6. Q24 C-TAS — help_text로 상호배타 안내 ─────────
    conn.execute(
        """UPDATE isd_questions
           SET help_text='※ "참여하지 않음" 선택 시 다른 항목과 중복 선택하지 마세요.'
           WHERE id='Q24'"""
    )

    # ── 7. Q27 주요투자 항목 — textarea → table ───────────
    q27_options = {
        "columns": [
            {"key": "item", "label": "투자 항목명", "type": "text", "width": "250px"},
            {"key": "amount", "label": "금액(원)", "type": "number", "width": "140px"},
            {"key": "note", "label": "비고", "type": "text", "width": "180px"}
        ],
        "dynamic_rows": True
    }
    conn.execute(
        """UPDATE isd_questions
           SET type='table', options=?,
               text='주요 투자 항목 (정보보호 투자의 주요 내역)',
               help_text='정보보호 투자 항목별 명칭과 금액을 기재해 주세요.'
           WHERE id='Q27'""",
        (json.dumps(q27_options, ensure_ascii=False),)
    )

    # ── 8. Q29 CISO 활동 내역 — textarea → table ─────────
    q29_options = {
        "columns": [
            {"key": "activity_type", "label": "활동 유형", "type": "select",
             "choices": ["이사회·경영진 보고", "예산 심의 참여", "정책·지침 수립",
                         "보안 사고 대응", "교육·훈련 주관", "취약점 점검 승인", "기타"],
             "width": "170px"},
            {"key": "detail", "label": "주요 내용", "type": "text", "width": "260px"},
            {"key": "count", "label": "횟수(회)", "type": "number", "width": "80px"}
        ],
        "dynamic_rows": True
    }
    conn.execute(
        """UPDATE isd_questions
           SET type='table', options=?,
               text='CISO/CPO 주요 활동 내역',
               help_text='공시 기간(1~12월) 중 CISO/CPO의 주요 활동을 유형별로 기재해 주세요.'
           WHERE id='Q29'""",
        (json.dumps(q29_options, ensure_ascii=False),)
    )

    conn.commit()


def downgrade(conn):
    # Q13
    conn.execute(
        "UPDATE isd_questions SET text='최고책임자(CISO/CPO) 지정 현황' WHERE id='Q13'"
    )
    # Q14 — 임명일 제거
    q14_orig = {
        "columns": [
            {"key": "type", "label": "구분", "type": "select",
             "choices": ["CISO", "CPO"], "width": "80px"},
            {"key": "name", "label": "성명", "type": "text", "width": "100px"},
            {"key": "position", "label": "직위", "type": "text", "width": "120px"},
            {"key": "is_officer", "label": "임원 여부", "type": "select",
             "choices": ["임원", "비임원"], "width": "90px"},
            {"key": "is_concurrent", "label": "겸직 여부", "type": "select",
             "choices": ["전담", "겸직"], "width": "80px"},
            {"key": "concurrent_role", "label": "겸직 시 주요 직무",
             "type": "text", "width": "180px"}
        ],
        "fixed_rows": ["CISO", "CPO"]
    }
    conn.execute("UPDATE isd_questions SET options=? WHERE id='Q14'",
                 (json.dumps(q14_orig, ensure_ascii=False),))
    # Q19 원복
    q19_orig = {
        "columns": [
            {"key": "name", "label": "교육명", "type": "text", "width": "200px"},
            {"key": "target", "label": "교육 대상", "type": "text", "width": "130px"},
            {"key": "method", "label": "교육 방식", "type": "select",
             "choices": ["집합", "온라인", "혼합"], "width": "100px"},
            {"key": "hours", "label": "교육 시간(h)", "type": "number", "width": "100px"},
            {"key": "attendees", "label": "이수 인원(명)", "type": "number", "width": "100px"}
        ],
        "dynamic_rows": True
    }
    conn.execute("UPDATE isd_questions SET options=? WHERE id='Q19'",
                 (json.dumps(q19_orig, ensure_ascii=False),))
    # Q20 원복
    conn.execute(
        "UPDATE isd_questions SET type='yes_no', options=NULL, text='정보보호 지침 및 절차서 수립/관리' WHERE id='Q20'"
    )
    # Q23 원복
    conn.execute(
        "UPDATE isd_questions SET type='number', options=NULL, text='공급망 보안(SBOM) 관리 및 조치 (건)', help_text=NULL WHERE id='Q23'"
    )
    # Q24 원복
    conn.execute("UPDATE isd_questions SET help_text=NULL WHERE id='Q24'")
    # Q27 원복
    conn.execute(
        "UPDATE isd_questions SET type='textarea', options=NULL, text='주요 투자 항목 (정보보호 투자의 주요 내역을 기재)', help_text=NULL WHERE id='Q27'"
    )
    # Q29 원복
    conn.execute(
        "UPDATE isd_questions SET type='textarea', options=NULL, text='CISO/CPO 주요 활동 내역', help_text=NULL WHERE id='Q29'"
    )
    conn.commit()
