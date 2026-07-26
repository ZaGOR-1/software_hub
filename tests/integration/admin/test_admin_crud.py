"""End-to-end integration coverage for Phase 8 administration workflows."""

import re

from app.models import AuditLog, Category, Release, Software, Tag
from app.models.enums import ReleaseStatus, SoftwareStatus, Visibility
from app.services.auth_service import AuthService
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

_CSRF_PATTERN = re.compile(r'name="csrf_token" value="([^"]+)"')


def _csrf(response_text: str) -> str:
    match = _CSRF_PATTERN.search(response_text)
    assert match is not None
    return match.group(1)


def _login(application: FastAPI, client: TestClient) -> None:
    settings = application.state.settings
    AuthService(application.state.database, settings).create_admin(
        username="admin",
        password="correct horse battery staple",
    )
    page = client.get("/admin/login")
    response = client.post(
        "/admin/login",
        data={
            "username": "admin",
            "password": "correct horse battery staple",
            "csrf_token": _csrf(page.text),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def _page_token(client: TestClient, path: str) -> tuple[str, str]:
    response = client.get(path)
    assert response.status_code == 200
    return _csrf(response.text), response.text


def test_complete_admin_catalog_workflow(application: FastAPI, client: TestClient) -> None:
    _login(application, client)

    dashboard = client.get("/admin")
    assert dashboard.status_code == 200
    assert "Огляд Software Hub" in dashboard.text
    assert "/static/css/admin.css" in dashboard.text

    category_token, _ = _page_token(client, "/admin/categories")
    created_category = client.post(
        "/admin/categories",
        data={
            "csrf_token": category_token,
            "name": "Інструменти",
            "slug": "",
            "description": "Системні утиліти",
            "sort_order": "10",
            "is_visible": "on",
        },
        follow_redirects=False,
    )
    assert created_category.status_code == 303

    tag_token, _ = _page_token(client, "/admin/tags")
    created_tag = client.post(
        "/admin/tags",
        data={"csrf_token": tag_token, "name": "Безпека", "slug": ""},
        follow_redirects=False,
    )
    assert created_tag.status_code == 303

    with application.state.database.session() as session:
        category = session.scalar(select(Category).where(Category.slug == "instrumenty"))
        tag = session.scalar(select(Tag).where(Tag.slug == "bezpeka"))
        assert category is not None
        assert tag is not None
        category_id = category.id
        tag_id = tag.id

    new_software_token, _ = _page_token(client, "/admin/software/new")
    created_software = client.post(
        "/admin/software",
        data={
            "csrf_token": new_software_token,
            "name": "Zagor Tool",
            "slug": "",
            "short_description": "Корисна системна утиліта",
            "full_description": "Безпечний опис <script>alert(1)</script>",
            "developer_name": "Denis",
            "official_website_url": "https://example.com/tool",
            "source_url": "https://example.com/source",
            "license_name": "MIT",
            "category_id": str(category_id),
            "tag_ids": str(tag_id),
            "supported_os": "Windows 10/11",
            "system_requirements": "x64, 4 GB RAM",
            "visibility": "private",
            "is_featured": "on",
        },
        follow_redirects=False,
    )
    assert created_software.status_code == 303
    assert created_software.headers["location"].startswith("/admin/software/")

    with application.state.database.session() as session:
        software = session.scalar(select(Software).where(Software.slug == "zagor-tool"))
        assert software is not None
        software_id = software.id
        assert software.status is SoftwareStatus.DRAFT
        assert software.visibility is Visibility.PRIVATE
        assert software.category_id == category_id
        assert [item.id for item in software.tags] == [tag_id]

    preview_token, preview_html = _page_token(
        client,
        f"/admin/software/{software_id}/preview",
    )
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in preview_html
    assert "<script>alert(1)</script>" not in preview_html

    edit_token, _ = _page_token(client, f"/admin/software/{software_id}/edit")
    updated = client.post(
        f"/admin/software/{software_id}/edit",
        data={
            "csrf_token": edit_token,
            "name": "Zagor Tool Pro",
            "slug": "zagor-tool-pro",
            "short_description": "Оновлена утиліта",
            "full_description": "Оновлений plain text опис",
            "developer_name": "Denis Zagorovskiy",
            "official_website_url": "https://example.com/pro",
            "source_url": "",
            "license_name": "Proprietary",
            "category_id": str(category_id),
            "tag_ids": str(tag_id),
            "supported_os": "Windows 11",
            "system_requirements": "x64",
            "visibility": "public",
        },
        follow_redirects=False,
    )
    assert updated.status_code == 303

    published = client.post(
        f"/admin/software/{software_id}/publish",
        data={"csrf_token": preview_token},
        follow_redirects=False,
    )
    assert published.status_code == 303

    release_token, _ = _page_token(
        client,
        f"/admin/software/{software_id}/releases/new",
    )
    created_release = client.post(
        f"/admin/software/{software_id}/releases",
        data={
            "csrf_token": release_token,
            "version": "1.0.0",
            "release_channel": "stable",
            "release_date": "2026-07-23",
            "changelog": "Перший реліз",
        },
        follow_redirects=False,
    )
    assert created_release.status_code == 303

    with application.state.database.session() as session:
        release = session.scalar(
            select(Release).where(
                Release.software_id == software_id,
                Release.version == "1.0.0",
            )
        )
        assert release is not None
        release_id = release.id

    release_edit_token, _ = _page_token(client, f"/admin/releases/{release_id}/edit")
    edited_release = client.post(
        f"/admin/releases/{release_id}/edit",
        data={
            "csrf_token": release_edit_token,
            "version": "1.0.1",
            "release_channel": "stable",
            "release_date": "2026-07-24",
            "changelog": "Виправлення",
        },
        follow_redirects=False,
    )
    assert edited_release.status_code == 303

    release_edit_token, _ = _page_token(client, f"/admin/releases/{release_id}/edit")
    release_published = client.post(
        f"/admin/releases/{release_id}/publish",
        data={"csrf_token": release_edit_token},
        follow_redirects=False,
    )
    assert release_published.status_code == 303

    release_edit_token, _ = _page_token(client, f"/admin/releases/{release_id}/edit")
    current = client.post(
        f"/admin/releases/{release_id}/current",
        data={"csrf_token": release_edit_token},
        follow_redirects=False,
    )
    assert current.status_code == 303

    with application.state.database.session() as session:
        persisted_software = session.get(Software, software_id)
        persisted_release = session.get(Release, release_id)
        assert persisted_software is not None
        assert persisted_release is not None
        assert persisted_software.name == "Zagor Tool Pro"
        assert persisted_software.status is SoftwareStatus.PUBLISHED
        assert persisted_software.visibility is Visibility.PUBLIC
        assert persisted_release.version == "1.0.1"
        assert persisted_release.status is ReleaseStatus.PUBLISHED
        assert persisted_release.is_current is True
        actions = set(session.scalars(select(AuditLog.action)).all())
        assert {
            "category_created",
            "tag_created",
            "software_created",
            "software_updated",
            "software_status_changed",
            "release_created",
            "release_updated",
            "release_status_changed",
            "release_current_changed",
        } <= actions

    current_token, _ = _page_token(client, f"/admin/releases/{release_id}/edit")
    cleared = client.post(
        f"/admin/releases/{release_id}/current/clear",
        data={"csrf_token": current_token},
        follow_redirects=False,
    )
    assert cleared.status_code == 303

    archive_token, _ = _page_token(client, f"/admin/releases/{release_id}/edit")
    archived = client.post(
        f"/admin/releases/{release_id}/archive",
        data={"csrf_token": archive_token},
        follow_redirects=False,
    )
    assert archived.status_code == 303

    software_preview_token, _ = _page_token(
        client,
        f"/admin/software/{software_id}/preview",
    )
    hidden = client.post(
        f"/admin/software/{software_id}/hide",
        data={"csrf_token": software_preview_token},
        follow_redirects=False,
    )
    assert hidden.status_code == 303

    software_preview_token, _ = _page_token(
        client,
        f"/admin/software/{software_id}/preview",
    )
    disabled = client.post(
        f"/admin/software/{software_id}/disable",
        data={"csrf_token": software_preview_token},
        follow_redirects=False,
    )
    assert disabled.status_code == 303

    software_preview_token, _ = _page_token(
        client,
        f"/admin/software/{software_id}/preview",
    )
    restored = client.post(
        f"/admin/software/{software_id}/restore",
        data={"csrf_token": software_preview_token},
        follow_redirects=False,
    )
    assert restored.status_code == 303

    category_edit_token, _ = _page_token(client, f"/admin/categories/{category_id}/edit")
    category_update = client.post(
        f"/admin/categories/{category_id}/edit",
        data={
            "csrf_token": category_edit_token,
            "name": "Системні інструменти",
            "slug": "system-tools",
            "description": "Оновлено",
            "sort_order": "5",
            "is_visible": "on",
        },
        follow_redirects=False,
    )
    assert category_update.status_code == 303

    tag_edit_token, _ = _page_token(client, f"/admin/tags/{tag_id}/edit")
    tag_update = client.post(
        f"/admin/tags/{tag_id}/edit",
        data={
            "csrf_token": tag_edit_token,
            "name": "Security",
            "slug": "security",
        },
        follow_redirects=False,
    )
    assert tag_update.status_code == 303

    tag_edit_token, _ = _page_token(client, f"/admin/tags/{tag_id}/edit")
    tag_deleted = client.post(
        f"/admin/tags/{tag_id}/delete",
        data={"csrf_token": tag_edit_token, "confirm": "yes"},
        follow_redirects=False,
    )
    assert tag_deleted.status_code == 303

    category_edit_token, _ = _page_token(client, f"/admin/categories/{category_id}/edit")
    category_deleted = client.post(
        f"/admin/categories/{category_id}/delete",
        data={"csrf_token": category_edit_token, "confirm": "yes"},
        follow_redirects=False,
    )
    assert category_deleted.status_code == 303

    with application.state.database.session() as session:
        persisted_software = session.get(Software, software_id)
        assert persisted_software is not None
        assert persisted_software.category_id is None
        assert persisted_software.tags == []
        assert session.get(Category, category_id) is None
        assert session.get(Tag, tag_id) is None

    final_dashboard = client.get("/admin")
    assert final_dashboard.status_code == 200
    assert "1" in final_dashboard.text


def test_admin_forms_validate_conflicts_urls_and_confirmations(
    application: FastAPI,
    client: TestClient,
) -> None:
    _login(application, client)

    token, _ = _page_token(client, "/admin/categories")
    assert (
        client.post(
            "/admin/categories",
            data={"csrf_token": token, "name": "Utilities", "slug": "utilities"},
            follow_redirects=False,
        ).status_code
        == 303
    )

    token, _ = _page_token(client, "/admin/categories")
    duplicate = client.post(
        "/admin/categories",
        data={"csrf_token": token, "name": "Other", "slug": "utilities"},
    )
    assert duplicate.status_code == 409
    assert "already exists" in duplicate.text

    token, _ = _page_token(client, "/admin/software/new")
    invalid_url = client.post(
        "/admin/software",
        data={
            "csrf_token": token,
            "name": "Bad URL",
            "short_description": "Test",
            "official_website_url": "file:///etc/passwd",
            "visibility": "private",
        },
    )
    assert invalid_url.status_code == 422
    assert "HTTP or HTTPS" in invalid_url.text
    assert "/etc/passwd" not in invalid_url.text

    missing_csrf = client.post(
        "/admin/tags",
        data={"name": "Missing CSRF", "slug": "missing-csrf"},
        headers={"accept": "application/json"},
    )
    assert missing_csrf.status_code == 403

    with application.state.database.session() as session:
        category = session.scalar(select(Category).where(Category.slug == "utilities"))
        assert category is not None
        category_id = category.id

    edit_token, _ = _page_token(client, f"/admin/categories/{category_id}/edit")
    no_confirmation = client.post(
        f"/admin/categories/{category_id}/delete",
        data={"csrf_token": edit_token},
        headers={"accept": "application/json"},
    )
    assert no_confirmation.status_code == 422
    with application.state.database.session() as session:
        assert session.get(Category, category_id) is not None


def test_unauthenticated_admin_routes_redirect(client: TestClient) -> None:
    for path in (
        "/admin/categories",
        "/admin/tags",
        "/admin/software",
        "/admin/software/new",
    ):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/admin/login"
