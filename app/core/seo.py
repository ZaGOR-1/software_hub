"""Public page metadata and trusted absolute URL construction."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlencode


@dataclass(frozen=True, slots=True)
class PageMetadata:
    """SEO-safe metadata passed to public Jinja templates."""

    title: str
    description: str
    canonical_url: str
    robots: str
    open_graph_type: str
    site_name: str
    locale: str = "uk_UA"


def public_url(
    base_url: object,
    path: str,
    query: Iterable[tuple[str, str]] = (),
) -> str:
    """Build an absolute URL from trusted configuration rather than request Host."""

    normalized_path = f"/{path.lstrip('/')}"
    if path == "":
        normalized_path = "/"
    base = str(base_url).rstrip("/")
    encoded_query = urlencode(tuple(query), doseq=True)
    if encoded_query:
        return f"{base}{normalized_path}?{encoded_query}"
    return f"{base}{normalized_path}"


def page_metadata(
    *,
    base_url: object,
    path: str,
    title: str,
    description: str,
    site_name: str,
    robots: str = "index, follow",
    open_graph_type: str = "website",
    query: Iterable[tuple[str, str]] = (),
) -> PageMetadata:
    """Create one immutable metadata object for a public page."""

    return PageMetadata(
        title=title,
        description=description,
        canonical_url=public_url(base_url, path, query),
        robots=robots,
        open_graph_type=open_graph_type,
        site_name=site_name,
    )
