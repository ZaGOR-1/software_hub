"""Public catalog, search, visibility and release-history integration coverage."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from uuid import uuid4

from app.models import Category, Release, ReleaseFile, Software, Tag
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
from sqlalchemy import event
from sqlalchemy.engine import Engine

_CSRF_PATTERN = re.compile(r'name="csrf_token" value="([^"]+)"')


@dataclass(frozen=True, slots=True)
class CatalogFixture:
    public_slug: str
    second_slug: str
    unlisted_slug: str
    archived_slug: str
    private_slug: str
    draft_slug: str
    disabled_slug: str
    visible_category_slug: str
    hidden_category_slug: str
    public_tag_slug: str
    private_tag_slug: str
    public_filename: str
    private_filename: str
    public_uuid: str
    storage_filename: str
    relative_path: str


def _release_file(
    release: Release,
    *,
    filename: str,
    downloads: int,
    visibility: Visibility = Visibility.PUBLIC,
    status: FileStatus = FileStatus.PUBLISHED,
    sha: str,
) -> ReleaseFile:
    storage_filename = f"{uuid4().hex}.zip"
    return ReleaseFile(
        release=release,
        original_filename=filename,
        display_filename=filename,
        storage_filename=storage_filename,
        relative_storage_path=(
            f"{storage_filename[:2]}/{storage_filename[2:4]}/{storage_filename}"
        ),
        file_extension=".zip",
        detected_mime_type="application/zip",
        file_size_bytes=1_048_576,
        sha256=sha,
        architecture=Architecture.X64,
        package_type=PackageType.ARCHIVE,
        platform="windows",
        download_count=downloads,
        status=status,
        visibility=visibility,
        signature_status=SignatureStatus.VALID,
        scanner_status=ScannerStatus.CLEAN,
        admin_note="INTERNAL-ADMIN-NOTE",
    )


def _create_catalog(
    application: FastAPI,
) -> CatalogFixture:
    public_filename = "7-Zip Українська.zip"
    private_filename = "7-Zip private.zip"
    with application.state.database.transaction() as session:
        visible_category = Category(
            name="Архіватори",
            slug="archivers",
            description="Робота з архівами.",
            is_visible=True,
        )
        hidden_category = Category(
            name="Секретна категорія",
            slug="secret-category",
            is_visible=False,
        )
        public_tag = Tag(name="Утиліти", slug="utilities")
        private_tag = Tag(name="Приватний тег", slug="private-tag")

        public = Software(
            name="7-Zip",
            slug="7-zip-public",
            short_description="Швидкий файловий архіватор.",
            full_description="Безпечний опис.\n<script>alert('xss')</script>",
            developer_name="Igor Pavlov",
            official_website_url="https://www.7-zip.org/",
            source_url="https://source.example/7zip",
            license_name="LGPL",
            supported_os="Windows 10 та Windows 11",
            system_requirements="64-bit процесор",
            category=visible_category,
            tags=[public_tag],
            status=SoftwareStatus.PUBLISHED,
            visibility=Visibility.PUBLIC,
            is_featured=True,
        )
        current = Release(
            software=public,
            version="26.00",
            release_channel=ReleaseChannel.STABLE,
            release_date=date(2026, 7, 1),
            changelog="Поточний реліз.",
            is_current=True,
            status=ReleaseStatus.PUBLISHED,
        )
        public_file = _release_file(
            current,
            filename=public_filename,
            downloads=75,
            sha="a" * 64,
        )
        _release_file(
            current,
            filename="7-Zip hidden direct.zip",
            downloads=500,
            visibility=Visibility.UNLISTED,
            sha="b" * 64,
        )
        _release_file(
            current,
            filename=private_filename,
            downloads=900,
            visibility=Visibility.PRIVATE,
            sha="c" * 64,
        )
        _release_file(
            current,
            filename="7-Zip quarantine.zip",
            downloads=0,
            status=FileStatus.QUARANTINE,
            sha="d" * 64,
        )
        legacy = Release(
            software=public,
            version="25.00",
            release_channel=ReleaseChannel.LEGACY,
            release_date=date(2025, 12, 1),
            changelog="Старий реліз.",
            status=ReleaseStatus.ARCHIVED,
        )
        _release_file(
            legacy,
            filename="7-Zip 25.00.zip",
            downloads=10,
            sha="e" * 64,
        )
        draft_release = Release(
            software=public,
            version="27.00-dev",
            release_channel=ReleaseChannel.NIGHTLY,
            status=ReleaseStatus.DRAFT,
        )
        _release_file(
            draft_release,
            filename="TOP-SECRET-NIGHTLY.zip",
            downloads=0,
            sha="f" * 64,
        )

        second = Software(
            name="Alpha Tool 100%",
            slug="alpha-tool",
            short_description="Друга публічна програма.",
            category=visible_category,
            tags=[public_tag],
            status=SoftwareStatus.PUBLISHED,
            visibility=Visibility.PUBLIC,
        )
        second_release = Release(
            software=second,
            version="1.0",
            release_channel=ReleaseChannel.STABLE,
            release_date=date(2026, 6, 1),
            is_current=True,
            status=ReleaseStatus.PUBLISHED,
        )
        _release_file(
            second_release,
            filename="Alpha Tool.zip",
            downloads=5,
            sha="1" * 64,
        )

        unlisted = Software(
            name="Unlisted Utility",
            slug="unlisted-utility",
            short_description="Доступна лише за прямим посиланням.",
            status=SoftwareStatus.PUBLISHED,
            visibility=Visibility.UNLISTED,
        )
        unlisted_release = Release(
            software=unlisted,
            version="2.0",
            release_channel=ReleaseChannel.STABLE,
            is_current=True,
            status=ReleaseStatus.PUBLISHED,
        )
        _release_file(
            unlisted_release,
            filename="Unlisted.zip",
            downloads=2,
            sha="2" * 64,
        )

        archived = Software(
            name="Archived Utility",
            slug="archived-utility",
            short_description="Архівна програма.",
            status=SoftwareStatus.ARCHIVED,
            visibility=Visibility.PUBLIC,
        )
        archived_release = Release(
            software=archived,
            version="0.9",
            release_channel=ReleaseChannel.LEGACY,
            status=ReleaseStatus.ARCHIVED,
        )
        _release_file(
            archived_release,
            filename="Archived.zip",
            downloads=1,
            sha="3" * 64,
        )

        private = Software(
            name="Private Utility",
            slug="private-utility",
            short_description="Приватна програма.",
            category=hidden_category,
            tags=[private_tag],
            status=SoftwareStatus.PUBLISHED,
            visibility=Visibility.PRIVATE,
        )
        private_release = Release(
            software=private,
            version="3.0",
            release_channel=ReleaseChannel.STABLE,
            is_current=True,
            status=ReleaseStatus.PUBLISHED,
        )
        _release_file(
            private_release,
            filename="Private Utility.zip",
            downloads=4,
            visibility=Visibility.PRIVATE,
            sha="4" * 64,
        )

        draft = Software(
            name="Draft Utility",
            slug="draft-utility",
            short_description="Чернетка.",
            status=SoftwareStatus.DRAFT,
            visibility=Visibility.PRIVATE,
        )
        disabled = Software(
            name="Disabled Utility",
            slug="disabled-utility",
            short_description="Вимкнена.",
            status=SoftwareStatus.DISABLED,
            visibility=Visibility.PRIVATE,
        )
        public_hidden_category = Software(
            name="Visible App Hidden Category",
            slug="visible-hidden-category",
            short_description="Публічна програма без публічної категорії.",
            category=hidden_category,
            status=SoftwareStatus.PUBLISHED,
            visibility=Visibility.PUBLIC,
        )
        session.add_all(
            [
                public,
                second,
                unlisted,
                archived,
                private,
                draft,
                disabled,
                public_hidden_category,
            ]
        )
        session.flush()
        return CatalogFixture(
            public_slug=public.slug,
            second_slug=second.slug,
            unlisted_slug=unlisted.slug,
            archived_slug=archived.slug,
            private_slug=private.slug,
            draft_slug=draft.slug,
            disabled_slug=disabled.slug,
            visible_category_slug=visible_category.slug,
            hidden_category_slug=hidden_category.slug,
            public_tag_slug=public_tag.slug,
            private_tag_slug=private_tag.slug,
            public_filename=public_filename,
            private_filename=private_filename,
            public_uuid=str(public_file.public_uuid),
            storage_filename=public_file.storage_filename,
            relative_path=public_file.relative_storage_path,
        )


def _login(application: FastAPI, client: TestClient) -> None:
    settings = application.state.settings
    AuthService(application.state.database, settings).create_admin(
        username="public-admin",
        password="correct horse battery staple",
    )
    page = client.get("/admin/login")
    match = _CSRF_PATTERN.search(page.text)
    assert match is not None
    response = client.post(
        "/admin/login",
        data={
            "username": "public-admin",
            "password": "correct horse battery staple",
            "csrf_token": match.group(1),
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_home_and_catalog_show_only_publicly_listed_software(
    application: FastAPI,
    client: TestClient,
) -> None:
    item = _create_catalog(application)

    home = client.get("/")
    assert home.status_code == 200
    assert "7-Zip" in home.text
    assert "Alpha Tool 100%" in home.text
    assert "Архіватори" in home.text
    assert "Unlisted Utility" not in home.text
    assert "Archived Utility" not in home.text
    assert "Private Utility" not in home.text
    assert "Draft Utility" not in home.text
    assert item.hidden_category_slug not in home.text
    assert item.private_tag_slug not in home.text

    catalog = client.get("/software")
    assert catalog.status_code == 200
    assert "Знайдено: <strong>3</strong>" in catalog.text
    assert "Visible App Hidden Category" in catalog.text
    assert "Секретна категорія" not in catalog.text
    assert item.storage_filename not in catalog.text
    assert item.relative_path not in catalog.text


def test_catalog_search_filters_sorts_and_escapes_wildcards(
    application: FastAPI,
    client: TestClient,
) -> None:
    item = _create_catalog(application)

    search = client.get("/search", params={"q": "7-Zip"})
    assert search.status_code == 200
    assert "7-Zip" in search.text
    assert "Alpha Tool 100%" not in search.text

    wildcard = client.get("/software", params={"q": "100%"})
    assert wildcard.status_code == 200
    assert "Alpha Tool 100%" in wildcard.text
    assert "7-Zip" not in wildcard.text

    category = client.get(f"/category/{item.visible_category_slug}")
    assert category.status_code == 200
    assert "7-Zip" in category.text
    assert "Alpha Tool 100%" in category.text
    assert "Visible App Hidden Category" not in category.text

    tag = client.get("/software", params={"tag": item.public_tag_slug})
    assert tag.status_code == 200
    assert "7-Zip" in tag.text
    assert "Alpha Tool 100%" in tag.text

    name_sort = client.get("/software", params={"sort": "name"})
    assert name_sort.text.index("7-Zip") < name_sort.text.index("Alpha Tool 100%")

    popularity = client.get("/software", params={"sort": "popularity"})
    assert popularity.text.index("7-Zip") < popularity.text.index("Alpha Tool 100%")

    assert client.get("/software", params={"q": "x"}).status_code == 422
    assert client.get("/software", params={"q": "x" * 101}).status_code == 422
    assert client.get("/software", params={"sort": "drop-table"}).status_code == 422
    assert client.get(f"/category/{item.hidden_category_slug}").status_code == 404
    assert client.get("/software", params={"tag": item.private_tag_slug}).status_code == 404


def test_public_detail_and_release_history_expose_only_safe_metadata(
    application: FastAPI,
    client: TestClient,
) -> None:
    item = _create_catalog(application)

    detail = client.get(f"/software/{item.public_slug}")
    assert detail.status_code == 200
    assert "Версія 26.00" in detail.text
    assert item.public_filename in detail.text
    assert item.public_uuid in detail.text
    assert "a" * 64 in detail.text
    assert "7-Zip hidden direct.zip" not in detail.text
    assert item.private_filename not in detail.text
    assert "TOP-SECRET-NIGHTLY.zip" not in detail.text
    assert "INTERNAL-ADMIN-NOTE" not in detail.text
    assert item.storage_filename not in detail.text
    assert item.relative_path not in detail.text
    assert "&lt;script&gt;alert" in detail.text
    assert "<script>alert" not in detail.text
    assert "%D0%A3%D0%BA%D1%80%D0%B0%D1%97%D0%BD%D1%81%D1%8C%D0%BA%D0%B0" in detail.text

    releases = client.get(f"/software/{item.public_slug}/releases")
    assert releases.status_code == 200
    assert "26.00" in releases.text
    assert "25.00" in releases.text
    assert "27.00-dev" not in releases.text
    assert "7-Zip 25.00.zip" in releases.text


def test_direct_visibility_rules_and_admin_private_preview(
    application: FastAPI,
    client: TestClient,
) -> None:
    item = _create_catalog(application)

    unlisted = client.get(f"/software/{item.unlisted_slug}")
    assert unlisted.status_code == 200
    assert 'content="noindex, nofollow"' in unlisted.text
    assert "Unlisted Utility" not in client.get("/software").text

    archived = client.get(f"/software/{item.archived_slug}")
    assert archived.status_code == 200
    assert "Програму архівовано" in archived.text

    assert client.get(f"/software/{item.private_slug}").status_code == 404
    assert client.get(f"/software/{item.draft_slug}").status_code == 404
    assert client.get(f"/software/{item.disabled_slug}").status_code == 404

    _login(application, client)
    private = client.get(f"/software/{item.private_slug}")
    assert private.status_code == 200
    assert "Приватна сторінка" in private.text
    assert "Private Utility.zip" in private.text
    assert "Секретна категорія" in private.text
    assert 'content="noindex, nofollow"' in private.text

    draft = client.get(f"/software/{item.draft_slug}")
    assert draft.status_code == 200
    assert "Draft Utility" in draft.text
    assert client.get(f"/software/{item.disabled_slug}").status_code == 404


def test_catalog_pagination_and_query_count_are_bounded(
    application: FastAPI,
    client: TestClient,
) -> None:
    _create_catalog(application)
    with application.state.database.transaction() as session:
        for index in range(20):
            session.add(
                Software(
                    name=f"Pagination Tool {index:02d}",
                    slug=f"pagination-tool-{index:02d}",
                    short_description="Pagination fixture.",
                    status=SoftwareStatus.PUBLISHED,
                    visibility=Visibility.PUBLIC,
                )
            )

    query_count = 0

    def count_query(*_args: object, **_kwargs: object) -> None:
        nonlocal query_count
        query_count += 1

    engine: Engine = application.state.database.engine
    event.listen(engine, "before_cursor_execute", count_query)
    try:
        first = client.get("/software", params={"sort": "name"})
    finally:
        event.remove(engine, "before_cursor_execute", count_query)

    assert first.status_code == 200
    assert "Сторінка 1 з 2" in first.text
    assert "Наступна" in first.text
    assert query_count <= 10

    second = client.get("/software", params={"sort": "name", "page": 2})
    assert second.status_code == 200
    assert "Сторінка 2 з 2" in second.text
    assert "Pagination Tool 19" in second.text


def test_robots_favicon_and_static_public_assets(client: TestClient) -> None:
    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert "Disallow: /admin" in robots.text
    assert "Disallow: /protected-downloads" in robots.text
    assert "Disallow: /internal" in robots.text

    favicon = client.get("/favicon.ico", follow_redirects=False)
    assert favicon.status_code == 307
    assert favicon.headers["location"] == "/static/icons/favicon.svg"
    assert client.get("/static/icons/favicon.svg").status_code == 200
    assert client.get("/static/css/public.css").status_code == 200
