"""Integration coverage for session-bound SQLAlchemy repositories."""

from datetime import UTC, date, datetime, timedelta

from app.core.time import utc_now
from app.database.session import Database
from app.models import (
    AuditLog,
    Category,
    FileStatus,
    Release,
    ReleaseChannel,
    ReleaseFile,
    ReleaseStatus,
    Software,
    SoftwareStatus,
    Tag,
    Visibility,
)
from app.repositories import (
    AuditRepository,
    CategoryRepository,
    DownloadStatRepository,
    ReleaseFileRepository,
    ReleaseRepository,
    SessionRepository,
    SoftwareFilters,
    SoftwareRepository,
    SoftwareSort,
    TagRepository,
    UserRepository,
)
from app.schemas.pagination import Pagination
from sqlalchemy import event
from tests.fixtures.models import make_catalog_graph, make_session, make_user


def seed_search_catalog(database: Database) -> dict[str, int]:
    """Create deterministic searchable entries with popularity metadata."""

    with database.transaction() as session:
        archivers = Category(name="Archivers", slug="archivers", sort_order=1)
        editors = Category(name="Editors", slug="editors", sort_order=2)
        utility = Tag(name="Utility", slug="utility")
        portable = Tag(name="Portable", slug="portable")

        seven_zip = Software(
            name="7-Zip",
            slug="7-zip",
            short_description="Fast file archiver",
            developer_name="Igor Pavlov",
            category=archivers,
            tags=[utility],
            status=SoftwareStatus.PUBLISHED,
            visibility=Visibility.PUBLIC,
            updated_at=datetime(2026, 7, 20, tzinfo=UTC),
        )
        notepad = Software(
            name="Notepad Plus",
            slug="notepad-plus",
            short_description="Source code editor",
            developer_name="Don Ho",
            category=editors,
            tags=[utility, portable],
            status=SoftwareStatus.HIDDEN,
            visibility=Visibility.UNLISTED,
            updated_at=datetime(2026, 7, 22, tzinfo=UTC),
        )
        percent_tool = Software(
            name="100% Tool_A",
            slug="percent-tool",
            short_description="Literal wildcard tester",
            category=editors,
            tags=[portable],
            status=SoftwareStatus.PUBLISHED,
            visibility=Visibility.PUBLIC,
            updated_at=datetime(2026, 7, 21, tzinfo=UTC),
        )
        other_tool = Software(
            name="100X ToolBA",
            slug="other-tool",
            short_description="Should not match escaped wildcards",
            category=editors,
            status=SoftwareStatus.PUBLISHED,
            visibility=Visibility.PRIVATE,
            updated_at=datetime(2026, 7, 19, tzinfo=UTC),
        )

        popular_release = Release(
            software=seven_zip,
            version="26.00",
            release_channel=ReleaseChannel.STABLE,
            status=ReleaseStatus.PUBLISHED,
            release_date=date(2026, 7, 20),
        )
        popular_release.files.append(
            ReleaseFile(
                original_filename="7z.exe",
                display_filename="7z.exe",
                storage_filename="popular.exe",
                relative_storage_path="7zip/popular.exe",
                file_extension=".exe",
                detected_mime_type="application/x-dosexec",
                file_size_bytes=100,
                sha256="b" * 64,
                platform="windows",
                status=FileStatus.PUBLISHED,
                visibility=Visibility.PUBLIC,
                download_count=100,
            )
        )
        quiet_release = Release(
            software=percent_tool,
            version="1.0",
            release_channel=ReleaseChannel.STABLE,
            status=ReleaseStatus.PUBLISHED,
            release_date=date(2026, 7, 21),
        )
        quiet_release.files.append(
            ReleaseFile(
                original_filename="tool.zip",
                display_filename="tool.zip",
                storage_filename="quiet.zip",
                relative_storage_path="tool/quiet.zip",
                file_extension=".zip",
                detected_mime_type="application/zip",
                file_size_bytes=50,
                sha256="c" * 64,
                platform="windows",
                status=FileStatus.PUBLISHED,
                visibility=Visibility.PUBLIC,
                download_count=3,
            )
        )
        session.add_all([seven_zip, notepad, percent_tool, other_tool])
        session.flush()
        return {
            "seven_zip": seven_zip.id,
            "notepad": notepad.id,
            "percent": percent_tool.id,
            "other": other_tool.id,
            "archivers": archivers.id,
            "utility": utility.id,
        }


def test_base_crud_count_and_category_ordering(domain_database: Database) -> None:
    with domain_database.transaction() as session:
        repository = CategoryRepository(session)
        second = repository.add(Category(name="Second", slug="second", sort_order=2))
        first = repository.add(Category(name="First", slug="first", sort_order=1))
        hidden = repository.add(
            Category(name="Hidden", slug="hidden", sort_order=0, is_visible=False)
        )
        assert repository.count() == 3
        assert repository.get(first.id) is first
        repository.delete(second)
        assert repository.count() == 2
        assert repository.get_by_slug(" FIRST ") is first

    with domain_database.session() as session:
        repository = CategoryRepository(session)
        page = repository.list_page(Pagination(per_page=10), visible_only=True)
        assert [category.slug for category in page.items] == ["first"]
        assert repository.get(hidden.id) is not None


def test_tag_lookup_many_and_pagination(domain_database: Database) -> None:
    with domain_database.transaction() as session:
        repository = TagRepository(session)
        beta = repository.add(Tag(name="Beta", slug="beta"))
        alpha = repository.add(Tag(name="Alpha", slug="alpha"))
        assert repository.get_by_slug(" ALPHA ") is alpha
        assert repository.get_many([]) == []
        assert repository.get_many([beta.id, alpha.id, beta.id]) == [beta, alpha]

    with domain_database.session() as session:
        page = TagRepository(session).list_page(Pagination(page=1, per_page=1))
        assert [tag.slug for tag in page.items] == ["alpha"]
        assert page.total == 2
        assert page.has_next is True


def test_user_and_session_repositories(domain_database: Database) -> None:
    now = utc_now()
    with domain_database.transaction() as session:
        user = UserRepository(session).add(make_user(username="Admin"))
        active = make_session(user, token_hash="a" * 64)
        SessionRepository(session).add(active)
        expired = make_session(user, token_hash="b" * 64)
        expired.expires_at = now - timedelta(seconds=1)
        SessionRepository(session).add(expired)

    with domain_database.transaction() as session:
        users = UserRepository(session)
        sessions = SessionRepository(session)
        assert users.get_by_username(" admin ") is not None
        loaded = sessions.get_by_token_hash("a" * 64)
        assert loaded is not None
        assert loaded.user.username == "Admin"
        assert sessions.delete_expired(now) == 1

    with domain_database.session() as session:
        assert SessionRepository(session).count() == 1


def test_software_search_filters_sorting_and_escaped_wildcards(
    domain_database: Database,
) -> None:
    ids = seed_search_catalog(domain_database)

    with domain_database.session() as session:
        repository = SoftwareRepository(session)
        assert repository.get_with_graph(ids["seven_zip"]) is not None
        assert repository.get_by_slug(" 7-ZIP ") is not None

        by_developer = repository.list_page(
            Pagination(),
            SoftwareFilters(query="  Igor   Pavlov  "),
        )
        assert [software.slug for software in by_developer.items] == ["7-zip"]

        by_category = repository.list_page(
            Pagination(),
            SoftwareFilters(query="Archivers"),
        )
        assert [software.slug for software in by_category.items] == ["7-zip"]

        by_tag = repository.list_page(
            Pagination(),
            SoftwareFilters(tag_slugs=("portable",), sort=SoftwareSort.NAME),
        )
        assert [software.slug for software in by_tag.items] == [
            "percent-tool",
            "notepad-plus",
        ]

        literal_wildcards = repository.list_page(
            Pagination(),
            SoftwareFilters(query="100% Tool_A"),
        )
        assert [software.slug for software in literal_wildcards.items] == ["percent-tool"]

        injection_attempt = repository.list_page(
            Pagination(),
            SoftwareFilters(query="x' OR 1=1 --"),
        )
        assert injection_attempt.total == 0

        filtered = repository.list_page(
            Pagination(),
            SoftwareFilters(
                category_slug="editors",
                statuses=(SoftwareStatus.PUBLISHED,),
                visibilities=(Visibility.PUBLIC,),
                sort=SoftwareSort.UPDATED,
            ),
        )
        assert [software.slug for software in filtered.items] == ["percent-tool"]

        popular = repository.list_page(
            Pagination(),
            SoftwareFilters(sort=SoftwareSort.POPULARITY),
        )
        assert popular.items[0].slug == "7-zip"


def test_software_pagination_and_eager_loading_do_not_add_n_plus_one_queries(
    domain_database: Database,
) -> None:
    seed_search_catalog(domain_database)
    statements: list[str] = []

    def record_statement(
        _connection: object,
        _cursor: object,
        statement: str,
        _parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        statements.append(statement)

    event.listen(domain_database.engine, "before_cursor_execute", record_statement)
    try:
        with domain_database.session() as session:
            page = SoftwareRepository(session).list_page(
                Pagination(page=2, per_page=2),
                SoftwareFilters(sort=SoftwareSort.NAME),
            )
            count_after_query = len(statements)
            for software in page.items:
                _ = software.category
                _ = list(software.tags)
                for release in software.releases:
                    _ = list(release.files)
            assert len(statements) == count_after_query
            assert page.total == 4
            assert len(page.items) == 2
    finally:
        event.remove(domain_database.engine, "before_cursor_execute", record_statement)


def test_release_repository_current_and_ordered_listing(domain_database: Database) -> None:
    with domain_database.transaction() as session:
        software = Software(
            name="Tool",
            slug="tool",
            short_description="Tool",
            status=SoftwareStatus.PUBLISHED,
            visibility=Visibility.PUBLIC,
        )
        older = Release(
            software=software,
            version="1.0",
            release_channel=ReleaseChannel.STABLE,
            release_date=date(2026, 1, 1),
            status=ReleaseStatus.PUBLISHED,
            is_current=True,
        )
        newer = Release(
            software=software,
            version="2.0",
            release_channel=ReleaseChannel.STABLE,
            release_date=date(2026, 2, 1),
            status=ReleaseStatus.PUBLISHED,
        )
        session.add(software)
        session.flush()
        software_id = software.id
        newer_id = newer.id
        repository = ReleaseRepository(session)
        assert repository.get_with_graph(older.id, for_update=True) is not None
        assert repository.get_current_stable(software_id) is older
        assert repository.clear_current_stable(software_id, except_release_id=newer_id) == 1
        newer.is_current = True
        session.flush()

    with domain_database.session() as session:
        repository = ReleaseRepository(session)
        current = repository.get_current_stable(software_id)
        assert current is not None
        assert current.version == "2.0"
        page = repository.list_for_software(software_id, Pagination())
        assert [release.version for release in page.items] == ["2.0", "1.0"]


def test_release_file_download_stat_and_audit_repositories(domain_database: Database) -> None:
    with domain_database.transaction() as session:
        release_file = make_catalog_graph(session)
        duplicate = ReleaseFile(
            release=release_file.release,
            original_filename="copy.exe",
            display_filename="copy.exe",
            storage_filename="copy.exe",
            relative_storage_path="7-zip/26/copy.exe",
            file_extension=".exe",
            detected_mime_type="application/x-dosexec",
            file_size_bytes=10,
            sha256=release_file.sha256,
            platform="windows",
        )
        session.add(duplicate)
        audit = AuditLog(
            action="software_created",
            entity_type="software",
            entity_id=str(release_file.release.software.id),
            result="success",
            safe_metadata={"slug": "7-zip"},
        )
        session.add(audit)
        session.flush()
        file_id = release_file.id
        duplicate_id = duplicate.id
        public_uuid = release_file.public_uuid
        stat_day = release_file.download_stats[0].date

    with domain_database.session() as session:
        files = ReleaseFileRepository(session)
        loaded = files.get_with_graph(file_id, for_update=True)
        assert loaded is not None
        assert loaded.release.software.slug == "7-zip"
        public_file = files.get_by_public_uuid(public_uuid)
        assert public_file is not None
        assert public_file.id == file_id
        assert [item.id for item in files.find_by_sha256("A" * 64)] == [
            file_id,
            duplicate_id,
        ]
        assert [item.id for item in files.find_by_sha256("a" * 64, exclude_file_id=file_id)] == [
            duplicate_id
        ]
        assert files.list_for_release(loaded.release_id, Pagination()).total == 2

        stats = DownloadStatRepository(session)
        assert stats.get_for_date(file_id, stat_day) is not None
        assert stats.list_for_file(file_id, Pagination()).total == 1

        audits = AuditRepository(session)
        page = audits.list_page(
            Pagination(),
            action="software_created",
            entity_type="software",
        )
        assert page.total == 1
        assert page.items[0].safe_metadata == {"slug": "7-zip"}
        assert audits.list_page(Pagination(), user_id=999).total == 0
