"""
013_q29_evidence_list.py

Q29(CISO/CPO 주요 활동내역, II-6) evidence_list 추가

양필조 검토 의견:
II-6은 공시 서식에 명시된 항목으로, CISO/CPO의 실제 활동 여부를
검증하기 위한 근거 서류가 필요함.
- 이사회·경영진 보고 활동 → 보고 자료 또는 회의록
- 예산 심의 → 예산 심의 회의록
- 정책·지침 수립 → 정보보호 정책서
활동 유형이 다양하므로 "CISO/CPO 활동 근거 서류"로 포괄 표기.
"""

import json


def upgrade(conn):
    conn.execute(
        "UPDATE isd_questions SET evidence_list=? WHERE id='Q29'",
        (json.dumps(["CISO/CPO 활동 근거 서류 (회의록, 보고자료 등)"], ensure_ascii=False),)
    )
    conn.commit()


def downgrade(conn):
    conn.execute(
        "UPDATE isd_questions SET evidence_list=NULL WHERE id='Q29'"
    )
    conn.commit()
