"""Fixtures for production-like Playwright tests using Uvicorn and Nginx."""

from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright
from pluggy import Result

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ADMIN_USERNAME = "e2e-admin"
_ADMIN_PASSWORD = "E2e-Admin-Password-2026!"


@dataclass(frozen=True, slots=True)
class E2EStack:
    """Addresses and filesystem paths for one isolated end-to-end stack."""

    base_url: str
    app_url: str
    root: Path
    upload_file: Path
    username: str = _ADMIN_USERNAME
    password: str = _ADMIN_PASSWORD


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_url(url: str, process: subprocess.Popen[str], *, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    last_error = "not started"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate(timeout=5)
            raise RuntimeError(
                f"Process exited while waiting for {url}. stdout={stdout!r} stderr={stderr!r}"
            )
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:  # noqa: S310
                if response.status < 500:
                    return
        except (OSError, urllib.error.URLError) as exc:
            last_error = str(exc)
        time.sleep(0.15)
    raise TimeoutError(f"Timed out waiting for {url}: {last_error}")


def _terminate(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _write_nginx_config(path: Path, *, app_port: int, public_port: int, storage: Path) -> None:
    mime_types = Path("/etc/nginx/mime.types")
    include_mime = f"include {mime_types};" if mime_types.exists() else ""
    path.write_text(
        f"""
worker_processes 1;
pid {path.parent / "nginx.pid"};
error_log {path.parent / "nginx-error.log"} info;
events {{ worker_connections 256; }}
http {{
    {include_mime}
    access_log {path.parent / "nginx-access.log"};
    client_max_body_size 16m;
    server_tokens off;
    server {{
        listen 127.0.0.1:{public_port};
        server_name 127.0.0.1 localhost;

        location ^~ /static/ {{
            alias {_PROJECT_ROOT / "app/static"}/;
            autoindex off;
        }}

        location ^~ /protected-downloads/ {{
            internal;
            alias {storage / "software"}/;
            autoindex off;
            disable_symlinks on;
        }}

        location / {{
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Request-ID $request_id;
            proxy_pass http://127.0.0.1:{app_port};
        }}
    }}
}}
""".strip()
        + "\n",
        encoding="utf-8",
    )


def _stack_environment(root: Path, *, public_port: int) -> dict[str, str]:
    storage = root / "storage"
    database = root / "database" / "software-hub.db"
    return {
        **os.environ,
        "PYTHONPATH": str(_PROJECT_ROOT),
        "SOFTWARE_HUB_APP_ENVIRONMENT": "test",
        "SOFTWARE_HUB_APP_DEBUG": "false",
        "SOFTWARE_HUB_DOCS_ENABLED": "false",
        "SOFTWARE_HUB_APP_SECRET_KEY": "phase18-e2e-app-secret-1234567890-ABCDEFG",
        "SOFTWARE_HUB_CSRF_SECRET": "phase18-e2e-csrf-secret-123456789-ABCDEFG",
        "SOFTWARE_HUB_DATABASE_URL": f"sqlite+pysqlite:///{database}",
        "SOFTWARE_HUB_PUBLIC_BASE_URL": f"http://127.0.0.1:{public_port}",
        "SOFTWARE_HUB_TRUSTED_HOSTS": "127.0.0.1,localhost",
        "SOFTWARE_HUB_TRUSTED_PROXY_NETWORKS": "127.0.0.1/32",
        "SOFTWARE_HUB_STORAGE_ROOT": str(storage),
        "SOFTWARE_HUB_TEMPORARY_ROOT": str(storage / "temporary"),
        "SOFTWARE_HUB_QUARANTINE_ROOT": str(storage / "quarantine"),
        "SOFTWARE_HUB_ICONS_ROOT": str(storage / "icons"),
        "SOFTWARE_HUB_BACKUP_ROOT": str(root / "backups"),
        "SOFTWARE_HUB_STORAGE_MIN_FREE_BYTES": "0",
        "SOFTWARE_HUB_BACKUP_MIN_FREE_BYTES": "0",
        "SOFTWARE_HUB_MAX_UPLOAD_SIZE": str(16 * 1024 * 1024),
        "SOFTWARE_HUB_ARGON2_TIME_COST": "1",
        "SOFTWARE_HUB_ARGON2_MEMORY_COST_KIB": "1024",
        "SOFTWARE_HUB_ARGON2_PARALLELISM": "1",
        "SOFTWARE_HUB_SECURITY_HEADERS_ENABLED": "true",
        "SOFTWARE_HUB_LOG_JSON": "false",
        "SOFTWARE_HUB_LOG_LEVEL": "WARNING",
        "SOFTWARE_HUB_CLAMAV_ENABLED": "false",
        "SOFTWARE_HUB_ADMIN_PASSWORD": _ADMIN_PASSWORD,
    }


def _prepare_runtime(root: Path) -> Path:
    storage = root / "storage"
    for directory in (
        root / "database",
        root / "backups",
        storage / "software",
        storage / "icons",
        storage / "import",
        storage / "temporary",
        storage / "quarantine",
    ):
        directory.mkdir(parents=True, exist_ok=True)
    upload_file = root / "e2e-tool.zip"
    with zipfile.ZipFile(upload_file, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", "Software Hub Phase 18 E2E payload\n")
    return upload_file


@pytest.fixture(scope="session")
def e2e_stack(tmp_path_factory: pytest.TempPathFactory) -> Generator[E2EStack]:
    """Run an isolated Uvicorn app behind a real Nginx internal-download proxy."""

    if os.getenv("SOFTWARE_HUB_RUN_E2E") != "1":
        pytest.skip("Set SOFTWARE_HUB_RUN_E2E=1 to run Playwright end-to-end tests.")
    if shutil.which("nginx") is None:
        pytest.skip("Nginx is required for protected download E2E tests.")

    root = tmp_path_factory.mktemp("phase18-e2e")
    upload_file = _prepare_runtime(root)
    app_port = _free_port()
    public_port = _free_port()
    env = _stack_environment(root, public_port=public_port)

    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_PROJECT_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "app.cli",
            "create-admin",
            "--username",
            _ADMIN_USERNAME,
        ],
        cwd=_PROJECT_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    app_stdout = (root / "app-stdout.log").open("w", encoding="utf-8")
    app_stderr = (root / "app-stderr.log").open("w", encoding="utf-8")
    app_process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(app_port),
            "--workers",
            "1",
            "--no-access-log",
        ],
        cwd=_PROJECT_ROOT,
        env=env,
        stdout=app_stdout,
        stderr=app_stderr,
        text=True,
    )
    _wait_for_url(f"http://127.0.0.1:{app_port}/health", app_process)

    nginx_conf = root / "nginx.conf"
    _write_nginx_config(
        nginx_conf,
        app_port=app_port,
        public_port=public_port,
        storage=root / "storage",
    )
    nginx_stdout = (root / "nginx-stdout.log").open("w", encoding="utf-8")
    nginx_stderr = (root / "nginx-stderr.log").open("w", encoding="utf-8")
    nginx_process = subprocess.Popen(
        ["nginx", "-c", str(nginx_conf), "-p", str(root), "-g", "daemon off;"],
        cwd=_PROJECT_ROOT,
        stdout=nginx_stdout,
        stderr=nginx_stderr,
        text=True,
    )
    base_url = f"http://127.0.0.1:{public_port}"
    _wait_for_url(f"{base_url}/health", nginx_process)

    try:
        yield E2EStack(
            base_url=base_url,
            app_url=f"http://127.0.0.1:{app_port}",
            root=root,
            upload_file=upload_file,
        )
    finally:
        _terminate(nginx_process)
        _terminate(app_process)
        nginx_stdout.close()
        nginx_stderr.close()
        app_stdout.close()
        app_stderr.close()


def _requested_browsers() -> tuple[str, ...]:
    raw = os.getenv("SOFTWARE_HUB_E2E_BROWSERS", "chromium")
    browsers = tuple(item.strip() for item in raw.split(",") if item.strip())
    unknown = set(browsers) - {"chromium", "firefox", "webkit"}
    if unknown:
        raise ValueError(f"Unknown Playwright browsers: {sorted(unknown)}")
    return browsers


@pytest.fixture(scope="session")
def playwright_runtime() -> Generator[Playwright]:
    with sync_playwright() as runtime:
        yield runtime


@pytest.fixture
def browser_name(request: pytest.FixtureRequest) -> str:
    return str(getattr(request, "param", "chromium"))


@pytest.fixture
def browser(
    playwright_runtime: Playwright,
    browser_name: str,
) -> Generator[Browser]:
    if browser_name not in _requested_browsers():
        pytest.skip(f"{browser_name} is not enabled by SOFTWARE_HUB_E2E_BROWSERS.")
    browser_type = getattr(playwright_runtime, browser_name)
    launch_options: dict[str, object] = {"headless": True}
    if browser_name == "chromium":
        executable = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE")
        if executable:
            launch_options["executable_path"] = executable
            launch_options["args"] = ["--no-sandbox", "--disable-dev-shm-usage"]
    instance = browser_type.launch(**launch_options)
    try:
        yield instance
    finally:
        instance.close()


@pytest.fixture
def browser_context(
    browser: Browser,
    tmp_path: Path,
) -> Generator[BrowserContext]:
    context = browser.new_context(
        accept_downloads=True,
        locale="uk-UA",
        record_video_dir=str(tmp_path / "video")
        if os.getenv("SOFTWARE_HUB_E2E_VIDEO") == "1"
        else None,
    )
    try:
        yield context
    finally:
        context.close()


@pytest.fixture
def page(
    browser_context: BrowserContext,
    request: pytest.FixtureRequest,
) -> Generator[Page]:
    current_page = browser_context.new_page()
    current_page.set_default_timeout(10_000)
    yield current_page
    report = getattr(request.node, "rep_call", None)
    if report is not None and report.failed:
        artifact_root = _PROJECT_ROOT / "tests" / "artifacts" / "e2e"
        artifact_root.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", request.node.nodeid)
        current_page.screenshot(path=str(artifact_root / f"{safe_name}.png"), full_page=True)
    current_page.close()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item,
) -> Generator[None, Result[pytest.TestReport]]:
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)
