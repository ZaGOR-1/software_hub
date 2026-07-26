"""Static acceptance tests for the Phase 17 container deployment."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def _yaml(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], yaml.safe_load((ROOT / name).read_text(encoding="utf-8")))


def test_application_dockerfile_is_multistage_and_non_root() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "python:3.14.6-slim-bookworm" in dockerfile
    assert " AS dependency-builder" in dockerfile
    assert " AS runtime" in dockerfile
    assert "uv export" in dockerfile
    assert "--require-hashes" in dockerfile
    assert "USER softwarehub:softwarehub" in dockerfile
    assert "COPY . ." not in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert '--workers", "1' in dockerfile


def test_nginx_image_is_non_root_and_contains_static_assets() -> None:
    dockerfile = (ROOT / "nginx/Dockerfile").read_text(encoding="utf-8")

    assert "nginx:1.30.4-alpine3.24" in dockerfile
    assert "COPY app/static /usr/share/nginx/html/static" in dockerfile
    assert "USER softwarehub:softwarehub" in dockerfile
    assert "EXPOSE 8080 8443" in dockerfile
    assert "HEALTHCHECK" in dockerfile


def test_compose_services_have_container_hardening() -> None:
    compose = _yaml("docker-compose.yml")
    services = compose["services"]

    assert set(services) == {"app", "nginx"}
    assert compose["networks"]["backend"]["internal"] is True
    assert "ports" not in services["app"]

    for service in services.values():
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
        assert "no-new-privileges:true" in service["security_opt"]
        assert service["init"] is True
        assert service["user"] != "0:0"
        assert all("noexec" in mount for mount in service["tmpfs"])
        assert "privileged" not in service
        assert service.get("network_mode") != "host"
        assert "/var/run/docker.sock" not in str(service.get("volumes", []))


def test_compose_mounts_atomic_application_root_without_tls_secrets() -> None:
    compose = _yaml("docker-compose.yml")
    app_volumes = compose["services"]["app"]["volumes"]
    nginx_volumes = compose["services"]["nginx"]["volumes"]

    assert app_volumes == [
        {
            "type": "bind",
            "source": "${SOFTWARE_HUB_DATA_ROOT:-./.runtime}/application",
            "target": "/srv/software-hub",
        }
    ]
    assert "letsencrypt" not in str(app_volumes)
    assert "certbot" not in str(app_volumes)

    nginx_targets = {volume["target"]: volume for volume in nginx_volumes}
    assert nginx_targets["/srv/software-hub/storage/software"]["read_only"] is True
    assert nginx_targets["/srv/software-hub/storage/software"]["source"].endswith(
        "/application/storage/software"
    )
    assert nginx_targets["/var/www/certbot"]["read_only"] is True
    assert (
        nginx_targets["/etc/software-hub/nginx/snippets/admin-access-runtime.conf"]["read_only"]
        is True
    )


def test_proxy_trust_matches_fixed_internal_nginx_address() -> None:
    compose = _yaml("docker-compose.yml")
    app = compose["services"]["app"]
    nginx = compose["services"]["nginx"]

    assert app["environment"]["SOFTWARE_HUB_FORWARDED_ALLOW_IPS"] == (
        "${SOFTWARE_HUB_NGINX_IP:-172.30.0.10}"
    )
    assert app["environment"]["SOFTWARE_HUB_TRUSTED_PROXY_NETWORKS"].endswith("/32")
    assert nginx["networks"]["backend"]["ipv4_address"] == ("${SOFTWARE_HUB_NGINX_IP:-172.30.0.10}")


def test_production_override_enables_tls_and_optional_certbot() -> None:
    production = _yaml("docker-compose.production.yml")
    services = production["services"]

    assert services["app"]["environment"]["SOFTWARE_HUB_APP_ENVIRONMENT"] == ("production")
    assert services["nginx"]["environment"]["SOFTWARE_HUB_NGINX_MODE"] == ("production")
    assert any("8443" in port for port in services["nginx"]["ports"])
    tls_volume = next(
        volume for volume in services["nginx"]["volumes"] if volume["target"] == "/etc/letsencrypt"
    )
    assert tls_volume["read_only"] is True
    assert services["certbot"]["profiles"] == ["certbot"]
    assert services["certbot"]["read_only"] is True
    assert services["certbot"]["cap_drop"] == ["ALL"]


def test_nginx_templates_enforce_security_boundaries() -> None:
    development = (ROOT / "nginx/templates/development.conf.template").read_text(encoding="utf-8")
    production = (ROOT / "nginx/templates/production.conf.template").read_text(encoding="utf-8")
    nginx_http = (ROOT / "nginx/nginx.conf").read_text(encoding="utf-8")

    for config in (development, production):
        assert "internal;" in config
        assert "alias /srv/software-hub/storage/software/;" in config
        assert "storage/quarantine" not in config
        assert "client_max_body_size 2g;" in config
        assert "client_max_body_size 64k;" in config
        assert "client_max_body_size 1m;" in config
        assert "proxy_request_buffering off;" in config
        assert "admin-access-runtime.conf" not in config
        assert "${SOFTWARE_HUB_ADMIN_ACCESS_FILE}" in config
        assert "location ^~ /static/" in config
        assert "location = /admin {" in config
        assert "limit_req zone=login_requests" in config
        assert "limit_req zone=download_requests" in config
        assert "disable_symlinks on;" in config

    assert "listen 8443 ssl" in production
    assert "http2 on;" in production
    assert "ssl_protocols TLSv1.2 TLSv1.3" in production
    assert "Strict-Transport-Security" in production
    assert "return 308 https://${SOFTWARE_HUB_DOMAIN}$request_uri" in production
    assert "server_tokens off;" in nginx_http
    assert "client_body_temp_path /tmp/nginx/client_temp;" in nginx_http


def test_entrypoints_refuse_root_and_validate_configuration() -> None:
    app_entrypoint = (ROOT / "docker/app-entrypoint.sh").read_text(encoding="utf-8")
    nginx_entrypoint = (ROOT / "docker/nginx-entrypoint.sh").read_text(encoding="utf-8")

    assert "refusing to run the application as root" in app_entrypoint
    assert "python -m alembic upgrade head" in app_entrypoint
    assert "--forwarded-allow-ips" in app_entrypoint
    assert "refusing to run as root" in nginx_entrypoint
    assert "nginx -t" in nginx_entrypoint
    assert "TLS certificate or private key is unreadable" in nginx_entrypoint
    assert "envsubst" in nginx_entrypoint


def test_shell_scripts_are_syntactically_valid() -> None:
    if shutil.which("sh") is None:
        pytest.skip("POSIX shell validation requires sh")
    scripts = sorted((ROOT / "docker").glob("*.sh")) + sorted((ROOT / "scripts").glob("*.sh"))
    completed = subprocess.run(
        ["sh", "-n", *(str(script) for script in scripts)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_production_example_is_fail_closed_for_admin_access() -> None:
    example = (ROOT / ".env.production.example").read_text(encoding="utf-8")
    deny_policy = (ROOT / "nginx/snippets/admin-access-deny.conf").read_text(encoding="utf-8")

    assert "SOFTWARE_HUB_ADMIN_ACCESS_CONF=./nginx/snippets/admin-access-deny.conf" in (example)
    assert "SOFTWARE_HUB_PUBLIC_BASE_URL=https://software.hotzagor.tech" in example
    assert "deny all;" in deny_policy
    assert "replace-with-a-generated-secret" in example


def test_nginx_healthcheck_uses_get_not_head() -> None:
    script = (ROOT / "docker/nginx-healthcheck.sh").read_text(encoding="utf-8")
    assert "--output-document=/dev/null" in script
    assert "--spider" not in script


def test_healthcheck_requires_all_component_states(monkeypatch: Any) -> None:
    import importlib.util
    from types import SimpleNamespace

    script = ROOT / "docker/healthcheck.py"
    spec = importlib.util.spec_from_file_location("software_hub_healthcheck", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class FakeResponse:
        status = 200

        @staticmethod
        def read() -> bytes:
            return (
                b'{"status":"ok","checks":{"application":"ok",'
                b'"database":"ok","storage":"ok","disk":"ok"}}'
            )

    class FakeConnection:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.request_data: tuple[object, ...] | None = None

        def request(self, *args: object, **_kwargs: object) -> None:
            self.request_data = args

        @staticmethod
        def getresponse() -> FakeResponse:
            return FakeResponse()

        @staticmethod
        def close() -> None:
            return None

    monkeypatch.setattr(module, "HTTPConnection", FakeConnection)
    monkeypatch.setattr(module, "os", SimpleNamespace(environ={}))
    assert module.main() == 0
