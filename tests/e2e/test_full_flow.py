"""Full browser flow from administrator login to protected public download."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.conftest import E2EStack

pytestmark = pytest.mark.e2e


def _login(page: Page, stack: E2EStack) -> None:
    page.goto(f"{stack.base_url}/admin/login")
    page.locator("#username").fill(stack.username)
    page.locator("#password").fill(stack.password)
    page.get_by_role("button", name="Увійти").click()
    expect(page).to_have_url(re.compile(r"/admin(?:\?.*)?$"))
    expect(page.get_by_role("heading", name="Огляд Software Hub")).to_be_visible()


def _id_from_url(page: Page, pattern: str) -> int:
    match = re.search(pattern, page.url)
    if match is None:
        raise AssertionError(f"Cannot extract identifier from URL: {page.url}")
    return int(match.group(1))


@pytest.mark.parametrize("browser_name", ["chromium"], indirect=True)
def test_admin_upload_publish_download_disable_flow(
    page: Page,
    e2e_stack: E2EStack,
    tmp_path: Path,
) -> None:
    """Exercise the complete critical MVP flow through rendered HTML forms."""

    _login(page, e2e_stack)

    page.goto(f"{e2e_stack.base_url}/admin/categories")
    page.locator('form[action="/admin/categories"] input[name="name"]').fill("Системні утиліти")
    page.get_by_role("button", name="Створити категорію").click()
    expect(page.get_by_text("Системні утиліти", exact=True).first).to_be_visible()

    page.goto(f"{e2e_stack.base_url}/admin/software/new")
    page.locator('input[name="name"]').fill("Phase 18 E2E Tool")
    page.locator('textarea[name="short_description"]').fill("Повний браузерний E2E сценарій.")
    page.locator('textarea[name="full_description"]').fill(
        "Тестова програма для перевірки upload, publish і download через Nginx."
    )
    page.locator('input[name="developer_name"]').fill("Software Hub CI")
    page.locator('input[name="license_name"]').fill("Test-only")
    page.locator('select[name="category_id"]').select_option(label="Системні утиліти")
    page.locator('select[name="visibility"]').select_option("public")
    page.get_by_role("button", name="Створити чернетку").click()
    software_id = _id_from_url(page, r"/admin/software/(\d+)/preview")

    page.get_by_role("button", name="Опублікувати").click()
    expect(page.get_by_text("published", exact=True).first).to_be_visible()

    page.get_by_role("link", name="Новий реліз").click()
    page.locator('input[name="version"]').fill("1.0.0")
    page.locator('textarea[name="changelog"]').fill("Перший production-like E2E реліз.")
    page.get_by_role("button", name="Створити реліз").click()
    release_id = _id_from_url(page, r"/admin/releases/(\d+)/edit")

    page.get_by_role("button", name="Опублікувати").click()
    page.goto(f"{e2e_stack.base_url}/admin/releases/{release_id}/edit")
    page.get_by_role("button", name="Зробити current stable").click()
    page.goto(f"{e2e_stack.base_url}/admin/releases/{release_id}/edit")
    expect(page.get_by_role("button", name="Зняти позначку current")).to_be_visible()

    page.get_by_role("link", name="Завантажити файл").click()
    page.locator('input[name="file"]').set_input_files(e2e_stack.upload_file)
    page.locator('input[name="display_filename"]').fill("phase18-e2e-tool.zip")
    page.locator('select[name="architecture"]').select_option("x64")
    page.locator('select[name="package_type"]').select_option("archive")
    page.locator('select[name="visibility"]').select_option("public")
    page.get_by_role("button", name="Завантажити в quarantine").click()
    file_id = _id_from_url(page, r"/admin/files/(\d+)")
    expect(page.get_by_text("ready", exact=True).first).to_be_visible()

    page.get_by_role("button", name="Опублікувати").click()
    expect(page.get_by_text("published", exact=True).first).to_be_visible()

    public_url = f"{e2e_stack.base_url}/software/phase-18-e2e-tool"
    page.goto(public_url)
    expect(page.get_by_role("heading", name="Phase 18 E2E Tool")).to_be_visible()
    download_link = page.get_by_role(
        "link",
        name=re.compile(r"Завантажити phase18-e2e-tool\.zip"),
    ).first
    download_href = download_link.get_attribute("href")
    assert download_href is not None

    with page.expect_download() as download_info:
        download_link.click()
    download = download_info.value
    assert download.suggested_filename == "phase18-e2e-tool.zip"
    saved_path = tmp_path / download.suggested_filename
    download.save_as(saved_path)
    assert saved_path.read_bytes() == e2e_stack.upload_file.read_bytes()

    page.goto(f"{e2e_stack.base_url}/admin/files/{file_id}")
    page.get_by_role("button", name="Вимкнути").click()
    expect(page.get_by_text("disabled", exact=True).first).to_be_visible()

    response = page.request.get(f"{e2e_stack.base_url}{download_href}")
    assert response.status == 404
    page.goto(public_url)
    download_link = page.get_by_role(
        "link",
        name=re.compile(r"Завантажити phase18-e2e-tool\.zip"),
    )
    expect(download_link).to_have_count(0)

    page.goto(f"{e2e_stack.base_url}/admin/software/{software_id}/preview")
    expect(page.get_by_text("Phase 18 E2E Tool", exact=True).first).to_be_visible()
