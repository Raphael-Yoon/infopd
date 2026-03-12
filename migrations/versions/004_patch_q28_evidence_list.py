"""
Q28(정보기술부문 인력 수) evidence_list 누락 패치

양필조 검토 의견: Q28은 IT 전체 인력 수 공시 항목으로,
인접 항목(Q10 총 임직원 수)과 동일하게 IT 인력 현황표·조직도가
근거 서류로 필요하다.
"""

import json


def upgrade(conn):
    conn.execute(
        "UPDATE isd_questions SET evidence_list = ? WHERE id = 'Q28'",
        (json.dumps(["IT 인력 현황표", "조직도"], ensure_ascii=False),)
    )


def downgrade(conn):
    conn.execute(
        "UPDATE isd_questions SET evidence_list = NULL WHERE id = 'Q28'"
    )
