"""Public home, catalog, search, category and software detail routes."""

from datetime import datetime

# Safe output encoding only; no XML parser is constructed.
from xml.sax.saxutils import escape  # nosec B406

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, RedirectResponse, Response

from app.core.exceptions import ValidationError
from app.core.seo import public_url
from app.database.session import DatabaseDependency
from app.models.enums import SoftwareStatus
from app.repositories.software_repository import SoftwareSort
from app.routers.auth.dependencies import OptionalAdminSession
from app.routers.public.common import public_page_number, render_public
from app.schemas.pagination import Pagination
from app.schemas.public_catalog import SoftwareDetailView
from app.services.public_catalog_service import PublicCatalogService

router = APIRouter(tags=["public-catalog"])


_SORT_OPTIONS = (
    (SoftwareSort.UPDATED.value, "Спочатку оновлені"),
    (SoftwareSort.NAME.value, "За назвою"),
    (SoftwareSort.POPULARITY.value, "За популярністю"),
)


def _sort_value(raw_value: str | None) -> SoftwareSort:
    try:
        return SoftwareSort(raw_value or SoftwareSort.UPDATED.value)
    except ValueError as exc:
        raise ValidationError("Невідомий спосіб сортування.") from exc


def _page_query(page: int) -> tuple[tuple[str, str], ...]:
    if page <= 1:
        return ()
    return (("page", str(page)),)


def _catalog_response(  # noqa: PLR0913
    request: Request,
    database: DatabaseDependency,
    admin_session: OptionalAdminSession,
    *,
    query: str | None = None,
    category_slug: str | None = None,
    tag_slug: str | None = None,
    heading: str = "Каталог програм",
    description: str | None = None,
    canonical_path: str = "/software",
    indexable: bool = True,
) -> Response:
    view = PublicCatalogService(database).catalog(
        pagination=Pagination(
            page=public_page_number(request.query_params.get("page")),
            per_page=18,
        ),
        query=query,
        category_slug=category_slug,
        tag_slug=tag_slug,
        sort=_sort_value(request.query_params.get("sort")),
    )
    has_dynamic_filter = bool(view.query or tag_slug or request.query_params.get("category"))
    robots = "index, follow" if indexable and not has_dynamic_filter else "noindex, follow"
    metadata_heading = heading
    metadata_description = description or "Знайдіть потрібну програму та версію."
    if view.category is not None:
        metadata_heading = view.category.name
        metadata_description = view.category.description or metadata_description
    elif view.tag is not None:
        metadata_heading = f"Тег {view.tag.name}"
    return render_public(
        request,
        "public/catalog.html",
        admin_session=admin_session,
        page_title=f"{metadata_heading} — Software Hub",
        page_description=metadata_description,
        canonical_path=canonical_path,
        canonical_query=_page_query(view.page.page) if robots.startswith("index") else (),
        page_robots=robots,
        view=view,
        heading=heading,
        heading_description=description,
        sort_options=_SORT_OPTIONS,
    )


@router.get("/", include_in_schema=False)
def home_page(
    request: Request,
    database: DatabaseDependency,
    admin_session: OptionalAdminSession,
) -> Response:
    """Render the public Software Hub home page."""

    view = PublicCatalogService(database).home()
    return render_public(
        request,
        "public/home.html",
        admin_session=admin_session,
        page_title="Software Hub — каталог програм",
        page_description=(
            "Персональний каталог програм, релізів і перевірених інсталяційних файлів."
        ),
        canonical_path="/",
        view=view,
    )


@router.get("/software", include_in_schema=False)
def software_catalog(
    request: Request,
    database: DatabaseDependency,
    admin_session: OptionalAdminSession,
) -> Response:
    """Render the complete publicly listed software catalog."""

    return _catalog_response(
        request,
        database,
        admin_session,
        query=request.query_params.get("q"),
        category_slug=request.query_params.get("category"),
        tag_slug=request.query_params.get("tag"),
    )


@router.get("/search", include_in_schema=False)
def search_catalog(
    request: Request,
    database: DatabaseDependency,
    admin_session: OptionalAdminSession,
) -> Response:
    """Render public search results without indexing dynamic query pages."""

    query = request.query_params.get("q")
    heading = "Результати пошуку"
    if query and query.strip():
        heading = f"Пошук: {query.strip()}"
    return _catalog_response(
        request,
        database,
        admin_session,
        query=query,
        category_slug=request.query_params.get("category"),
        tag_slug=request.query_params.get("tag"),
        heading=heading,
        canonical_path="/search",
        indexable=False,
    )


@router.get("/category/{category_slug}", include_in_schema=False)
def category_page(
    category_slug: str,
    request: Request,
    database: DatabaseDependency,
    admin_session: OptionalAdminSession,
) -> Response:
    """Render one visible category and its public software entries."""

    return _catalog_response(
        request,
        database,
        admin_session,
        query=request.query_params.get("q"),
        category_slug=category_slug,
        tag_slug=request.query_params.get("tag"),
        heading="Категорія програм",
        canonical_path=f"/category/{category_slug}",
    )


def _software_robots(software: SoftwareDetailView) -> str:
    if software.is_private or software.is_unlisted:
        return "noindex, nofollow"
    if software.is_archived or software.status is not SoftwareStatus.PUBLISHED:
        return "noindex, follow"
    return "index, follow"


@router.get("/software/{software_slug}/releases", include_in_schema=False)
def software_releases_page(
    software_slug: str,
    request: Request,
    database: DatabaseDependency,
    admin_session: OptionalAdminSession,
) -> Response:
    """Render the dedicated public release history for one software entry."""

    software = PublicCatalogService(database).software(
        software_slug,
        is_admin=admin_session is not None,
    )
    return render_public(
        request,
        "public/releases.html",
        admin_session=admin_session,
        page_title=f"Історія версій {software.name} — Software Hub",
        page_description=f"Релізи, зміни та доступні файли для {software.name}.",
        canonical_path=f"/software/{software.slug}/releases",
        page_robots=_software_robots(software),
        software=software,
    )


@router.get("/software/{software_slug}", include_in_schema=False)
def software_detail_page(
    software_slug: str,
    request: Request,
    database: DatabaseDependency,
    admin_session: OptionalAdminSession,
) -> Response:
    """Render one direct software page under its visibility policy."""

    software = PublicCatalogService(database).software(
        software_slug,
        is_admin=admin_session is not None,
    )
    return render_public(
        request,
        "public/software_detail.html",
        admin_session=admin_session,
        page_title=f"{software.name} — Software Hub",
        page_description=software.short_description,
        canonical_path=f"/software/{software.slug}",
        page_robots=_software_robots(software),
        open_graph_type="article",
        software=software,
    )


@router.get("/robots.txt", include_in_schema=False)
def robots_txt(request: Request) -> PlainTextResponse:
    """Prevent indexing of administrative routes and advertise the sitemap."""

    settings = request.app.state.settings
    sitemap_url = public_url(settings.public_base_url, "/sitemap.xml")
    response = PlainTextResponse(
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /protected-downloads\n"
        "Disallow: /internal\n"
        "Disallow: /backups\n"
        f"Sitemap: {sitemap_url}\n"
    )
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@router.get("/sitemap.xml", include_in_schema=False)
def sitemap_xml(request: Request, database: DatabaseDependency) -> Response:
    """Return a bounded XML sitemap containing only indexable public pages."""

    settings = request.app.state.settings
    entries = PublicCatalogService(database).sitemap_entries()
    rows: list[str] = []
    for entry in entries:
        location = escape(public_url(settings.public_base_url, entry.path))
        last_modified = ""
        if entry.last_modified is not None:
            value = entry.last_modified
            date_value = value.date() if isinstance(value, datetime) else value
            last_modified = f"<lastmod>{date_value.isoformat()}</lastmod>"
        rows.append(f"<url><loc>{location}</loc>{last_modified}</url>")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{''.join(rows)}"
        "</urlset>"
    )
    return Response(
        content=xml,
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/favicon.ico", include_in_schema=False)
def favicon() -> RedirectResponse:
    """Redirect legacy favicon requests to the versioned static SVG."""

    return RedirectResponse("/static/icons/favicon.svg", status_code=307)
