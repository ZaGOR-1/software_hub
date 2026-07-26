"""FastAPI application factory and ASGI entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from app.core.config import AppSettings, get_settings
from app.core.error_handlers import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import install_middleware
from app.database.session import create_database
from app.routers.admin.audit import router as admin_audit_router
from app.routers.admin.categories import router as admin_categories_router
from app.routers.admin.dashboard import router as admin_dashboard_router
from app.routers.admin.files import router as admin_files_router
from app.routers.admin.releases import router as admin_releases_router
from app.routers.admin.software import router as admin_software_router
from app.routers.admin.tags import router as admin_tags_router
from app.routers.auth.login import router as auth_router
from app.routers.health.health import router as health_router
from app.routers.public.catalog import router as public_catalog_router
from app.routers.public.downloads import router as public_downloads_router
from app.storage.manager import StorageManager
from app.storage.scanner import create_file_scanner


def create_app(settings: AppSettings | None = None) -> FastAPI:
    """Create a fully configured FastAPI application instance."""

    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)
    database = create_database(resolved_settings)
    storage = StorageManager.from_settings(resolved_settings)
    file_scanner = create_file_scanner(resolved_settings)

    @asynccontextmanager
    async def lifespan(_application: FastAPI) -> AsyncIterator[None]:
        try:
            storage.initialize()
            yield
        finally:
            database.dispose()

    docs_url = "/docs" if resolved_settings.docs_enabled else None
    redoc_url = "/redoc" if resolved_settings.docs_enabled else None
    openapi_url = "/openapi.json" if resolved_settings.docs_enabled else None

    application = FastAPI(
        title=resolved_settings.app_name,
        version=resolved_settings.app_version,
        debug=False,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
        lifespan=lifespan,
    )
    application.state.settings = resolved_settings
    application.state.database = database
    application.state.storage = storage
    application.state.file_scanner = file_scanner

    static_directory = Path(__file__).resolve().parent / "static"
    application.mount("/static", StaticFiles(directory=static_directory), name="static")

    register_exception_handlers(application)
    application.include_router(health_router, prefix=resolved_settings.health_path)
    application.include_router(public_catalog_router)
    application.include_router(public_downloads_router)
    application.include_router(auth_router)
    application.include_router(admin_dashboard_router)
    application.include_router(admin_audit_router)
    application.include_router(admin_categories_router)
    application.include_router(admin_tags_router)
    application.include_router(admin_software_router)
    application.include_router(admin_releases_router)
    application.include_router(admin_files_router)
    install_middleware(application, resolved_settings)
    return application


app = create_app()
