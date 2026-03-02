"""
infopd 데이터베이스 마이그레이션 관리 클래스
"""
import sqlite3
import importlib.util
from datetime import datetime
from pathlib import Path


class MigrationManager:
    """데이터베이스 마이그레이션을 관리하는 클래스"""

    def __init__(self, database_path='infopd.db'):
        self.database_path = database_path
        self.migrations_dir = Path(__file__).parent / 'versions'
        self._ensure_migration_table()

    def _get_connection(self):
        """데이터베이스 연결 생성"""
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_migration_table(self):
        """마이그레이션 이력 테이블 생성"""
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS ipd_migration_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    execution_time_ms INTEGER,
                    status TEXT DEFAULT 'success'
                )
            ''')
            conn.commit()

    def _get_applied_migrations(self):
        """적용된 마이그레이션 목록 조회"""
        with self._get_connection() as conn:
            cursor = conn.execute('''
                SELECT version FROM ipd_migration_history
                WHERE status = 'success'
                ORDER BY version
            ''')
            return [row['version'] for row in cursor.fetchall()]

    def _get_available_migrations(self):
        """사용 가능한 마이그레이션 파일 목록"""
        migrations = []
        if not self.migrations_dir.exists():
            return migrations
        for file in sorted(self.migrations_dir.glob('*.py')):
            if file.name.startswith('__'):
                continue
            version = file.stem.split('_')[0]
            name = '_'.join(file.stem.split('_')[1:])
            migrations.append({'version': version, 'name': name, 'file_path': file})
        return migrations

    def _load_migration_module(self, file_path):
        """마이그레이션 파일을 동적으로 로드"""
        spec = importlib.util.spec_from_file_location("migration", file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _record_migration(self, version, name, execution_time_ms, status='success'):
        """마이그레이션 실행 이력 기록"""
        with self._get_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO ipd_migration_history (version, name, execution_time_ms, status)
                VALUES (?, ?, ?, ?)
            ''', (version, name, execution_time_ms, status))
            conn.commit()

    def _remove_migration_record(self, version):
        """마이그레이션 이력 제거 (롤백 시)"""
        with self._get_connection() as conn:
            conn.execute('DELETE FROM ipd_migration_history WHERE version = ?', (version,))
            conn.commit()

    def status(self):
        """현재 마이그레이션 상태 조회"""
        applied = set(self._get_applied_migrations())
        available = self._get_available_migrations()
        print("=" * 70)
        print("infopd 데이터베이스 마이그레이션 상태")
        print("=" * 70)
        print(f"데이터베이스: {self.database_path}")
        print("-" * 70)
        if not available:
            print("사용 가능한 마이그레이션이 없습니다.")
            return
        for migration in available:
            version = migration['version']
            name = migration['name']
            status = "[OK] 적용됨" if version in applied else "[  ] 대기 중"
            print(f"{status}  [{version}] {name}")
        print("-" * 70)
        print(f"전체: {len(available)}개 / 적용됨: {len(applied)}개 / 대기 중: {len(available) - len(applied)}개")
        print("=" * 70)

    def upgrade(self, target_version=None):
        """마이그레이션 업그레이드 실행"""
        applied = set(self._get_applied_migrations())
        available = self._get_available_migrations()
        to_apply = []
        for migration in available:
            version = migration['version']
            if version in applied:
                continue
            if target_version and version > target_version:
                break
            to_apply.append(migration)
        if not to_apply:
            print("적용할 마이그레이션이 없습니다.")
            return True
        print(f"\n{len(to_apply)}개의 마이그레이션을 적용합니다...\n")
        for migration in to_apply:
            version = migration['version']
            name = migration['name']
            print(f"[{version}] {name} 적용 중...", end=' ')
            try:
                module = self._load_migration_module(migration['file_path'])
                start_time = datetime.now()
                with self._get_connection() as conn:
                    module.upgrade(conn)
                    conn.commit()
                ms = int((datetime.now() - start_time).total_seconds() * 1000)
                self._record_migration(version, name, ms, 'success')
                print(f"[OK] 완료 ({ms}ms)")
            except Exception as e:
                print(f"[FAIL] 실패\n  오류: {e}")
                import traceback
                traceback.print_exc()
                self._record_migration(version, name, 0, 'failed')
                return False
        print(f"\n마이그레이션이 성공적으로 완료되었습니다.")
        return True

    def downgrade(self, target_version):
        """마이그레이션 다운그레이드 (롤백) 실행"""
        applied = sorted(self._get_applied_migrations(), reverse=True)
        available = {m['version']: m for m in self._get_available_migrations()}
        to_rollback = [available[v] for v in applied if v > target_version and v in available]
        if not to_rollback:
            print("롤백할 마이그레이션이 없습니다.")
            return True
        print(f"\n{len(to_rollback)}개의 마이그레이션을 롤백합니다...\n")
        for migration in to_rollback:
            version = migration['version']
            name = migration['name']
            print(f"[{version}] {name} 롤백 중...", end=' ')
            try:
                module = self._load_migration_module(migration['file_path'])
                if not hasattr(module, 'downgrade'):
                    print(f"[FAIL] downgrade 함수 없음")
                    return False
                start_time = datetime.now()
                with self._get_connection() as conn:
                    module.downgrade(conn)
                    conn.commit()
                ms = int((datetime.now() - start_time).total_seconds() * 1000)
                self._remove_migration_record(version)
                print(f"[OK] 완료 ({ms}ms)")
            except Exception as e:
                print(f"[FAIL] 실패\n  오류: {e}")
                import traceback
                traceback.print_exc()
                return False
        print(f"\n롤백이 성공적으로 완료되었습니다.")
        return True
