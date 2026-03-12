"""
Audit Trail: isd_answer_history 테이블 생성

답변 변경 이력을 보존하여 감사 추적(Audit Trail)을 지원한다.
K-SOX 공시 감사 기준: 누가, 언제, 무엇을 변경했는지 기록 필수.
"""


def upgrade(conn):
    conn.execute('''
        CREATE TABLE IF NOT EXISTS isd_answer_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id  TEXT    NOT NULL,
            year        INTEGER NOT NULL,
            question_id TEXT    NOT NULL,
            old_value   TEXT,
            new_value   TEXT,
            changed_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            changed_by  TEXT    DEFAULT 'system'
        )
    ''')
    conn.execute(
        'CREATE INDEX IF NOT EXISTS idx_answer_history_target '
        'ON isd_answer_history (company_id, year, question_id)'
    )


def downgrade(conn):
    conn.execute('DROP TABLE IF EXISTS isd_answer_history')
    conn.execute('DROP INDEX IF EXISTS idx_answer_history_target')
