"""
인력 관련 질문 help_text 보강 — 월평균 계산 기준 안내 추가

양필조 검토 의견 ⑧: 인력 입력 항목에 월평균 산정 기준이 명시되지 않아
담당자가 기준을 잘못 적용할 수 있음. 공시 지침 기준으로 각 항목별
산정 방식을 help_text에 명시한다.
"""


def upgrade(conn):
    updates = [
        (
            'Q10',
            '매월 간이세액 신고 인원의 12개월 평균 (월별 인원 합산 ÷ 12).\n'
            '예) 1월 100명 ~ 12월 120명 → 합산 후 12로 나눔.'
        ),
        (
            'Q28',
            'IT 관련 업무를 수행하는 전체 인력의 월평균 인원수 (정보보호 인력 포함).\n'
            '총 임직원 수(Q2-1-1)와 동일한 기준으로 월별 IT 인원 합산 ÷ 12.'
        ),
        (
            'Q11',
            '정보보호 전담 조직 내부 인원의 월평균 인원수 (소수점 허용).\n'
            '예) 연간 6개월 전담 근무자 1명 → 0.5명으로 산정.'
        ),
        (
            'Q12',
            '외주 정보보호 전담 인력의 월평균 인원수 (계약서 M/M 기준).\n'
            '예) 연간 계약 6M/M → 0.5명. 계약서에 M/M이 명기되어야 함.'
        ),
    ]
    for qid, help_text in updates:
        conn.execute(
            'UPDATE isd_questions SET help_text = ? WHERE id = ?',
            (help_text, qid)
        )


def downgrade(conn):
    originals = [
        ('Q10', '매월 간이세액 신고 인원의 12개월 평균'),
        ('Q28', 'IT 관련 업무를 수행하는 전체 인력 수 (정보보호 인력 포함)'),
        ('Q11', '정보보호 전담 조직에 속한 내부 인원(월평균)'),
        ('Q12', '외주 인력 중 정보보호 업무 전담 인원(월평균)'),
    ]
    for qid, help_text in originals:
        conn.execute(
            'UPDATE isd_questions SET help_text = ? WHERE id = ?',
            (help_text, qid)
        )
