"""Ensure every state-changing HTTP route declares an approved CSRF dependency."""

from collections.abc import Iterable, Iterator

from fastapi import APIRouter, FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_APPROVED_CSRF_DEPENDENCIES = frozenset(
    {"require_login_csrf", "require_session_csrf", "require_upload_session_csrf"}
)


def _dependency_names(dependant: Dependant) -> Iterator[str]:
    for dependency in dependant.dependencies:
        name = getattr(dependency.call, "__name__", "")
        if name:
            yield name
        yield from _dependency_names(dependency)


def _api_routes(routes: Iterable[object]) -> Iterator[APIRoute]:
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
            continue
        original_router = getattr(route, "original_router", None)
        if isinstance(original_router, APIRouter):
            yield from _api_routes(original_router.routes)


def test_every_state_changing_route_has_csrf_dependency(application: FastAPI) -> None:
    protected_routes: list[str] = []
    for route in _api_routes(application.routes):
        if not (_UNSAFE_METHODS & (route.methods or set())):
            continue

        dependency_names = set(_dependency_names(route.dependant))
        assert dependency_names & _APPROVED_CSRF_DEPENDENCIES, (
            f"State-changing route {route.path} lacks an approved CSRF dependency."
        )
        protected_routes.append(route.path)

    assert sorted(protected_routes) == sorted(
        [
            "/admin/files/{file_id}/archive",
            "/admin/files/{file_id}/delete-metadata",
            "/admin/files/{file_id}/delete-permanently",
            "/admin/files/{file_id}/disable",
            "/admin/files/{file_id}/publish",
            "/admin/files/{file_id}/restore",
            "/admin/files/{file_id}/review/approve",
            "/admin/files/{file_id}/review/reject",
            "/admin/files/{file_id}/review/reopen",
            "/admin/files/{file_id}/verify",
            "/admin/login",
            "/admin/logout",
            "/admin/categories",
            "/admin/categories/{category_id}/edit",
            "/admin/categories/{category_id}/delete",
            "/admin/tags",
            "/admin/tags/{tag_id}/edit",
            "/admin/tags/{tag_id}/delete",
            "/admin/software",
            "/admin/software/{software_id}/edit",
            "/admin/software/{software_id}/publish",
            "/admin/software/{software_id}/hide",
            "/admin/software/{software_id}/archive",
            "/admin/software/{software_id}/disable",
            "/admin/software/{software_id}/restore",
            "/admin/software/{software_id}/releases",
            "/admin/releases/{release_id}/edit",
            "/admin/releases/{release_id}/publish",
            "/admin/releases/{release_id}/archive",
            "/admin/releases/{release_id}/disable",
            "/admin/releases/{release_id}/restore",
            "/admin/releases/{release_id}/current",
            "/admin/releases/{release_id}/current/clear",
            "/admin/releases/{release_id}/files",
        ]
    )
