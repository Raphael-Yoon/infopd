"""
012_fix_q10_evidence_list.py

Q10(총 임직원 수) evidence_list 수정

양필조 검토 의견:
- 기존: IT 인력 현황표, 조직도  ← II-2(IT 인력) 증빙과 중복, 총 임직원 근거로 부적절
- 변경: 4대보험 가입자 명부, 간이세액징수 신고서
  → 총 임직원 수는 '월평균 간이세액 인원' 기준이므로
    4대보험 또는 간이세액 신고서가 실제 근거 서류
"""

import json


def upgrade(conn):
    conn.execute(
        "UPDATE isd_questions SET evidence_list=? WHERE id='Q10'",
        (json.dumps(["4대보험 가입자 명부", "간이세액징수 신고서"], ensure_ascii=False),)
    )
    conn.commit()


def downgrade(conn):
    conn.execute(
        "UPDATE isd_questions SET evidence_list=? WHERE id='Q10'",
        (json.dumps(["IT 인력 현황표", "조직도"], ensure_ascii=False),)
    )
    conn.commit()
