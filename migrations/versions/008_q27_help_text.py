"""
Q27 help_text 보강 — 주요 투자 항목 입력 가이드 구체화

양필조 검토 의견 ⑦: Q27(주요 투자 항목)은 자유 입력 필드이나,
공시 지침에 따라 투자 유형별(유/무형자산, 서비스, 인건비)로 구분하여
구체적 항목명을 기재해야 적정 공시로 인정됨.
"""


def upgrade(conn):
    conn.execute(
        "UPDATE isd_questions SET help_text = ? WHERE id = 'Q27'",
        (
            '투자 유형별로 항목명과 금액을 구체적으로 기재하세요.\n'
            '예) 유/무형자산: 방화벽 장비 구입(○○만원), 보안SW 라이선스(○○만원)\n'
            '    서비스: 보안관제 서비스(○○만원), 취약점 진단(○○만원)\n'
            '    인건비: 정보보호 전담인력 인건비(○○만원)',
        )
    )


def downgrade(conn):
    conn.execute(
        "UPDATE isd_questions SET help_text = ? WHERE id = 'Q27'",
        ('예: 방화벽 도입, 보안관제 서비스, 취약점 진단 등',)
    )
