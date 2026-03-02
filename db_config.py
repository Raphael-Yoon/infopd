"""
infopd 데이터베이스 설정 및 연결 관리
SQLite 전용
"""
import sqlite3
import os
from contextlib import contextmanager
from pathlib import Path

_DB_DIR = Path(__file__).parent.resolve()
SQLITE_DATABASE = os.getenv('INFOPD_DB_PATH', str(_DB_DIR / 'infopd.db'))


def get_db_connection():
    """SQLite 연결 반환"""
    conn = sqlite3.connect(SQLITE_DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db():
    """컨텍스트 매니저로 데이터베이스 연결 제공"""
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()
