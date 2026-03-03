"""
infosd Playwright Unit 테스트 베이스 클래스 및 유틸리티

Playwright를 활용한 E2E 테스트의 기본 기능을 제공합니다.
- 브라우저 설정
- 공통 페이지 액션
- 스크린샷 캡처
- 테스트 결과 리포팅

(snowball playwright_base.py 구조 참조, infosd 포트 5001로 적용)
"""

import os
import sys
import re
import time
import subprocess
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from enum import Enum

from playwright.sync_api import Page, Browser, BrowserContext, Playwright, sync_playwright

# 프로젝트 루트 경로
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestStatus(Enum):
    """테스트 상태"""
    RUNNING = "🔄"
    PASSED  = "✅"
    FAILED  = "❌"
    WARNING = "⚠️"
    SKIPPED = "⊘"


class UnitTestResult:
    """Unit 테스트 결과 클래스"""

    def __init__(self, test_name: str, category: str):
        self.test_name = test_name
        self.category = category
        self.status = TestStatus.RUNNING
        self.message = ""
        self.details: List[str] = []
        self.screenshots: List[str] = []
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

    def start(self):
        self.start_time = datetime.now()
        self.status = TestStatus.RUNNING

    def pass_test(self, message: str = "테스트 통과"):
        self.status = TestStatus.PASSED
        self.message = message
        self.end_time = datetime.now()

    def fail_test(self, message: str):
        self.status = TestStatus.FAILED
        self.message = message
        self.end_time = datetime.now()

    def warn_test(self, message: str):
        self.status = TestStatus.WARNING
        self.message = message
        self.end_time = datetime.now()

    def skip_test(self, message: str = "건너뜀"):
        self.status = TestStatus.SKIPPED
        self.message = message
        self.end_time = datetime.now()

    def add_detail(self, detail: str):
        self.details.append(detail)

    def add_screenshot(self, screenshot_path: str):
        self.screenshots.append(screenshot_path)

    def get_duration(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    def __str__(self):
        dur = f"({self.get_duration():.2f}s)" if self.end_time else ""
        return f"{self.status.value} {self.test_name} {dur} - {self.message}"


class PlaywrightTestBase:
    """infosd Playwright 테스트 베이스 클래스"""

    def __init__(self, base_url: str = "http://localhost:5001",
                 headless: bool = True, slow_mo: int = 0):
        self.base_url = base_url
        self.headless = headless
        self.slow_mo = slow_mo
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.results: List[UnitTestResult] = []

        self.server_process: Optional[subprocess.Popen] = None
        self.server_was_running: bool = False

        self.screenshot_dir = project_root / "test" / "screenshots"
        self.screenshot_dir.mkdir(exist_ok=True)

    # ─── 서버 관리 ───────────────────────────────────────────
    def check_server_running(self) -> bool:
        """기존 서버 종료 후 재시작 (환경변수 반영 보장)"""
        port = int(self.base_url.split(':')[-1])
        print(f"🧹 기존 포트({port}) 정리 중...")
        try:
            output = subprocess.check_output(
                f"netstat -ano | findstr LISTENING | findstr :{port}",
                shell=True
            ).decode()
            for line in output.splitlines():
                parts = line.strip().split()
                if len(parts) > 4 and parts[1].endswith(f":{port}"):
                    pid = parts[-1]
                    if pid != "0" and int(pid) != os.getpid():
                        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
                        print(f"   종료된 PID: {pid}")
        except Exception:
            pass

        print(f"🚀 infosd 서버 시작 중... ({self.base_url})")
        self.server_was_running = False
        return self._start_server()

    def _start_server(self) -> bool:
        try:
            self.server_process = subprocess.Popen(
                [sys.executable, "infosd.py"],
                cwd=str(project_root),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
            )
            print(f"   서버 PID: {self.server_process.pid}")
            for i in range(30):
                time.sleep(1)
                try:
                    r = requests.get(f"{self.base_url}/health", timeout=2)
                    if r.status_code == 200:
                        print("✅ 서버 시작 완료")
                        return True
                except Exception:
                    print(f"   대기 중... ({i+1}/30)")
            print("❌ 서버 시작 시간 초과")
            return False
        except Exception as e:
            print(f"❌ 서버 시작 실패: {e}")
            return False

    def stop_server(self):
        if self.server_process and not self.server_was_running:
            print(f"\n🛑 서버 중지 중... (PID: {self.server_process.pid})")
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
                print("✅ 서버 중지 완료")
            except Exception:
                try:
                    self.server_process.kill()
                except Exception:
                    pass
            self.server_process = None

    # ─── Playwright 설정 ──────────────────────────────────────
    def setup(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless, slow_mo=self.slow_mo
        )
        self.context = self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="ko-KR",
            timezone_id="Asia/Seoul",
        )
        self.page = self.context.new_page()

    def teardown(self):
        if self.page:    self.page.close()
        if self.context: self.context.close()
        if self.browser: self.browser.close()
        if self.playwright: self.playwright.stop()

    # ─── 페이지 헬퍼 ─────────────────────────────────────────
    def navigate_to(self, path: str = ""):
        url = f"{self.base_url}{path}"
        self.page.goto(url, wait_until="networkidle")
        return self.page

    def take_screenshot(self, name: str) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fp = self.screenshot_dir / f"{name}_{ts}.png"
        self.page.screenshot(path=str(fp), full_page=True)
        return str(fp)

    def fill_input(self, selector: str, value: str):
        self.page.fill(selector, value)

    def click_button(self, selector: str):
        self.page.click(selector)

    def get_text(self, selector: str) -> str:
        text = self.page.text_content(selector) or ""
        return re.sub(r'\s+', ' ', text).strip()

    def is_visible(self, selector: str) -> bool:
        return self.page.is_visible(selector)

    def check_element_exists(self, selector: str, timeout: int = 2000) -> bool:
        try:
            self.page.wait_for_selector(selector, timeout=timeout)
            return True
        except Exception:
            return False

    # ─── 테스트 실행 ─────────────────────────────────────────
    def run_category(self, category_name: str, tests: List):
        print(f"\n{'=' * 70}")
        print(f"{category_name}")
        print(f"{'=' * 70}")

        for test_func in tests:
            result = UnitTestResult(test_func.__name__, category_name)
            self.results.append(result)
            try:
                result.start()
                print(f"\n{TestStatus.RUNNING.value} {test_func.__name__}...", end=" ", flush=True)
                test_func(result)
                if result.status == TestStatus.RUNNING:
                    result.pass_test()
                print(f"\r{result}")
                for d in result.details:
                    print(f"    ℹ️  {d}")
                for s in result.screenshots:
                    print(f"    📷 {s}")
            except Exception as e:
                result.fail_test(f"예외 발생: {str(e)}")
                print(f"\r{result}")
                try:
                    ss = self.take_screenshot(f"error_{test_func.__name__}")
                    result.add_screenshot(ss)
                    print(f"    📷 Error: {ss}")
                except Exception:
                    pass

    def print_final_report(self) -> int:
        """최종 결과 출력. 실패 0이면 0, 아니면 1 반환."""
        print("\n" + "=" * 70)
        print("infosd Unit 테스트 결과 요약")
        print("=" * 70)

        counts = {s: 0 for s in TestStatus}
        for r in self.results:
            counts[r.status] += 1

        total = len(self.results)
        if total == 0:
            print("실행된 테스트 없음")
            return 0

        passed  = counts[TestStatus.PASSED]
        failed  = counts[TestStatus.FAILED]
        warning = counts[TestStatus.WARNING]
        skipped = counts[TestStatus.SKIPPED]

        print(f"\n총 테스트: {total}개")
        print(f"✅ 통과:   {passed}개  ({passed/total*100:.1f}%)")
        print(f"❌ 실패:   {failed}개  ({failed/total*100:.1f}%)")
        print(f"⚠️  경고:   {warning}개  ({warning/total*100:.1f}%)")
        print(f"⊘  건너뜀: {skipped}개  ({skipped/total*100:.1f}%)")
        return 0 if failed == 0 else 1

    def save_markdown_report(self, filepath: str):
        """마크다운 리포트 저장"""
        counts = {s: 0 for s in TestStatus}
        for r in self.results:
            counts[r.status] += 1
        total = len(self.results)

        lines = [
            f"<!-- Test Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} -->",
            "# infosd Unit 테스트 결과\n",
            "## 테스트 결과 요약\n",
            "| 항목 | 개수 | 비율 |",
            "|------|------|------|",
            f"| ✅ 통과 | {counts[TestStatus.PASSED]} | {counts[TestStatus.PASSED]/total*100:.1f}% |" if total else "| ✅ 통과 | 0 | 0% |",
            f"| ❌ 실패 | {counts[TestStatus.FAILED]} | {counts[TestStatus.FAILED]/total*100:.1f}% |" if total else "| ❌ 실패 | 0 | 0% |",
            f"| ⚠️ 경고 | {counts[TestStatus.WARNING]} | {counts[TestStatus.WARNING]/total*100:.1f}% |" if total else "| ⚠️ 경고 | 0 | 0% |",
            f"| ⊘ 건너뜀 | {counts[TestStatus.SKIPPED]} | {counts[TestStatus.SKIPPED]/total*100:.1f}% |" if total else "| ⊘ 건너뜀 | 0 | 0% |",
            f"| **총계** | **{total}** | **100%** |\n",
            "## 테스트 상세\n",
            "| 카테고리 | 테스트명 | 결과 | 시간 | 메시지 |",
            "|----------|---------|------|------|--------|",
        ]
        for r in self.results:
            lines.append(
                f"| {r.category} | `{r.test_name}` | {r.status.value} | "
                f"{r.get_duration():.2f}s | {r.message} |"
            )

        Path(filepath).write_text('\n'.join(lines), encoding='utf-8')
        print(f"\n📄 리포트 저장: {filepath}")
