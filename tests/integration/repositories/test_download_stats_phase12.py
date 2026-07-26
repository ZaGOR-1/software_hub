"""Atomic aggregate updates for download accounting."""

from datetime import date

from app.database.session import Database
from app.models.release_file import ReleaseFile
from app.repositories.download_stat_repository import DownloadStatRepository
from tests.fixtures.models import make_catalog_graph


def test_download_counters_are_updated_atomically(domain_database: Database) -> None:
    day = date(2026, 7, 24)
    with domain_database.transaction() as session:
        release_file = make_catalog_graph(session, slug="download-counters")
        file_id = release_file.id

    for _ in range(10):
        with domain_database.transaction() as session:
            DownloadStatRepository(session).record_authorized_start(file_id, day)
    for _ in range(4):
        with domain_database.transaction() as session:
            DownloadStatRepository(session).record_blocked(file_id, day)

    with domain_database.session() as session:
        repository = DownloadStatRepository(session)
        stat = repository.get_for_date(file_id, day)
        stored_file = session.get(ReleaseFile, file_id)

    assert stat is not None
    assert stat.download_count == 10
    assert stat.successful_download_count == 10
    assert stat.blocked_download_count == 4
    assert stored_file is not None
    assert stored_file.download_count == 10
