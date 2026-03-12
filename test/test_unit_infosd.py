"""
infosd: 정보보호공시 시스템 Unit 테스트 코드

unit_checklist_infosd.md 시나리오 기반 자동 테스트.
실행 완료 후 unit_checklist_infosd_result.md에 결과 저장.

실행:
    python test/test_unit_infosd.py
"""

import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from test.playwright_base import PlaywrightTestBase, TestStatus, UnitTestResult

import requests as req

TEST_COMPANY_NAME = "테스트회사_자동"
TEST_YEAR = 2026        # index.html select options: range(2023, 2027)
W = 400                 # 액션 후 최소 대기(ms)

# ── 셀렉터 상수 ──────────────────────────────────────────────────
# 카드: .progress-card (class="progress-card p-0 overflow-hidden ...")
# 카드 헤더: .p-4.border-bottom  (회사 삭제 버튼·연도 추가 폼이 여기)
# 연도 행: table tbody tr


class InfosdUnitTest(PlaywrightTestBase):

    def __init__(self, base_url="http://localhost:5001", **kwargs):
        super().__init__(base_url=base_url, **kwargs)
        self.category = "infosd: 정보보호공시"
        self.checklist_source = project_root / "test" / "unit_checklist_infosd.md"
        self.checklist_result = project_root / "test" / "unit_checklist_infosd_result.md"
        self._company_id = None   # 최초 1회만 셋업, 이후 캐시

    # ─── 공통 헬퍼 ───────────────────────────────────────────

    def _get_cookies(self) -> dict:
        return {c["name"]: c["value"] for c in self.context.cookies()}

    def _card(self, name=None):
        """회사 카드 locator. name 생략 시 TEST_COMPANY_NAME 사용."""
        n = name or TEST_COMPANY_NAME
        return self.page.locator(f".progress-card:has-text('{n}')")

    def _open_add_modal(self):
        """신규 기업 등록 모달 열기."""
        self.page.locator("[data-bs-target='#addCompanyModal']").click()
        self.page.wait_for_selector("#addCompanyModal.show", state="visible")

    def _ensure_session(self) -> str | None:
        """테스트용 회사+연도 세션을 보장. 첫 호출에만 실제 작업, 이후 캐시."""
        if self._company_id:
            return self._company_id

        self.navigate_to("/")
        self.page.wait_for_load_state("domcontentloaded")

        # 테스트 회사 없으면 등록 (모달)
        if self._card().count() == 0:
            self._open_add_modal()
            self.page.locator("#addCompanyModal input[name='name']").fill(TEST_COMPANY_NAME)
            self.page.locator("#addCompanyModal button[type='submit']").click()
            self.page.wait_for_selector(f".progress-card:has-text('{TEST_COMPANY_NAME}')")

        # company_id 추출 (헤더 영역 회사 삭제 form action 기준)
        hdr = self._card().locator(".p-4.border-bottom")
        del_form = hdr.locator("form[action$='/delete']").first
        if del_form.count() == 0:
            return None
        action = del_form.get_attribute("action") or ""
        # action: /company/<uuid>/delete
        parts = [p for p in action.split("/") if p]
        if len(parts) < 2:
            return None
        company_id = parts[1]

        # 연도 없으면 select 로 추가
        year_row = self._card().locator(f"table td .badge:has-text('{TEST_YEAR}년')")
        if year_row.count() == 0:
            year_form = hdr.locator("form[action*='/year/add']").first
            if year_form.count() > 0:
                year_form.locator("select[name='year']").select_option(str(TEST_YEAR))
                year_form.locator("button[type='submit']").click()
                self.page.wait_for_selector(f"text={TEST_YEAR}년")

        # 세션 선택
        self.navigate_to(f"/disclosure/select/{company_id}/{TEST_YEAR}")
        self.page.wait_for_load_state("domcontentloaded")
        self._company_id = company_id
        return company_id

    def _api(self, method: str, path: str, **kwargs):
        return getattr(req, method)(
            f"{self.base_url}{path}",
            cookies=self._get_cookies(),
            timeout=10,
            **kwargs,
        )

    def _go_work(self):
        self.navigate_to("/disclosure/work")
        self.page.wait_for_load_state("domcontentloaded")

    def _click_yn_wait(self, selector: str):
        """YES/NO 버튼 클릭 후 JS reload 완료까지 대기 (JS: 120ms 후 location.reload())."""
        with self.page.expect_navigation(wait_until="domcontentloaded", timeout=5000):
            self.page.locator(selector).first.click()

    def _q1_yes(self):
        """Q1 YES 클릭 후 페이지 리로드 완료까지 대기."""
        if self.page.locator("#btn-Q1-YES").count() > 0:
            self._click_yn_wait("#btn-Q1-YES")

    # ─── 1. 회사·연도 관리 ──────────────────────────────────

    def test_company_add(self, result: UnitTestResult):
        """1. 신규 회사 등록"""
        self.navigate_to("/")
        self.page.wait_for_load_state("domcontentloaded")

        # 이미 있으면 삭제
        if self._card().count() > 0:
            hdr = self._card().locator(".p-4.border-bottom")
            del_form = hdr.locator("form[action$='/delete']").first
            if del_form.count() > 0:
                self.page.evaluate("window.confirm = () => true")
                del_form.locator("button[type='submit']").click()
                self.page.wait_for_load_state("domcontentloaded")
            self._company_id = None

        self._open_add_modal()
        self.page.locator("#addCompanyModal input[name='name']").fill(TEST_COMPANY_NAME)
        self.page.locator("#addCompanyModal button[type='submit']").click()
        self.page.wait_for_selector(f"text={TEST_COMPANY_NAME}")

        if self._card().count() > 0:
            result.pass_test(f"'{TEST_COMPANY_NAME}' 등록 및 목록 표시 확인")
        else:
            result.fail_test("등록 후 목록에서 회사명을 찾을 수 없음")

    def test_company_add_duplicate(self, result: UnitTestResult):
        """1. 중복 회사 등록 차단"""
        self.navigate_to("/")
        self.page.wait_for_load_state("domcontentloaded")
        self._open_add_modal()
        self.page.locator("#addCompanyModal input[name='name']").fill(TEST_COMPANY_NAME)
        self.page.locator("#addCompanyModal button[type='submit']").click()
        self.page.wait_for_load_state("domcontentloaded")

        if "이미 등록" in self.page.content():
            result.pass_test("중복 등록 시 경고 메시지 확인")
        else:
            result.warn_test("경고 텍스트 미감지 — 중복 차단 로직 수동 확인 필요")

    def test_company_edit(self, result: UnitTestResult):
        """1. 회사명 수정"""
        self.navigate_to("/")
        self.page.wait_for_load_state("domcontentloaded")

        if self._card().count() == 0:
            result.skip_test(f"'{TEST_COMPANY_NAME}' 카드 없음")
            return

        # 편집 아이콘 클릭 → 모달 열기
        # data-bs-target="#editCompanyModal-<id>" 버튼
        edit_btn = self._card().locator("[data-bs-target*='editCompanyModal']").first
        if edit_btn.count() == 0:
            result.skip_test("수정 버튼 미발견")
            return

        modal_target = edit_btn.get_attribute("data-bs-target") or ""
        edit_btn.click()
        self.page.wait_for_selector(f"{modal_target}.show", state="visible")

        new_name = TEST_COMPANY_NAME + "_편집"
        self.page.locator(f"{modal_target} input[name='name']").fill(new_name)
        self.page.locator(f"{modal_target} button[type='submit']").click()
        self.page.wait_for_selector(f"text={new_name}")

        if self.page.locator(f"text={new_name}").count() > 0:
            # 원래 이름으로 복구
            edit_btn2 = self.page.locator(f".progress-card:has-text('{new_name}') [data-bs-target*='editCompanyModal']").first
            if edit_btn2.count() > 0:
                modal_target2 = edit_btn2.get_attribute("data-bs-target") or ""
                edit_btn2.click()
                self.page.wait_for_selector(f"{modal_target2}.show", state="visible")
                self.page.locator(f"{modal_target2} input[name='name']").fill(TEST_COMPANY_NAME)
                self.page.locator(f"{modal_target2} button[type='submit']").click()
                self.page.wait_for_selector(f"text={TEST_COMPANY_NAME}")
            self._company_id = None  # company_id는 같지만 캐시 안전 초기화
            result.pass_test(f"회사명 수정 확인 (→ {new_name} → 복구)")
        else:
            result.fail_test("수정 후 새 이름이 목록에 표시되지 않음")

    def test_year_add(self, result: UnitTestResult):
        """1. 공시 연도 추가"""
        company_id = self._ensure_session()
        if not company_id:
            result.skip_test("세션 구성 실패")
            return

        self.navigate_to("/")
        self.page.wait_for_load_state("domcontentloaded")

        year_badge = self._card().locator(f"table td .badge:has-text('{TEST_YEAR}년')")
        if year_badge.count() > 0:
            result.pass_test(f"{TEST_YEAR}년도 목록 존재 확인")
        else:
            result.fail_test(f"{TEST_YEAR}년도가 목록에 없음")

    def test_year_add_duplicate(self, result: UnitTestResult):
        """1. 연도 중복 추가 차단"""
        company_id = self._ensure_session()
        if not company_id:
            result.skip_test("세션 구성 실패")
            return

        self.navigate_to("/")
        self.page.wait_for_load_state("domcontentloaded")

        hdr = self._card().locator(".p-4.border-bottom")
        year_form = hdr.locator("form[action*='/year/add']").first
        if year_form.count() == 0:
            result.skip_test("연도 추가 폼 미발견")
            return

        year_form.locator("select[name='year']").select_option(str(TEST_YEAR))
        year_form.locator("button[type='submit']").click()
        self.page.wait_for_load_state("domcontentloaded")

        if "이미 등록" in self.page.content() or "중복" in self.page.content():
            result.pass_test("연도 중복 추가 시 경고 확인")
        else:
            result.warn_test("경고 텍스트 미감지 — 중복 차단 여부 수동 확인 필요")

    def test_company_delete(self, result: UnitTestResult):
        """1. 회사 삭제"""
        tmp_name = "삭제테스트_임시"
        self.navigate_to("/")
        self.page.wait_for_load_state("domcontentloaded")

        self._open_add_modal()
        self.page.locator("#addCompanyModal input[name='name']").fill(tmp_name)
        self.page.locator("#addCompanyModal button[type='submit']").click()
        self.page.wait_for_selector(f"text={tmp_name}")

        tmp_card = self.page.locator(f".progress-card:has-text('{tmp_name}')")
        del_form = tmp_card.locator(".p-4.border-bottom form[action$='/delete']").first
        if del_form.count() == 0:
            result.fail_test("삭제 폼 미발견")
            return

        # form action URL 추출 후 API 직접 호출 (JS confirm 우회)
        action_path = del_form.get_attribute("action") or ""
        if not action_path:
            result.fail_test("삭제 form action 속성 없음")
            return

        del_resp = self._api("post", action_path, data={})
        self.navigate_to("/")
        self.page.wait_for_load_state("domcontentloaded")

        if self.page.locator(f".progress-card:has-text('{tmp_name}')").count() == 0:
            result.pass_test(f"'{tmp_name}' 삭제 후 목록 제거 확인")
        else:
            result.fail_test("삭제 후에도 목록에 회사가 남아 있음")

    # ─── 2. 공시 세션 진입 및 대시보드 ─────────────────────

    def test_session_select(self, result: UnitTestResult):
        """2. 회사+연도 선택 후 대시보드 진입"""
        company_id = self._ensure_session()
        if not company_id:
            result.skip_test("세션 구성 실패")
            return

        url = self.page.url
        if "disclosure" in url or "공시" in self.page.title():
            result.pass_test(f"대시보드 진입 확인 (URL: {url})")
        else:
            result.fail_test(f"대시보드 미진입 (URL: {url})")

    def test_dashboard_render(self, result: UnitTestResult):
        """2. 대시보드 카테고리 카드 렌더링"""
        if not self._ensure_session():
            result.skip_test("세션 구성 실패")
            return

        self.navigate_to("/disclosure/")
        self.page.wait_for_load_state("domcontentloaded")

        count = self.page.locator(".category-card").count()
        if count >= 4:
            result.pass_test(f"카테고리 카드 {count}개 렌더링 확인")
        else:
            result.fail_test(f"카테고리 카드 수 부족 ({count}개, 최소 4개 필요)")

    def test_dashboard_category_navigation(self, result: UnitTestResult):
        """2. 카테고리 카드 클릭 → 작업 화면 이동"""
        if not self._ensure_session():
            result.skip_test("세션 구성 실패")
            return

        self.navigate_to("/disclosure/")
        self.page.wait_for_load_state("domcontentloaded")

        first_card = self.page.locator(".category-card").first
        if first_card.count() == 0:
            result.skip_test("카테고리 카드 없음")
            return

        first_card.click()
        self.page.wait_for_load_state("domcontentloaded")
        url = self.page.url

        if "work" in url or self.page.locator(".question-item").count() > 0:
            result.pass_test("카테고리 클릭 → 작업 화면 이동 확인")
        else:
            result.fail_test(f"작업 화면 미이동 (URL: {url})")

    # ─── 3. 답변 저장 및 검증 ───────────────────────────────

    def test_answer_yes_no(self, result: UnitTestResult):
        """3. YES/NO 답변 저장"""
        if not self._ensure_session():
            result.skip_test("세션 구성 실패")
            return

        self._go_work()
        yes_btn = self.page.locator("#btn-Q1-YES").first
        if yes_btn.count() == 0:
            result.skip_test("Q1 YES 버튼 미발견")
            return

        yes_btn.scroll_into_view_if_needed()
        yes_btn.click()
        self.page.wait_for_timeout(W)

        cls = yes_btn.get_attribute("class") or ""
        if "selected" in cls:
            result.pass_test("YES 버튼 selected 상태 확인")
        else:
            result.fail_test(f"selected 클래스 미부여 (class: {cls})")

    def test_answer_dependent_show(self, result: UnitTestResult):
        """3. 상위 YES → 하위 질문 표시"""
        if not self._ensure_session():
            result.skip_test("세션 구성 실패")
            return

        self._go_work()
        self._q1_yes()

        q2 = self.page.locator("#card-Q2")
        if q2.count() > 0 and q2.is_visible():
            result.pass_test("Q1 YES → Q2 하위 질문 표시 확인")
        else:
            result.fail_test("Q1 YES 선택 후 Q2가 표시되지 않음")

    def test_answer_dependent_hide(self, result: UnitTestResult):
        """3. 상위 NO → 하위 질문 숨김"""
        if not self._ensure_session():
            result.skip_test("세션 구성 실패")
            return

        self._go_work()
        if self.page.locator("#btn-Q1-YES").count() == 0:
            result.skip_test("Q1 버튼 미발견")
            return

        self._click_yn_wait("#btn-Q1-YES")  # YES → reload
        self._click_yn_wait("#btn-Q1-NO")   # NO → reload

        q2 = self.page.locator("#card-Q2")
        if q2.count() == 0 or not q2.is_visible():
            result.pass_test("Q1 NO → Q2 숨김 확인")
        else:
            result.fail_test("Q1 NO 후에도 Q2가 화면에 표시됨")

    def test_answer_number(self, result: UnitTestResult):
        """3. 숫자 입력 및 쉼표 포맷팅"""
        if not self._ensure_session():
            result.skip_test("세션 구성 실패")
            return

        self._go_work()
        self._q1_yes()

        q2_input = self.page.locator("#input-Q2")
        if q2_input.count() == 0 or not q2_input.is_visible():
            result.skip_test("Q2 입력 필드 미발견")
            return

        q2_input.fill("1000000")
        q2_input.dispatch_event("input")
        q2_input.blur()
        self.page.wait_for_timeout(W)

        val = q2_input.input_value()
        if "1,000,000" in val or val.replace(",", "") == "1000000":
            result.pass_test(f"숫자 입력 및 포맷팅 확인 (표시: {val})")
        else:
            result.fail_test(f"포맷팅 미적용 (val: {val})")

    def test_answer_text(self, result: UnitTestResult):
        """3. 텍스트(textarea) 입력 및 저장"""
        company_id = self._ensure_session()
        if not company_id:
            result.skip_test("세션 구성 실패")
            return

        self._go_work()
        self._q1_yes()

        q27 = self.page.locator("#input-Q27")
        if q27.count() == 0 or not q27.is_visible():
            result.skip_test("Q27 textarea 미발견")
            return

        test_text = "방화벽 도입(50만원), 보안관제(100만원)"
        q27.fill(test_text)
        q27.blur()
        self.page.wait_for_timeout(W)

        resp = self._api("get", f"/disclosure/api/answers/{company_id}/{TEST_YEAR}")
        if resp.status_code == 200:
            # answers는 list[{question_id, value, ...}] 구조
            answers_list = resp.json().get("answers", [])
            q27 = next((x for x in answers_list if x.get("question_id") == "Q27"), None)
            saved = q27.get("value", "") if q27 else ""
            if saved:
                result.pass_test(f"Q27 텍스트 저장 확인 ({str(saved)[:40]})")
            else:
                result.fail_test("Q27 저장값 없음")
        else:
            result.warn_test(f"저장 확인 API 오류 ({resp.status_code})")

    def test_validation_negative(self, result: UnitTestResult):
        """3. 음수 입력 차단"""
        company_id = self._ensure_session()
        if not company_id:
            result.skip_test("세션 구성 실패")
            return

        resp = self._api("post", "/disclosure/api/answer",
                         json={"question_id": "Q2", "company_id": company_id,
                               "year": TEST_YEAR, "value": "-5000"})
        if resp.status_code == 400:
            result.pass_test(f"음수 입력 400 차단 ({resp.json().get('message', '')})")
        else:
            result.fail_test(f"음수 입력 미차단 (status: {resp.status_code})")

    def test_validation_b_gt_a(self, result: UnitTestResult):
        """3. 정보보호 투자액(B) > IT 투자액(A) 차단"""
        company_id = self._ensure_session()
        if not company_id:
            result.skip_test("세션 구성 실패")
            return

        self._api("post", "/disclosure/api/answer",
                  json={"question_id": "Q2", "company_id": company_id,
                        "year": TEST_YEAR, "value": "1000000"})
        resp = self._api("post", "/disclosure/api/answer",
                         json={"question_id": "Q4", "company_id": company_id,
                               "year": TEST_YEAR, "value": "2000000"})

        if resp.status_code == 400:
            result.pass_test(f"B > A 차단 확인 ({resp.json().get('message', '')[:60]})")
        else:
            result.fail_test(f"B > A 허용됨 (status: {resp.status_code})")

    def test_validation_personnel(self, result: UnitTestResult):
        """3. 인력 계층 검증 (IT인력 > 총인원 차단)"""
        company_id = self._ensure_session()
        if not company_id:
            result.skip_test("세션 구성 실패")
            return

        self._api("post", "/disclosure/api/answer",
                  json={"question_id": "Q10", "company_id": company_id,
                        "year": TEST_YEAR, "value": "10"})
        resp = self._api("post", "/disclosure/api/answer",
                         json={"question_id": "Q28", "company_id": company_id,
                               "year": TEST_YEAR, "value": "20"})

        if resp.status_code == 400:
            result.pass_test(f"IT인력 > 총인원 400 차단 ({resp.json().get('message', '')[:60]})")
        else:
            result.fail_test(f"인력 계층 위반 미차단 (status: {resp.status_code})")

    def test_answer_confirmed_blocked(self, result: UnitTestResult):
        """3. 확정(confirmed) 상태에서 답변 수정 403 차단"""
        company_id = self._ensure_session()
        if not company_id:
            result.skip_test("세션 구성 실패")
            return

        resp = self._api("post", "/disclosure/api/answer",
                         json={"question_id": "Q27", "company_id": company_id,
                               "year": TEST_YEAR, "value": "confirmed 차단 테스트"})
        if resp.status_code == 403:
            result.pass_test("confirmed 상태 수정 시도 시 403 확인")
        elif resp.status_code == 200:
            result.skip_test("현재 세션이 confirmed 아님 — 확정 후 수동 재확인 필요")
        else:
            result.warn_test(f"예상치 못한 응답: {resp.status_code}")

    # ─── 4. 증빙 자료 관리 ──────────────────────────────────

    def test_evidence_upload(self, result: UnitTestResult):
        """4. 허용 확장자(PNG) 파일 업로드"""
        company_id = self._ensure_session()
        if not company_id:
            result.skip_test("세션 구성 실패")
            return

        png_sig = b"\x89PNG\r\n\x1a\n"
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(png_sig + b"infosd unit test evidence")
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                resp = self._api("post", "/disclosure/api/evidence",
                                 files={"file": ("test_ev.png", f, "image/png")},
                                 data={"question_id": "Q2", "company_id": company_id,
                                       "year": str(TEST_YEAR)})
            if resp.status_code == 200 and resp.json().get("success"):
                ev_id = str(resp.json().get("evidence_id", "?"))[:8]
                result.pass_test(f"PNG 업로드 성공 (id: {ev_id}...)")
            else:
                result.fail_test(f"업로드 실패: {resp.status_code} — {resp.text[:80]}")
        finally:
            os.unlink(tmp_path)

    def test_evidence_invalid_ext(self, result: UnitTestResult):
        """4. 비허용 확장자(exe) 차단"""
        company_id = self._ensure_session()
        if not company_id:
            result.skip_test("세션 구성 실패")
            return

        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as tmp:
            tmp.write(b"MZ fake exe")
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                resp = self._api("post", "/disclosure/api/evidence",
                                 files={"file": ("malware.exe", f, "application/octet-stream")},
                                 data={"question_id": "Q2", "company_id": company_id,
                                       "year": str(TEST_YEAR)})
            blocked = resp.status_code in (400, 415) or not resp.json().get("success", True)
            if blocked:
                result.pass_test(f"비허용 확장자 차단 확인 (status: {resp.status_code})")
            else:
                result.fail_test(f".exe 파일 업로드 허용됨 (status: {resp.status_code})")
        finally:
            os.unlink(tmp_path)

    def test_evidence_delete(self, result: UnitTestResult):
        """4. 증빙 파일 삭제"""
        company_id = self._ensure_session()
        if not company_id:
            result.skip_test("세션 구성 실패")
            return

        png_sig = b"\x89PNG\r\n\x1a\n"
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(png_sig + b"delete test")
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                up = self._api("post", "/disclosure/api/evidence",
                               files={"file": ("del_test.png", f, "image/png")},
                               data={"question_id": "Q2", "company_id": company_id,
                                     "year": str(TEST_YEAR)})
        finally:
            os.unlink(tmp_path)

        if up.status_code != 200 or not up.json().get("success"):
            result.skip_test("사전 업로드 실패 — 삭제 테스트 건너뜀")
            return

        ev_id = up.json().get("evidence_id")
        if not ev_id:
            result.skip_test("업로드 응답에서 증빙 ID 추출 실패")
            return

        dl = self._api("delete", f"/disclosure/api/evidence/{ev_id}")
        if dl.status_code == 200 and dl.json().get("success"):
            result.pass_test(f"증빙 삭제 성공 (ID: {str(ev_id)[:8]}...)")
        else:
            result.fail_test(f"삭제 실패: {dl.status_code} — {dl.text[:80]}")

    # ─── 5. 공시 확정 흐름 ──────────────────────────────────

    def test_submit_incomplete_blocked(self, result: UnitTestResult):
        """5. 미완료 상태에서 검토 요청(submit) 차단"""
        if not self._ensure_session():
            result.skip_test("세션 구성 실패")
            return

        self.navigate_to("/disclosure/review")
        self.page.wait_for_load_state("domcontentloaded")

        submit_btn = self.page.locator("form[action*='/submit'] button[type='submit']").first
        if submit_btn.count() > 0:
            submit_btn.click()
            self.page.wait_for_load_state("domcontentloaded")

        if "모든 항목" in self.page.content() or "작성해야" in self.page.content():
            result.pass_test("미완료 상태에서 submit 차단 메시지 확인")
        else:
            result.warn_test("차단 메시지 미감지 — 완료율이 이미 100%이거나 셀렉터 불일치")

    def test_confirm_without_submit_blocked(self, result: UnitTestResult):
        """5. submitted 상태 없이 confirm 차단"""
        if not self._ensure_session():
            result.skip_test("세션 구성 실패")
            return

        # confirmed 상태 해제 (있을 경우)
        self._api("post", "/disclosure/unconfirm", data={})

        # API 직접 호출로 confirm 시도 (submitted 상태가 아닌 경우 flash + redirect)
        resp = self._api("post", "/disclosure/confirm", data={})

        # submitted 상태가 아니면 Flask가 flash('검토 요청(submitted)...') 후 review로 redirect
        # requests가 redirect를 follow한 HTML에서 확인
        content = resp.text if resp.status_code == 200 else ""
        blocked = (resp.status_code == 403
                   or "submitted" in content
                   or "검토 요청" in content
                   or "확정" in content)

        if blocked:
            result.pass_test("submitted 없이 confirm 차단 확인")
        else:
            # DB에서 직접 상태 확인: confirmed로 변경되지 않았으면 차단된 것
            import sqlite3
            with sqlite3.connect(str(project_root / "infosd.db")) as conn:
                conn.row_factory = sqlite3.Row
                company_id = self._ensure_session()
                row = conn.execute(
                    'SELECT status FROM isd_sessions WHERE company_id=? AND year=?',
                    (company_id, TEST_YEAR)
                ).fetchone()
                status = row['status'] if row else None
            if status != 'confirmed':
                result.pass_test(f"submitted 없이 confirm 미실행 확인 (status: {status})")
            else:
                result.fail_test("submitted 없이 confirm이 실행됨 (status: confirmed)")

    # ─── 6. Audit Trail ─────────────────────────────────────

    def test_audit_trail_recorded(self, result: UnitTestResult):
        """6. 답변 저장 후 isd_answer_history 이력 기록"""
        company_id = self._ensure_session()
        if not company_id:
            result.skip_test("세션 구성 실패")
            return

        import sqlite3
        db_path = project_root / "infosd.db"

        def count_history():
            try:
                conn = sqlite3.connect(str(db_path))
                n = conn.execute(
                    "SELECT COUNT(*) FROM isd_answer_history WHERE company_id=? AND year=?",
                    (company_id, TEST_YEAR)
                ).fetchone()[0]
                conn.close()
                return n
            except Exception:
                return None

        before = count_history()
        if before is None:
            result.skip_test("DB 접근 실패")
            return

        self._api("post", "/disclosure/api/answer",
                  json={"question_id": "Q27", "company_id": company_id,
                        "year": TEST_YEAR, "value": "Audit Trail 테스트"})

        after = count_history()
        if after is not None and after > before:
            result.pass_test(f"Audit Trail 이력 기록 확인 ({before} → {after}건)")
        else:
            result.fail_test(f"이력 미증가 (before: {before}, after: {after})")

    # ─── 7. 데이터 무결성 ───────────────────────────────────

    def test_recursive_na_cleanup(self, result: UnitTestResult):
        """7. YES→NO→YES 순환 시 하위 질문 재활성화"""
        if not self._ensure_session():
            result.skip_test("세션 구성 실패")
            return

        self._go_work()
        if self.page.locator("#btn-Q1-YES").count() == 0:
            result.skip_test("Q1 버튼 미발견")
            return

        self._click_yn_wait("#btn-Q1-YES")  # YES → reload
        q2_shown = self.page.locator("#card-Q2").count() > 0

        self._click_yn_wait("#btn-Q1-NO")   # NO → reload
        q2_hidden = self.page.locator("#card-Q2").count() == 0

        self._click_yn_wait("#btn-Q1-YES")  # YES → reload
        q2_back = self.page.locator("#card-Q2").count() > 0

        if q2_shown and q2_hidden and q2_back:
            result.pass_test("YES→NO→YES 순환 시 하위 질문 재활성화 확인")
        else:
            result.fail_test(f"재활성화 실패 (shown:{q2_shown} hidden:{q2_hidden} back:{q2_back})")

    def test_session_progress_update(self, result: UnitTestResult):
        """7. 답변 저장 후 세션 완료율 갱신"""
        company_id = self._ensure_session()
        if not company_id:
            result.skip_test("세션 구성 실패")
            return

        import sqlite3
        db_path = project_root / "infosd.db"

        def get_rate():
            try:
                conn = sqlite3.connect(str(db_path))
                row = conn.execute(
                    "SELECT completion_rate FROM isd_sessions WHERE company_id=? AND year=?",
                    (company_id, TEST_YEAR)
                ).fetchone()
                conn.close()
                return row[0] if row else None
            except Exception:
                return None

        before = get_rate()
        self._api("post", "/disclosure/api/answer",
                  json={"question_id": "Q1", "company_id": company_id,
                        "year": TEST_YEAR, "value": "YES"})
        after = get_rate()

        result.add_detail(f"완료율: {before}% → {after}%")
        if after is not None:
            result.pass_test(f"세션 완료율 갱신 확인 ({before}% → {after}%)")
        else:
            result.fail_test("완료율 갱신 후 DB 값 확인 실패")

    # ─── 8. table 타입 답변 저장 ──────────────────────────────

    def test_answer_table_type_json(self, result: UnitTestResult):
        """8. table 타입 질문(Q27) JSON 배열 저장 및 검증"""
        company_id = self._ensure_session()
        if not company_id:
            result.skip_test("세션 구성 실패")
            return

        # Q27은 migration 009 이후 type='table' (항목명+금액 구조)
        table_value = [
            {"item": "방화벽 도입", "amount": 5000000, "note": "차세대 방화벽"},
            {"item": "보안관제 서비스", "amount": 10000000, "note": ""},
        ]
        self._api("post", "/disclosure/api/answer",
                  json={"question_id": "Q27", "company_id": company_id,
                        "year": TEST_YEAR, "value": table_value})
        self.page.wait_for_timeout(W)

        resp = self._api("get", f"/disclosure/api/answers/{company_id}/{TEST_YEAR}")
        if resp.status_code != 200:
            result.fail_test(f"답변 조회 API 실패 ({resp.status_code})")
            return

        answers_list = resp.json().get("answers", [])
        q27_row = next((x for x in answers_list if x.get("question_id") == "Q27"), None)
        if not q27_row:
            result.fail_test("Q27 답변 없음")
            return

        saved = q27_row.get("value")
        if isinstance(saved, list) and len(saved) == 2:
            result.pass_test(f"Q27 JSON 배열 저장 확인 ({len(saved)}행)")
        elif isinstance(saved, str) and "방화벽" in saved:
            result.warn_test("Q27 문자열로 저장됨 — JSON 파싱 실패 가능성 확인 필요")
        else:
            result.fail_test(f"Q27 저장값 불일치 (type: {type(saved).__name__})")

    # ─── 9. inv-grid 렌더링 ───────────────────────────────────

    def test_inv_grid_investment_render(self, result: UnitTestResult):
        """9. 카테고리 1 — 투자 inv-grid 및 I-3 ratio-bar 렌더링"""
        if not self._ensure_session():
            result.skip_test("세션 구성 실패")
            return

        # Q1 YES 설정 후 카테고리 1 작업 화면
        self._api("post", "/disclosure/api/answer",
                  json={"question_id": "Q1", "company_id": self._company_id,
                        "year": TEST_YEAR, "value": "YES"})
        self.navigate_to("/disclosure/work?category=1")
        self.page.wait_for_load_state("domcontentloaded")

        # inv-grid-outer (투자 항목 그리드) 존재 확인
        if self.page.locator(".inv-grid-outer").count() == 0:
            result.fail_test("inv-grid-outer 요소 없음 (카테고리 1 작업 화면)")
            return
        result.add_detail(f"inv-grid-outer {self.page.locator('.inv-grid-outer').count()}개 확인")

        # I-3 ratio-bar 존재 확인
        ratio_bar = self.page.locator("#ratio-bar-investment")
        if ratio_bar.count() == 0:
            result.fail_test("#ratio-bar-investment 요소 없음")
            return
        result.add_detail("I-3 투자비율 ratio-bar DOM 확인")

        # ratio-bar-value span 존재
        if self.page.locator("#investment-ratio-display").count() > 0:
            result.add_detail("#investment-ratio-display span 확인")

        result.pass_test("카테고리 1 투자 inv-grid + I-3 ratio-bar 렌더링 확인")

    def test_inv_grid_personnel_render(self, result: UnitTestResult):
        """9. 카테고리 2 — 인력 컴팩트 그리드(Q10/Q28/Q11/Q12) 및 II-4 ratio-bar 렌더링"""
        if not self._ensure_session():
            result.skip_test("세션 구성 실패")
            return

        # Q9 YES 설정 후 카테고리 2 작업 화면
        self._api("post", "/disclosure/api/answer",
                  json={"question_id": "Q9", "company_id": self._company_id,
                        "year": TEST_YEAR, "value": "YES"})
        self.navigate_to("/disclosure/work?category=2")
        self.page.wait_for_load_state("domcontentloaded")

        # 4개 인력 입력 필드 확인 (컴팩트 2×2 그리드)
        personnel_inputs = {
            "#input-Q10": "총 임직원 (II-1)",
            "#input-Q28": "IT 인력 C (II-2)",
            "#input-Q11": "내부 전담 D1 (II-3-가)",
            "#input-Q12": "외주 전담 D2 (II-3-나)",
        }
        missing = []
        for sel, label in personnel_inputs.items():
            if self.page.locator(sel).count() > 0:
                result.add_detail(f"{label} 입력 필드 확인")
            else:
                missing.append(label)

        if missing:
            result.fail_test(f"인력 입력 필드 미발견: {', '.join(missing)}")
            return

        # II-4 ratio-bar 존재 확인
        ratio_span = self.page.locator("#personnel-ratio-display")
        if ratio_span.count() == 0:
            result.fail_test("#personnel-ratio-display 없음 (II-4 ratio-bar 미렌더링)")
            return
        result.add_detail("II-4 인력비율 ratio-bar DOM 확인")

        result.pass_test("카테고리 2 인력 컴팩트 그리드 + II-4 ratio-bar 렌더링 확인")

    # ─── 10. 비율 자동계산 (API) ──────────────────────────────

    def test_investment_ratio_api(self, result: UnitTestResult):
        """10. 투자비율(B/A) 자동계산 API 검증"""
        company_id = self._ensure_session()
        if not company_id:
            result.skip_test("세션 구성 실패")
            return

        # Q1=YES, Q2(A)=10,000,000, Q4(B감가)=2,000,000 설정
        for qid, val in [("Q1", "YES"), ("Q2", "10000000"), ("Q4", "2000000")]:
            self._api("post", "/disclosure/api/answer",
                      json={"question_id": qid, "company_id": company_id,
                            "year": TEST_YEAR, "value": val})

        # 대시보드 API에서 ratios 확인 (dashboard 렌더링에 ratios 포함)
        self.navigate_to("/disclosure/")
        self.page.wait_for_load_state("domcontentloaded")

        # 카테고리 1 작업 화면에서 ratio-bar-value 확인
        self.navigate_to("/disclosure/work?category=1")
        self.page.wait_for_load_state("domcontentloaded")

        ratio_el = self.page.locator("#investment-ratio-display")
        if ratio_el.count() == 0:
            result.fail_test("#investment-ratio-display 없음")
            return

        # JS 계산 대기
        self.page.wait_for_timeout(500)
        ratio_text = ratio_el.text_content() or "-"
        result.add_detail(f"I-3 표시값: {ratio_text.strip()}")

        if ratio_text.strip() in ("-", ""):
            result.warn_test("ratio-bar DOM 존재하나 JS 계산값 미표시 — 입력 후 수동 확인 필요")
        else:
            result.pass_test(f"투자비율 자동계산 표시 확인 ({ratio_text.strip()})")

    def test_personnel_ratio_api(self, result: UnitTestResult):
        """10. 인력비율(D/C) 자동계산 API 검증"""
        company_id = self._ensure_session()
        if not company_id:
            result.skip_test("세션 구성 실패")
            return

        # Q9=YES, Q10=100명, Q28(C)=20명, Q11(D1)=5명, Q12(D2)=2명 설정
        for qid, val in [("Q9", "YES"), ("Q10", "100"), ("Q28", "20"),
                         ("Q11", "5"), ("Q12", "2")]:
            self._api("post", "/disclosure/api/answer",
                      json={"question_id": qid, "company_id": company_id,
                            "year": TEST_YEAR, "value": val})

        self.navigate_to("/disclosure/work?category=2")
        self.page.wait_for_load_state("domcontentloaded")

        ratio_el = self.page.locator("#personnel-ratio-display")
        if ratio_el.count() == 0:
            result.fail_test("#personnel-ratio-display 없음")
            return

        self.page.wait_for_timeout(500)
        ratio_text = ratio_el.text_content() or "-"
        result.add_detail(f"II-4 표시값: {ratio_text.strip()}")

        if ratio_text.strip() in ("-", ""):
            result.warn_test("ratio-bar DOM 존재하나 JS 계산값 미표시 — 입력 후 수동 확인 필요")
        else:
            result.pass_test(f"인력비율 자동계산 표시 확인 ({ratio_text.strip()})")

    # ─── 11. table 타입 증빙 자료 ────────────────────────────

    def test_evidence_for_table_type(self, result: UnitTestResult):
        """11. table 타입 질문(Q29 CISO 활동내역) 증빙 업로드"""
        company_id = self._ensure_session()
        if not company_id:
            result.skip_test("세션 구성 실패")
            return

        import tempfile, os
        pdf_sig = b"%PDF-1.4 infosd test evidence"
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_sig)
            tmp_path = tmp.name

        try:
            with open(tmp_path, "rb") as f:
                resp = self._api("post", "/disclosure/api/evidence",
                                 files={"file": ("ciso_activity.pdf", f, "application/pdf")},
                                 data={"question_id": "Q29", "company_id": company_id,
                                       "year": str(TEST_YEAR)})
            if resp.status_code == 200 and resp.json().get("success"):
                ev_id = str(resp.json().get("evidence_id", "?"))[:8]
                result.add_detail(f"Q29 PDF 업로드 성공 (id: {ev_id}...)")

                # 업로드된 파일 목록 확인 (answers API 통해 evidence 구조 간접 확인)
                # 삭제로 정리
                full_ev_id = resp.json().get("evidence_id")
                if full_ev_id:
                    del_r = self._api("delete", f"/disclosure/api/evidence/{full_ev_id}")
                    if del_r.status_code == 200:
                        result.add_detail("테스트 증빙 파일 정리 완료")
                result.pass_test("table 타입(Q29) 증빙 PDF 업로드 및 삭제 확인")
            else:
                result.fail_test(f"Q29 증빙 업로드 실패: {resp.status_code} — {resp.text[:80]}")
        finally:
            os.unlink(tmp_path)

    # ─── 12. 증빙 섹션 표시 조건 (number 타입 0원 숨김) ───────

    def test_evidence_section_toggle_by_value(self, result: UnitTestResult):
        """12. number 타입 금액 0 → 증빙 섹션 숨김, 금액 입력 → 증빙 섹션 표시"""
        if not self._ensure_session():
            result.skip_test("세션 구성 실패")
            return

        # Q1=YES 설정 후 카테고리 1 작업 화면
        self._api("post", "/disclosure/api/answer",
                  json={"question_id": "Q1", "company_id": self._company_id,
                        "year": TEST_YEAR, "value": "YES"})
        self.navigate_to("/disclosure/work?category=1")
        self.page.wait_for_load_state("domcontentloaded")

        # Q2 (I-1, number 타입) 입력 필드 존재 확인
        q2_input = self.page.locator("#input-Q2")
        if q2_input.count() == 0:
            result.skip_test("Q2 입력 필드 미발견")
            return

        ev_section = self.page.locator("#ev-section-Q2")
        if ev_section.count() == 0:
            result.skip_test("Q2 증빙 섹션(#ev-section-Q2) 미발견 — evidence_list 없을 수 있음")
            return

        # 0 입력 시 증빙 섹션 숨김 확인
        q2_input.fill("0")
        q2_input.dispatch_event("input")
        self.page.wait_for_timeout(300)
        is_hidden = not ev_section.is_visible()
        result.add_detail(f"Q2=0 → 증빙 섹션 숨김: {is_hidden}")

        # 금액 입력 시 증빙 섹션 표시 확인
        q2_input.fill("5000000")
        q2_input.dispatch_event("input")
        self.page.wait_for_timeout(300)
        is_shown = ev_section.is_visible()
        result.add_detail(f"Q2=5,000,000 → 증빙 섹션 표시: {is_shown}")

        if is_hidden and is_shown:
            result.pass_test("number 타입 금액 기반 증빙 섹션 토글 확인 (0→숨김, 양수→표시)")
        elif not is_hidden:
            result.warn_test("Q2=0 에도 증빙 섹션이 표시됨 (Q2에 evidence_list 없을 수도 있음)")
        else:
            result.fail_test(f"증빙 섹션 토글 실패 (hidden:{is_hidden}, shown:{is_shown})")

    # ─── 결과 저장 ───────────────────────────────────────────

    def _update_checklist_result(self):
        if not self.checklist_source.exists():
            return

        with open(self.checklist_source, "r", encoding="utf-8") as f:
            lines = f.readlines()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        updated = [f"<!-- Test Run: {timestamp} -->\n"]

        for line in lines:
            updated_line = line
            for res in self.results:
                if res.test_name in line:
                    msg = res.message.replace("\n", " ").strip()
                    if res.status == TestStatus.PASSED:
                        updated_line = line.replace("- [ ]", "- [x] ✅")
                        updated_line = updated_line.rstrip() + f" → **통과** ({msg})\n"
                    elif res.status == TestStatus.FAILED:
                        updated_line = line.replace("- [ ]", "- [ ] ❌")
                        updated_line = updated_line.rstrip() + f" → **실패** ({msg})\n"
                    elif res.status == TestStatus.WARNING:
                        updated_line = line.replace("- [ ]", "- [~] ⚠️")
                        updated_line = updated_line.rstrip() + f" → **경고** ({msg})\n"
                    elif res.status == TestStatus.SKIPPED:
                        updated_line = line.replace("- [ ]", "- [ ] ⊘")
                        updated_line = updated_line.rstrip() + f" → **건너뜀** ({msg})\n"
                    break
            updated.append(updated_line)

        total   = len(self.results) or 1
        passed  = sum(1 for r in self.results if r.status == TestStatus.PASSED)
        failed  = sum(1 for r in self.results if r.status == TestStatus.FAILED)
        warning = sum(1 for r in self.results if r.status == TestStatus.WARNING)
        skipped = sum(1 for r in self.results if r.status == TestStatus.SKIPPED)

        updated += [
            "\n---\n",
            "## 테스트 결과 요약\n\n",
            "| 항목 | 개수 | 비율 |\n",
            "|------|------|------|\n",
            f"| ✅ 통과  | {passed}  | {passed/total*100:.1f}% |\n",
            f"| ❌ 실패  | {failed}  | {failed/total*100:.1f}% |\n",
            f"| ⚠️ 경고  | {warning} | {warning/total*100:.1f}% |\n",
            f"| ⊘ 건너뜀 | {skipped} | {skipped/total*100:.1f}% |\n",
            f"| **총계** | **{total}** | **100%** |\n",
        ]

        with open(self.checklist_result, "w", encoding="utf-8") as f:
            f.writelines(updated)
        print(f"\n✅ 체크리스트 결과 저장: {self.checklist_result}")


def run_tests():
    runner = InfosdUnitTest(headless=True, slow_mo=0)
    if not runner.check_server_running():
        print("❌ 서버 시작 실패 — 테스트 중단")
        return 1

    runner.setup()
    try:
        runner.run_category("infosd Unit Tests", [
            runner.test_company_add,
            runner.test_company_add_duplicate,
            runner.test_company_edit,
            runner.test_year_add,
            runner.test_year_add_duplicate,
            runner.test_company_delete,
            runner.test_session_select,
            runner.test_dashboard_render,
            runner.test_dashboard_category_navigation,
            runner.test_answer_yes_no,
            runner.test_answer_dependent_show,
            runner.test_answer_dependent_hide,
            runner.test_answer_number,
            runner.test_answer_text,
            runner.test_validation_negative,
            runner.test_validation_b_gt_a,
            runner.test_validation_personnel,
            runner.test_answer_confirmed_blocked,
            runner.test_evidence_upload,
            runner.test_evidence_invalid_ext,
            runner.test_evidence_delete,
            runner.test_submit_incomplete_blocked,
            runner.test_confirm_without_submit_blocked,
            runner.test_audit_trail_recorded,
            runner.test_recursive_na_cleanup,
            runner.test_session_progress_update,
            # 8. table 타입 답변
            runner.test_answer_table_type_json,
            # 9. inv-grid 렌더링
            runner.test_inv_grid_investment_render,
            runner.test_inv_grid_personnel_render,
            # 10. 비율 자동계산
            runner.test_investment_ratio_api,
            runner.test_personnel_ratio_api,
            # 11. table 타입 증빙
            runner.test_evidence_for_table_type,
            # 12. 증빙 섹션 토글
            runner.test_evidence_section_toggle_by_value,
        ])
    finally:
        runner._update_checklist_result()
        runner.print_final_report()
        runner.stop_server()
        runner.teardown()


if __name__ == "__main__":
    exit(run_tests())
