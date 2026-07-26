"""Cross-browser accessibility, theme and responsive smoke matrix."""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, ViewportSize, expect

from tests.e2e.accessibility import audit_page, audit_page_with_axe
from tests.e2e.conftest import E2EStack

pytestmark = pytest.mark.e2e

_VIEWPORTS = [
    pytest.param({"width": 390, "height": 844}, id="mobile"),
    pytest.param({"width": 1440, "height": 1000}, id="desktop"),
]
_BROWSERS = ["chromium", "firefox", "webkit"]


def _assert_accessible(page_url: str, browser: Browser, viewport: ViewportSize) -> None:
    context = browser.new_context(
        viewport=viewport,
        locale="uk-UA",
        bypass_csp=True,
    )
    page = context.new_page()
    try:
        page.goto(page_url)
        expect(page.locator("main")).to_be_visible()
        violations = audit_page(page)
        assert violations == (), "\n".join(violations)
        axe_violations = audit_page_with_axe(page)
        assert axe_violations == (), "\n".join(axe_violations)

        page.keyboard.press("Tab")
        active_tag = page.evaluate("document.activeElement && document.activeElement.tagName")
        assert active_tag not in {None, "BODY", "HTML"}
        assert page.evaluate(
            "document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1"
        )
    finally:
        context.close()


@pytest.mark.parametrize("browser_name", _BROWSERS, indirect=True)
@pytest.mark.parametrize("viewport", _VIEWPORTS)
def test_public_and_login_accessibility_matrix(
    browser: Browser,
    e2e_stack: E2EStack,
    viewport: ViewportSize,
) -> None:
    """Check public and authentication surfaces in all supported engines."""

    for path in ("/", "/software", "/admin/login"):
        _assert_accessible(f"{e2e_stack.base_url}{path}", browser, viewport)


@pytest.mark.parametrize("browser_name", _BROWSERS, indirect=True)
def test_theme_preference_persists_in_real_browser(
    browser: Browser,
    e2e_stack: E2EStack,
) -> None:
    """Verify system/light/dark persistence against the real DOM and storage API."""

    context = browser.new_context(locale="uk-UA")
    page = context.new_page()
    try:
        page.goto(e2e_stack.base_url)
        toggle = page.locator("[data-theme-toggle]")
        expect(toggle).to_be_visible()

        toggle.click()
        expect(page.locator("html")).to_have_attribute("data-theme", "light")
        page.reload()
        expect(page.locator("html")).to_have_attribute("data-theme", "light")

        toggle = page.locator("[data-theme-toggle]")
        toggle.click()
        expect(page.locator("html")).to_have_attribute("data-theme", "dark")
        page.reload()
        expect(page.locator("html")).to_have_attribute("data-theme", "dark")

        page.locator("[data-theme-toggle]").click()
        expect(page.locator("html")).not_to_have_attribute("data-theme", "light")
        expect(page.locator("html")).not_to_have_attribute("data-theme", "dark")
        assert page.evaluate("localStorage.getItem('software-hub-theme')") is None
    finally:
        context.close()
