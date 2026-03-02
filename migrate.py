#!/usr/bin/env python
"""
infopd 데이터베이스 마이그레이션 스크립트

사용법:
    python migrate.py status              # 현재 마이그레이션 상태 확인
    python migrate.py upgrade             # 모든 마이그레이션 적용
    python migrate.py upgrade --target 002 # 특정 버전까지 마이그레이션
    python migrate.py downgrade --target 001 # 특정 버전으로 롤백
"""
import sys
import argparse
from pathlib import Path

# 이 파일 위치 기준으로 경로 설정
_APP_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(_APP_DIR))

from migrations.migration_manager import MigrationManager


def main():
    parser = argparse.ArgumentParser(description='infopd 데이터베이스 마이그레이션 도구')
    parser.add_argument('command', choices=['status', 'upgrade', 'downgrade'])
    parser.add_argument('--target', type=str, help='타겟 마이그레이션 버전')
    parser.add_argument('--database', type=str, default=str(_APP_DIR / 'infopd.db'))
    args = parser.parse_args()

    manager = MigrationManager(args.database)

    try:
        if args.command == 'status':
            manager.status()

        elif args.command == 'upgrade':
            print(f"\n데이터베이스: {args.database}")
            print("=" * 70)
            success = manager.upgrade(target_version=args.target)
            return 0 if success else 1

        elif args.command == 'downgrade':
            if not args.target:
                print("오류: downgrade 명령에는 --target 옵션이 필요합니다.")
                return 1
            response = input(f"\n버전 {args.target}로 롤백하시겠습니까? (yes/no): ")
            if response.lower() not in ['yes', 'y']:
                print("롤백이 취소되었습니다.")
                return 0
            success = manager.downgrade(target_version=args.target)
            return 0 if success else 1

    except KeyboardInterrupt:
        print("\n작업이 중단되었습니다.")
        return 130
    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
