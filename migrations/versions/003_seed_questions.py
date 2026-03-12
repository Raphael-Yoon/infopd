"""
정보보호공시 질문 초기 데이터 삽입 (Q1-Q29)

snowball.db sb_disclosure_questions 기준 최종 확정본.
sort_order는 038_fix_sort_order 기준으로 적용.
"""

import json


QUESTIONS = [
    # ============================================================
    # 카테고리 1: 정보보호 투자
    # ============================================================
    {
        "id": "Q1", "display_number": "Q1-1", "level": 1, "category_id": 1,
        "category": "정보보호 투자", "subcategory": "투자",
        "text": "공시대상연도(1~12월)에 정보보호 투자가 발생했나요?",
        "type": "yes_no",
        "dependent_question_ids": ["Q2", "Q3", "Q27"],
        "sort_order": 10,
        "help_text": "정보보호 관련 설비 구입, 서비스 이용, 인건비 등 투자가 있었는지 확인합니다."
    },
    {
        "id": "Q2", "display_number": "Q1-1-1", "level": 2, "category_id": 1,
        "category": "정보보호 투자", "subcategory": "투자",
        "text": "정보기술부문 투자액(A) (원)",
        "type": "number",
        "parent_question_id": "Q1",
        "sort_order": 20,
        "help_text": "발생주의 원칙에 따른 1년 간의 총 IT 투자액"
    },
    {
        "id": "Q3", "display_number": "Q1-1-2", "level": 2, "category_id": 1,
        "category": "정보보호 투자", "subcategory": "투자",
        "text": "정보보호부문 투자액(B) - 다음 3개 항목의 합계",
        "type": "group",
        "parent_question_id": "Q1",
        "dependent_question_ids": ["Q4", "Q5", "Q6"],
        "sort_order": 30,
        "help_text": "정보보호 투자액은 감가상각비, 서비스비용, 인건비의 합으로 구성됩니다."
    },
    {
        "id": "Q4", "display_number": "Q1-1-2-1", "level": 3, "category_id": 1,
        "category": "정보보호 투자", "subcategory": "투자",
        "text": "1) 유/무형자산 당기 감가상각비",
        "type": "number",
        "parent_question_id": "Q3",
        "sort_order": 35,
        "help_text": "보안 장비, S/W 등의 당기 감가상각비"
    },
    {
        "id": "Q5", "display_number": "Q1-1-2-2", "level": 3, "category_id": 1,
        "category": "정보보호 투자", "subcategory": "투자",
        "text": "2) 비용(서비스 이용료, 외주용역비 등)",
        "type": "number",
        "parent_question_id": "Q3",
        "sort_order": 40,
        "help_text": "클라우드 보안 서비스, 보안 관제, 컨설팅 비용 등"
    },
    {
        "id": "Q6", "display_number": "Q1-1-2-3", "level": 3, "category_id": 1,
        "category": "정보보호 투자", "subcategory": "투자",
        "text": "3) 내부 전담인력 인건비(급여, 상여, 퇴직급여 등)",
        "type": "number",
        "parent_question_id": "Q3",
        "sort_order": 45,
        "help_text": "정보보호 업무만을 전담하는 인력의 인건비"
    },
    {
        "id": "Q27", "display_number": "Q1-1-3", "level": 2, "category_id": 1,
        "category": "정보보호 투자", "subcategory": "투자",
        "text": "주요 투자 항목 (정보보호 투자의 주요 내역을 기재)",
        "type": "textarea",
        "parent_question_id": "Q1",
        "sort_order": 50,
        "help_text": "예: 방화벽 도입, 보안관제 서비스, 취약점 진단 등"
    },
    {
        "id": "Q7", "display_number": "Q1-2", "level": 1, "category_id": 1,
        "category": "정보보호 투자", "subcategory": "투자 계획",
        "text": "향후(차기 연도) 정보보호 투자 계획이 있으신가요?",
        "type": "yes_no",
        "dependent_question_ids": ["Q8"],
        "sort_order": 60
    },
    {
        "id": "Q8", "display_number": "Q1-2-1", "level": 2, "category_id": 1,
        "category": "정보보호 투자", "subcategory": "투자 계획",
        "text": "예정 투자액 (원)",
        "type": "number",
        "parent_question_id": "Q7",
        "sort_order": 70
    },

    # ============================================================
    # 카테고리 2: 정보보호 인력
    # ============================================================
    {
        "id": "Q9", "display_number": "Q2-1", "level": 1, "category_id": 2,
        "category": "정보보호 인력", "subcategory": "정보보호 인력",
        "text": "정보보호 전담 부서 또는 전담 인력이 있나요?",
        "type": "yes_no",
        "dependent_question_ids": ["Q10", "Q28", "Q11", "Q12"],
        "sort_order": 80
    },
    {
        "id": "Q10", "display_number": "Q2-1-1", "level": 2, "category_id": 2,
        "category": "정보보호 인력", "subcategory": "인력",
        "text": "총 임직원 수 (월평균 간이세액 인원)",
        "type": "number",
        "parent_question_id": "Q9",
        "sort_order": 90,
        "help_text": "매월 간이세액 신고 인원의 12개월 평균"
    },
    {
        "id": "Q28", "display_number": "Q2-1-2", "level": 2, "category_id": 2,
        "category": "정보보호 인력", "subcategory": "인력",
        "text": "정보기술부문 인력 수(C) (IT 전체 인력)",
        "type": "number",
        "parent_question_id": "Q9",
        "sort_order": 95,
        "help_text": "IT 관련 업무를 수행하는 전체 인력 수 (정보보호 인력 포함)"
    },
    {
        "id": "Q11", "display_number": "Q2-1-3", "level": 2, "category_id": 2,
        "category": "정보보호 인력", "subcategory": "인력",
        "text": "내부 전담인력 수(D1) (월평균, 소수점 포함)",
        "type": "number",
        "parent_question_id": "Q9",
        "sort_order": 100,
        "help_text": "정보보호 전담 조직에 속한 내부 인원(월평균)"
    },
    {
        "id": "Q12", "display_number": "Q2-1-4", "level": 2, "category_id": 2,
        "category": "정보보호 인력", "subcategory": "인력",
        "text": "외주 전담인력 수(D2) (계약서 M/M 기반 월평균)",
        "type": "number",
        "parent_question_id": "Q9",
        "sort_order": 110,
        "help_text": "외주 인력 중 정보보호 업무 전담 인원(월평균)"
    },
    {
        "id": "Q13", "display_number": "Q2-2", "level": 1, "category_id": 2,
        "category": "정보보호 인력", "subcategory": "CISO/CPO",
        "text": "최고책임자(CISO/CPO) 지정 현황",
        "type": "yes_no",
        "dependent_question_ids": ["Q14", "Q29"],
        "sort_order": 120
    },
    {
        "id": "Q14", "display_number": "Q2-2-1", "level": 2, "category_id": 2,
        "category": "정보보호 인력", "subcategory": "CISO/CPO",
        "text": "CISO/CPO 상세 현황",
        "type": "table",
        "options": ["이름", "직급", "임원여부(Y/N)", "겸직여부(Y/N)"],
        "parent_question_id": "Q13",
        "sort_order": 130
    },
    {
        "id": "Q29", "display_number": "Q2-2-2", "level": 2, "category_id": 2,
        "category": "정보보호 인력", "subcategory": "CISO/CPO",
        "text": "CISO/CPO 주요 활동 내역",
        "type": "textarea",
        "parent_question_id": "Q13",
        "sort_order": 135,
        "help_text": "예: 보안정책 수립, 보안교육 실시, 보안점검 수행, 침해대응 등"
    },

    # ============================================================
    # 카테고리 3: 정보보호 인증
    # ============================================================
    {
        "id": "Q15", "display_number": "Q3-1", "level": 1, "category_id": 3,
        "category": "정보보호 인증", "subcategory": "인증/평가",
        "text": "ISMS, ISO27001 등 유효한 인증이 있나요?",
        "type": "yes_no",
        "dependent_question_ids": ["Q16"],
        "sort_order": 140
    },
    {
        "id": "Q16", "display_number": "Q3-1-1", "level": 2, "category_id": 3,
        "category": "정보보호 인증", "subcategory": "인증/평가",
        "text": "인증 보유 현황",
        "type": "table",
        "options": ["인증종류", "유효기간", "발행기관"],
        "parent_question_id": "Q15",
        "sort_order": 150
    },

    # ============================================================
    # 카테고리 4: 정보보호 활동
    # ============================================================
    {
        "id": "Q17", "display_number": "Q4-1", "level": 1, "category_id": 4,
        "category": "정보보호 활동", "subcategory": "보호 활동",
        "text": "이용자 보호를 위한 활동이 있나요?",
        "type": "yes_no",
        "dependent_question_ids": ["Q18", "Q19", "Q20", "Q21", "Q22", "Q23", "Q24", "Q25", "Q26"],
        "sort_order": 160,
        "help_text": "가이드라인에 명시된 주요 정보보호 관련 활동 수행 현황을 입력합니다."
    },
    {
        "id": "Q18", "display_number": "Q4-1-1", "level": 2, "category_id": 4,
        "category": "정보보호 활동", "subcategory": "보호 활동",
        "text": "IT 자산 식별 및 관리 현황",
        "type": "select",
        "options": ["미수행", "기초관리(엑셀 등)", "자산관리시스템 운영", "정기적 현행화 및 점검"],
        "parent_question_id": "Q17",
        "sort_order": 170,
        "help_text": "정보보호의 기본인 IT 자산(H/W, S/W) 목록 관리 및 최신화 여부"
    },
    {
        "id": "Q19", "display_number": "Q4-1-2", "level": 2, "category_id": 4,
        "category": "정보보호 활동", "subcategory": "보호 활동",
        "text": "임직원 정보보호 교육 및 훈련 실적",
        "type": "table",
        "options": ["교육구분(임직원/협력사)", "실시횟수(연간)", "이수율(%)"],
        "parent_question_id": "Q17",
        "sort_order": 180,
        "help_text": "정기 보안 교육, 캠페인 등 인식 제고 활동"
    },
    {
        "id": "Q20", "display_number": "Q4-1-3", "level": 2, "category_id": 4,
        "category": "정보보호 활동", "subcategory": "보호 활동",
        "text": "정보보호 지침 및 절차서 수립/관리",
        "type": "yes_no",
        "parent_question_id": "Q17",
        "sort_order": 190
    },
    {
        "id": "Q21", "display_number": "Q4-1-4", "level": 2, "category_id": 4,
        "category": "정보보호 활동", "subcategory": "보호 활동",
        "text": "정보시스템 취약점 분석 및 평가",
        "type": "select",
        "options": ["미수행", "자체 점검(간이)", "정기 점검(연 1회 이상)", "상시 취약점 관리체계"],
        "parent_question_id": "Q17",
        "sort_order": 200,
        "help_text": "서버, 네트워크, DB, 웹/앱 등에 대한 보안 취약점 점검"
    },
    {
        "id": "Q22", "display_number": "Q4-1-5", "level": 2, "category_id": 4,
        "category": "정보보호 활동", "subcategory": "보호 활동",
        "text": "제로트러스트(Zero Trust) 도입 단계",
        "type": "select",
        "options": ["도입전", "계획수립", "기초운영", "고도화단계"],
        "parent_question_id": "Q17",
        "sort_order": 210
    },
    {
        "id": "Q23", "display_number": "Q4-1-6", "level": 2, "category_id": 4,
        "category": "정보보호 활동", "subcategory": "보호 활동",
        "text": "공급망 보안(SBOM) 관리 및 조치 (건)",
        "type": "number",
        "parent_question_id": "Q17",
        "sort_order": 220
    },
    {
        "id": "Q24", "display_number": "Q4-1-7", "level": 2, "category_id": 4,
        "category": "정보보호 활동", "subcategory": "보호 활동",
        "text": "사이버 위협정보 분석/공유시스템(C-TAS) 참여",
        "type": "checkbox",
        "options": ["C-TAS 정회원", "C-TAS 준회원", "기타 보안커뮤니티 활동"],
        "parent_question_id": "Q17",
        "sort_order": 230
    },
    {
        "id": "Q25", "display_number": "Q4-1-8", "level": 2, "category_id": 4,
        "category": "정보보호 활동", "subcategory": "보호 활동",
        "text": "사이버 위기대응 모의훈련 (DDoS, 랜섬웨어 등)",
        "type": "table",
        "options": ["훈련종류", "실시일자", "참여인원"],
        "parent_question_id": "Q17",
        "sort_order": 240
    },
    {
        "id": "Q26", "display_number": "Q4-1-9", "level": 2, "category_id": 4,
        "category": "정보보호 활동", "subcategory": "보호 활동",
        "text": "침해사고 배상책임보험 또는 준비금 가입",
        "type": "yes_no",
        "parent_question_id": "Q17",
        "sort_order": 250,
        "help_text": "사고 발생 시 이용자 피해 보상을 위한 보험 가입 또는 적립금 여부"
    },
]


def upgrade(conn):
    print(f"  {len(QUESTIONS)}개의 질문을 삽입합니다...")

    for q in QUESTIONS:
        options = json.dumps(q["options"], ensure_ascii=False) if "options" in q else None
        dep_ids = json.dumps(q["dependent_question_ids"], ensure_ascii=False) if "dependent_question_ids" in q else None

        conn.execute('''
            INSERT INTO isd_questions
            (id, display_number, level, category_id, category, subcategory,
             text, type, options, parent_question_id, dependent_question_ids,
             sort_order, help_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            q["id"], q.get("display_number"), q["level"], q["category_id"],
            q["category"], q.get("subcategory"), q["text"], q["type"],
            options, q.get("parent_question_id"), dep_ids,
            q["sort_order"], q.get("help_text")
        ))

    print(f"  [OK] {len(QUESTIONS)}개 질문 삽입 완료.")


def downgrade(conn):
    conn.execute('DELETE FROM isd_questions')
    print("  [OK] 질문 데이터 삭제 완료.")
