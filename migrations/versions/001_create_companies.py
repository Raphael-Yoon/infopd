"""
회사 및 공시 대상 테이블 생성
- ipd_companies : 회사 기본 정보
- ipd_targets   : 공시 대상 (회사 + 연도)
"""


def upgrade(conn):
    conn.execute('''
        CREATE TABLE IF NOT EXISTS ipd_companies (
            id         TEXT PRIMARY KEY,
            name       TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS ipd_targets (
            id         TEXT PRIMARY KEY,
            company_id TEXT NOT NULL,
            year       INTEGER NOT NULL,
            status     TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES ipd_companies(id),
            UNIQUE(company_id, year)
        )
    ''')

    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_ipd_targets_company
        ON ipd_targets(company_id)
    ''')


def downgrade(conn):
    conn.execute('DROP INDEX IF EXISTS idx_ipd_targets_company')
    conn.execute('DROP TABLE IF EXISTS ipd_targets')
    conn.execute('DROP TABLE IF EXISTS ipd_companies')
