"""
공시 관련 테이블 생성
- isd_questions  : 공시 질문 마스터 (고정)
- isd_answers    : 공시 답변
- isd_evidence   : 증빙 자료
- isd_sessions   : 공시 세션 (회사+연도 단위)
- isd_submissions: 공시 제출 기록
"""


def upgrade(conn):
    # 질문 마스터 테이블
    conn.execute('''
        CREATE TABLE IF NOT EXISTS isd_questions (
            id                   TEXT PRIMARY KEY,
            display_number       TEXT,
            level                INTEGER NOT NULL,
            category_id          INTEGER NOT NULL,
            category             TEXT NOT NULL,
            subcategory          TEXT,
            text                 TEXT NOT NULL,
            type                 TEXT NOT NULL,
            options              TEXT,
            parent_question_id   TEXT,
            dependent_question_ids TEXT,
            required             INTEGER DEFAULT 1,
            help_text            TEXT,
            evidence_list        TEXT,
            sort_order           INTEGER DEFAULT 0,
            created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_isd_questions_sort
        ON isd_questions(sort_order)
    ''')

    # 답변 테이블
    conn.execute('''
        CREATE TABLE IF NOT EXISTS isd_answers (
            id          TEXT PRIMARY KEY,
            question_id TEXT NOT NULL,
            company_id  TEXT NOT NULL,
            year        INTEGER NOT NULL,
            value       TEXT,
            status      TEXT DEFAULT 'pending',
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deleted_at  TIMESTAMP,
            FOREIGN KEY (question_id) REFERENCES isd_questions(id),
            FOREIGN KEY (company_id)  REFERENCES isd_companies(id),
            UNIQUE(question_id, company_id, year)
        )
    ''')

    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_isd_answers_company_year
        ON isd_answers(company_id, year)
    ''')

    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_isd_answers_question_company
        ON isd_answers(question_id, company_id)
    ''')

    # 증빙 자료 테이블
    conn.execute('''
        CREATE TABLE IF NOT EXISTS isd_evidence (
            id            TEXT PRIMARY KEY,
            answer_id     TEXT,
            question_id   TEXT,
            company_id    TEXT NOT NULL,
            year          INTEGER NOT NULL,
            file_name     TEXT NOT NULL,
            file_url      TEXT NOT NULL,
            file_size     INTEGER,
            file_type     TEXT,
            evidence_type TEXT,
            uploaded_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (answer_id)   REFERENCES isd_answers(id),
            FOREIGN KEY (question_id) REFERENCES isd_questions(id),
            FOREIGN KEY (company_id)  REFERENCES isd_companies(id)
        )
    ''')

    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_isd_evidence_answer
        ON isd_evidence(answer_id)
    ''')

    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_isd_evidence_company_year
        ON isd_evidence(company_id, year)
    ''')

    # 공시 세션 테이블 (회사+연도 단위 작업 상태)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS isd_sessions (
            id                  TEXT PRIMARY KEY,
            company_id          TEXT NOT NULL,
            year                INTEGER NOT NULL,
            status              TEXT DEFAULT 'draft',
            total_questions     INTEGER DEFAULT 0,
            answered_questions  INTEGER DEFAULT 0,
            completion_rate     INTEGER DEFAULT 0,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            submitted_at        TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES isd_companies(id),
            UNIQUE(company_id, year)
        )
    ''')

    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_isd_sessions_company
        ON isd_sessions(company_id)
    ''')

    # 공시 제출 기록 테이블
    conn.execute('''
        CREATE TABLE IF NOT EXISTS isd_submissions (
            id                  TEXT PRIMARY KEY,
            session_id          TEXT NOT NULL,
            company_id          TEXT NOT NULL,
            year                INTEGER NOT NULL,
            submission_data     TEXT,
            submission_details  TEXT,
            submitted_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            confirmation_number TEXT,
            status              TEXT DEFAULT 'draft',
            FOREIGN KEY (session_id)  REFERENCES isd_sessions(id),
            FOREIGN KEY (company_id)  REFERENCES isd_companies(id)
        )
    ''')

    conn.execute('''
        CREATE INDEX IF NOT EXISTS idx_isd_submissions_company_year
        ON isd_submissions(company_id, year)
    ''')


def downgrade(conn):
    conn.execute('DROP INDEX IF EXISTS idx_isd_submissions_company_year')
    conn.execute('DROP INDEX IF EXISTS idx_isd_sessions_company')
    conn.execute('DROP INDEX IF EXISTS idx_isd_evidence_company_year')
    conn.execute('DROP INDEX IF EXISTS idx_isd_evidence_answer')
    conn.execute('DROP INDEX IF EXISTS idx_isd_answers_question_company')
    conn.execute('DROP INDEX IF EXISTS idx_isd_answers_company_year')
    conn.execute('DROP INDEX IF EXISTS idx_isd_questions_sort')

    conn.execute('DROP TABLE IF EXISTS isd_submissions')
    conn.execute('DROP TABLE IF EXISTS isd_sessions')
    conn.execute('DROP TABLE IF EXISTS isd_evidence')
    conn.execute('DROP TABLE IF EXISTS isd_answers')
    conn.execute('DROP TABLE IF EXISTS isd_questions')
