"""
010_writer_qa_wording_fix.py

작가팀 문구 검토 결과 반영 — 질문 표현 통일
대상: Q7, Q9, Q13, Q26

1. Q7  어조 통일: '있으신가요?' → '있나요?'
2. Q9  후행 공백 제거
3. Q13 질문형 전환: '지정 여부' → '지정되어 있나요?'
4. Q26 어법 오류 수정 + 질문형 전환 (본문 + help_text)
"""


def upgrade(conn):
    # 1. Q7 어조 통일
    conn.execute(
        "UPDATE isd_questions SET text='향후(차기 연도) 정보보호 투자 계획이 있나요?' WHERE id='Q7'"
    )

    # 2. Q9 후행 공백 제거
    conn.execute(
        "UPDATE isd_questions SET text='정보보호 전담 부서 또는 전담 인력이 있나요?' WHERE id='Q9'"
    )

    # 3. Q13 질문형 전환
    conn.execute(
        "UPDATE isd_questions SET text='최고책임자(CISO/CPO)가 지정되어 있나요?' WHERE id='Q13'"
    )

    # 4. Q26 어법 오류 수정 + 질문형 전환 (본문 + help_text)
    conn.execute(
        """UPDATE isd_questions
           SET text='침해사고 배상책임보험에 가입하거나 배상 준비금을 적립하고 있나요?',
               help_text='사고 발생 시 이용자 피해 보상을 위한 배상책임보험 가입 또는 배상 준비금 적립 여부를 확인합니다.'
           WHERE id='Q26'"""
    )

    conn.commit()


def downgrade(conn):
    conn.execute(
        "UPDATE isd_questions SET text='향후(차기 연도) 정보보호 투자 계획이 있으신가요?' WHERE id='Q7'"
    )
    conn.execute(
        "UPDATE isd_questions SET text='정보보호 전담 부서 또는 전담 인력이 있나요? ' WHERE id='Q9'"
    )
    conn.execute(
        "UPDATE isd_questions SET text='최고책임자(CISO/CPO) 지정 여부' WHERE id='Q13'"
    )
    conn.execute(
        """UPDATE isd_questions
           SET text='침해사고 배상책임보험 또는 준비금 가입',
               help_text='사고 발생 시 이용자 피해 보상을 위한 보험 가입 또는 적립금 여부'
           WHERE id='Q26'"""
    )
    conn.commit()
