"""SEO, theme, accessibility and sitemap integration coverage for Phase 14."""

from __future__ import annotations

import re
from datetime import date

from app.models import Category, Release, ReleaseFile, Software
from app.models.enums import (
    Architecture,
    FileStatus,
    PackageType,
    ReleaseChannel,
    ReleaseStatus,
    ScannerStatus,
    SignatureStatus,
    SoftwareStatus,
    Visibility,
)
from app.services.auth_service import AuthService
from fastapi import FastAPI
from fastapi.testclient import TestClient

_CSRF_PATTERN = re.compile(r'name="csrf_token" value="([^"]+)"')


def _seed_public_pages(application: FastAPI) -> tuple[str, str]:
    with application.state.database.transaction() as session:
        category = Category(
            name="Утиліти",
            slug="utilities-phase14",
            description="Публічна категорія.",
            is_visible=True,
        )
        public = Software(
            name="Accessible Tool",
            slug="accessible-tool",
            short_description="Публічна програма для SEO та accessibility тестів.",
            category=category,
            status=SoftwareStatus.PUBLISHED,
            visibility=Visibility.PUBLIC,
        )
        release = Release(
            software=public,
            version="1.0",
            release_channel=ReleaseChannel.STABLE,
            release_date=date(2026, 7, 24),
            status=ReleaseStatus.PUBLISHED,
            is_current=True,
        )
        file = ReleaseFile(
            release=release,
            original_filename="Accessible Tool.zip",
            display_filename="Accessible Tool.zip",
            storage_filename="a" * 32 + ".zip",
            relative_storage_path="aa/aa/" + "a" * 32 + ".zip",
            file_extension=".zip",
            detected_mime_type="application/zip",
            file_size_bytes=1024,
            sha256="a" * 64,
            architecture=Architecture.X64,
            package_type=PackageType.ARCHIVE,
            platform="Windows",
            status=FileStatus.PUBLISHED,
            visibility=Visibility.PUBLIC,
            scanner_status=ScannerStatus.CLEAN,
            signature_status=SignatureStatus.VALID,
        )
        private = Software(
            name="Private Sitemap Tool",
            slug="private-sitemap-tool",
            short_description="Не повинна потрапити в sitemap.",
            status=SoftwareStatus.PUBLISHED,
            visibility=Visibility.PRIVATE,
        )
        unlisted = Software(
            name="Unlisted Sitemap Tool",
            slug="unlisted-sitemap-tool",
            short_description="Не повинна потрапити в sitemap.",
            status=SoftwareStatus.PUBLISHED,
            visibility=Visibility.UNLISTED,
        )
        draft = Software(
            name="Draft Sitemap Tool",
            slug="draft-sitemap-tool",
            short_description="Не повинна потрапити в sitemap.",
            status=SoftwareStatus.DRAFT,
            visibility=Visibility.PUBLIC,
        )
        session.add_all([public, private, unlisted, draft])
        session.flush()
        return public.slug, str(file.public_uuid)


def _login(application: FastAPI, client: TestClient) -> None:
    AuthService(application.state.database, application.state.settings).create_admin(
        username="phase14-admin",
        password="correct horse battery staple",
    )
    page = client.get("/admin/login")
    match = _CSRF_PATTERN.search(page.text)
    assert match is not None
    response = client.post(
        "/admin/login",
        data={
            "username": "phase14-admin",
            "password": "correct horse battery staple",
            "csrf_token": match.group(1),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_public_shell_contains_trusted_seo_and_accessibility_metadata(
    client: TestClient,
) -> None:
    response = client.get("/", headers={"Host": "testserver"})

    assert response.status_code == 200
    assert '<html lang="uk">' in response.text
    assert '<link rel="canonical" href="http://localhost:8000/">' in response.text
    assert 'property="og:url" content="http://localhost:8000/"' in response.text
    assert 'property="og:locale" content="uk_UA"' in response.text
    assert '<meta name="robots" content="index, follow">' in response.text
    assert 'href="/static/css/theme.css"' in response.text
    assert 'src="/static/js/theme.js" defer' in response.text
    assert "data-theme-toggle hidden" in response.text
    assert 'href="#main-content"' in response.text
    assert 'id="main-content" class="container page-shell" tabindex="-1"' in response.text
    assert "<script>" not in response.text


def test_populated_home_software_card_ids_are_unique(
    application: FastAPI,
    client: TestClient,
) -> None:
    _seed_public_pages(application)

    response = client.get("/")

    identifiers = re.findall(r'\sid="([^"]+)"', response.text)
    assert len(identifiers) == len(set(identifiers))
    assert 'id="software-latest-accessible-tool-title"' in response.text
    assert 'id="software-popular-accessible-tool-title"' in response.text


def test_search_is_noindex_and_public_detail_has_article_metadata(
    application: FastAPI,
    client: TestClient,
) -> None:
    public_slug, _ = _seed_public_pages(application)

    search = client.get("/search", params={"q": "Accessible"})
    assert '<meta name="robots" content="noindex, follow">' in search.text
    assert '<link rel="canonical" href="http://localhost:8000/search">' in search.text

    detail = client.get(f"/software/{public_slug}")
    assert detail.status_code == 200
    assert 'property="og:type" content="article"' in detail.text
    assert (
        f'<link rel="canonical" href="http://localhost:8000/software/{public_slug}">' in detail.text
    )
    assert '<caption class="visually-hidden">Доступні файли релізу 1.0</caption>' in detail.text
    assert 'role="region" aria-label="Файли релізу 1.0"' in detail.text
    assert 'aria-label="Завантажити Accessible Tool.zip"' in detail.text


def test_sitemap_and_robots_expose_only_indexable_public_pages(
    application: FastAPI,
    client: TestClient,
) -> None:
    public_slug, _ = _seed_public_pages(application)

    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert sitemap.headers["content-type"].startswith("application/xml")
    assert "http://localhost:8000/" in sitemap.text
    assert "http://localhost:8000/software" in sitemap.text
    assert f"http://localhost:8000/software/{public_slug}" in sitemap.text
    assert f"http://localhost:8000/software/{public_slug}/releases" in sitemap.text
    assert "http://localhost:8000/category/utilities-phase14" in sitemap.text
    assert "private-sitemap-tool" not in sitemap.text
    assert "unlisted-sitemap-tool" not in sitemap.text
    assert "draft-sitemap-tool" not in sitemap.text
    assert "<lastmod>" in sitemap.text

    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert "Disallow: /admin" in robots.text
    assert "Sitemap: http://localhost:8000/sitemap.xml" in robots.text


def test_login_error_and_admin_shell_are_noindex_and_accessible(
    application: FastAPI,
    client: TestClient,
) -> None:
    login = client.get("/admin/login")
    assert login.status_code == 200
    assert '<meta name="robots" content="noindex, nofollow">' in login.text
    assert 'href="/static/css/system.css"' in login.text
    assert '<label class="system-field" for="username">' in login.text
    assert '<label class="system-field" for="password">' in login.text
    assert 'id="main-content" class="system-main" tabindex="-1"' in login.text

    missing = client.get("/missing-phase14", headers={"Accept": "text/html"})
    assert missing.status_code == 404
    assert '<meta name="robots" content="noindex, nofollow">' in missing.text
    assert 'href="/static/css/system.css"' in missing.text
    assert 'id="error-title"' in missing.text

    _login(application, client)
    admin = client.get("/admin")
    assert admin.status_code == 200
    assert '<meta name="robots" content="noindex, nofollow">' in admin.text
    assert "data-theme-toggle hidden" in admin.text
    assert 'id="main-content" class="admin-main" tabindex="-1"' in admin.text
    assert 'aria-label="Адміністративна навігація"' in admin.text


def test_theme_assets_support_persistence_reduced_motion_and_csp(
    client: TestClient,
) -> None:
    javascript = client.get("/static/js/theme.js")
    shared_css = client.get("/static/css/theme.css")
    public_css = client.get("/static/css/public.css")
    admin_css = client.get("/static/css/admin.css")

    assert javascript.status_code == 200
    assert 'const STORAGE_KEY = "software-hub-theme"' in javascript.text
    assert 'document.documentElement.setAttribute("data-theme", theme)' in javascript.text
    assert "window.localStorage" in javascript.text
    assert "innerHTML" not in javascript.text
    assert "prefers-reduced-motion: reduce" in shared_css.text
    assert 'html[data-theme="light"]' in public_css.text
    assert 'html[data-theme="dark"]' in public_css.text
    assert 'html[data-theme="light"]' in admin_css.text
    assert 'html[data-theme="dark"]' in admin_css.text

    home = client.get("/")
    policy = home.headers["content-security-policy"]
    assert "script-src 'self'" in policy
    assert "style-src 'self'" in policy
    assert "'unsafe-inline'" not in policy
