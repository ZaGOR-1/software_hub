"""Trusted SEO metadata helpers introduced in Phase 14."""

from app.core.seo import page_metadata, public_url


def test_public_url_uses_configured_base_and_encodes_query() -> None:
    assert public_url(
        "https://software.hotzagor.tech/",
        "/software",
        (("page", "2"), ("q", "архіватор 100%")),
    ) == (
        "https://software.hotzagor.tech/software?"
        "page=2&q=%D0%B0%D1%80%D1%85%D1%96%D0%B2%D0%B0%D1%82%D0%BE%D1%80+100%25"
    )
    assert public_url("https://software.hotzagor.tech", "") == ("https://software.hotzagor.tech/")


def test_page_metadata_is_immutable_public_context() -> None:
    metadata = page_metadata(
        base_url="https://software.hotzagor.tech",
        path="/software/7-zip",
        title="7-Zip — Software Hub",
        description="Архіватор",
        site_name="Software Hub",
        robots="index, follow",
        open_graph_type="article",
    )

    assert metadata.canonical_url == "https://software.hotzagor.tech/software/7-zip"
    assert metadata.open_graph_type == "article"
    assert metadata.locale == "uk_UA"
