"""
Migration 015: 테이블 prefix ipd_ → isd_ 변경

기존 ipd_ prefix 테이블을 isd_(Information Security Disclosure) prefix로 일괄 변경.
ipd_migration_history는 migration_manager._ensure_migration_table()에서 자동 처리됨.
"""

TABLES = [
    ('ipd_companies', 'isd_companies'),
    ('ipd_targets', 'isd_targets'),
    ('ipd_questions', 'isd_questions'),
    ('ipd_answers', 'isd_answers'),
    ('ipd_evidence', 'isd_evidence'),
    ('ipd_sessions', 'isd_sessions'),
    ('ipd_submissions', 'isd_submissions'),
    ('ipd_answer_history', 'isd_answer_history'),
]


def upgrade(conn):
    """ipd_ → isd_ 테이블 rename (존재하는 테이블만 처리)"""
    existing = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    for old_name, new_name in TABLES:
        if old_name in existing:
            conn.execute(f'ALTER TABLE {old_name} RENAME TO {new_name}')


def downgrade(conn):
    """isd_ → ipd_ 테이블 rename 롤백"""
    existing = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    for old_name, new_name in TABLES:
        if new_name in existing:
            conn.execute(f'ALTER TABLE {new_name} RENAME TO {old_name}')
