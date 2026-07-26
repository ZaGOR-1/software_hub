"""Shared helpers for public server-rendered pages."""

from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import Response
from starlette.templating import Jinja2Templates

from app.core.seo import page_metadata
from app.routers.auth.dependencies import OptionalAdminSession

TEMPLATES = Jinja2Templates(directory=Path(__file__).resolve().parents[2] / "templates")


def render_public(  # noqa: PLR0913
    request: Request,
    template_name: str,
    *,
    admin_session: OptionalAdminSession,
    status_code: int = 200,
    page_title: str | None = None,
    page_description: str | None = None,
    canonical_path: str | None = None,
    canonical_query: tuple[tuple[str, str], ...] = (),
    page_robots: str = "index, follow",
    open_graph_type: str = "website",
    **context: Any,
) -> Response:
    """Render one public page with shared navigation and trusted metadata."""

    settings = request.app.state.settings
    title = page_title or settings.app_name
    description = page_description or ("Каталог перевірених програм та інсталяційних файлів.")
    metadata = page_metadata(
        base_url=settings.public_base_url,
        path=canonical_path or request.url.path,
        query=canonical_query,
        title=title,
        description=description,
        site_name=settings.app_name,
        robots=page_robots,
        open_graph_type=open_graph_type,
    )
    payload: dict[str, Any] = {
        "request": request,
        "app_name": settings.app_name,
        "seo": metadata,
        "admin_session": admin_session,
        "current_path": request.url.path,
    }
    payload.update(context)
    return TEMPLATES.TemplateResponse(
        request=request,
        name=template_name,
        context=payload,
        status_code=status_code,
    )


def public_page_number(raw_value: str | None) -> int:
    """Parse a bounded one-based public page number."""

    if raw_value is None:
        return 1
    try:
        value = int(raw_value)
    except ValueError:
        return 1
    return min(max(value, 1), 100_000)
