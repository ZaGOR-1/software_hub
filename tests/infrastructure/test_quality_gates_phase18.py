"""Static acceptance tests for Phase 18 CI and E2E quality gates."""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

import yaml

_ROOT = Path(__file__).resolve().parents[2]
_ACTION_USE = re.compile(
    r"^\s*uses:\s*(?P<action>[^@\s]+)@(?P<ref>[^\s#]+)"
    r"(?:\s+#\s+(?P<version>\S+))?\s*$",
    re.MULTILINE,
)


def _workflow(name: str) -> dict[str, object]:
    payload = yaml.safe_load((_ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, object], payload)


def _workflow_text(name: str) -> str:
    return (_ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")


def test_quality_workflow_enforces_all_python_gates() -> None:
    text = _workflow_text("ci.yml")
    for required in (
        "uv lock --check",
        "ruff format --check",
        "ruff check --output-format=github",
        "mypy --junit-xml",
        "pre-commit run --all-files",
        "pytest --junitxml",
        "bandit[toml]==1.9.4",
        "pip-audit==2.10.1",
        "--requirement test-results/quality/requirements.txt",
        "--output test-results/quality/pip-audit.json",
        "uv export --frozen --no-dev",
    ):
        assert required in text
    assert "continue-on-error" not in text


def test_release_verifier_audits_the_frozen_runtime_graph() -> None:
    text = (_ROOT / "scripts" / "verify-release-candidate.sh").read_text(encoding="utf-8")

    assert "uv export --frozen --no-dev" in text
    assert "pip-audit --requirement" in text


def test_e2e_workflow_runs_real_browser_matrix() -> None:
    workflow = _workflow("e2e.yml")
    text = _workflow_text("e2e.yml")
    pyproject = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert workflow["name"] == "Browser E2E"
    assert '"playwright==1.61.0"' in pyproject
    assert "playwright install --with-deps chromium firefox webkit" in text
    assert "uv run --with" not in text
    assert "axe-core@${AXE_CORE_VERSION}" in text
    assert "AXE_CORE_PATH:" in text
    assert "SOFTWARE_HUB_E2E_BROWSERS: chromium,firefox,webkit" in text
    assert 'pytest -o addopts="" -m e2e tests/e2e' in text
    assert "tests/artifacts/e2e" in text


def test_container_workflow_builds_scans_and_smoke_tests_images() -> None:
    workflow = _workflow("container-build.yml")
    text = _workflow_text("container-build.yml")
    assert workflow["name"] == "Container Build and Scan"
    assert (
        text.count("aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25 # v0.36.0")
        == 3
    )
    assert "software-hub-app:ci" in text
    assert "software-hub-nginx:ci" in text
    assert "docker compose up --detach --no-build" in text
    assert "docker compose exec -T app id -u" in text
    assert "docker compose exec -T nginx id -u" in text
    assert ("docker compose exec -T app python /usr/local/bin/software-hub-healthcheck.py") in text
    assert "docker compose down --volumes --remove-orphans" in text


def test_third_party_actions_are_pinned_to_reviewable_commit_shas() -> None:
    mutable: list[str] = []
    missing_version_comments: list[str] = []
    for workflow_path in sorted((_ROOT / ".github" / "workflows").glob("*.yml")):
        text = workflow_path.read_text(encoding="utf-8")
        matches = list(_ACTION_USE.finditer(text))
        assert matches, f"{workflow_path.name} declares no actions"
        for match in matches:
            action = match.group("action")
            if action.startswith("./"):
                continue
            if re.fullmatch(r"[0-9a-f]{40}", match.group("ref")) is None:
                mutable.append(f"{workflow_path.name}: {match.group(0).strip()}")
            if match.group("version") is None:
                missing_version_comments.append(f"{workflow_path.name}: {match.group(0).strip()}")

    assert mutable == []
    assert missing_version_comments == []


def test_dependabot_tracks_reviewed_github_action_updates() -> None:
    text = (_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")

    assert "package-ecosystem: github-actions" in text
    assert "interval: weekly" in text


def test_pytest_configuration_declares_strict_e2e_marker() -> None:
    pyproject = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"e2e: production-like Playwright tests' in pyproject
    assert 'filterwarnings = ["error"]' in pyproject
    assert "xfail_strict = true" in pyproject


def test_e2e_suite_contains_critical_flow_and_accessibility_matrix() -> None:
    full_flow = (_ROOT / "tests" / "e2e" / "test_full_flow.py").read_text(encoding="utf-8")
    matrix = (_ROOT / "tests" / "e2e" / "test_accessibility_matrix.py").read_text(encoding="utf-8")
    audit = (_ROOT / "tests" / "e2e" / "accessibility.py").read_text(encoding="utf-8")

    for phrase in (
        "Створити категорію",
        "Створити чернетку",
        "Зробити current stable",
        "Завантажити в quarantine",
        "expect_download",
        "download_href",
        "status == 404",
    ):
        assert phrase in full_flow
    for browser in ("chromium", "firefox", "webkit"):
        assert browser in matrix
    for rule in (
        "exactly one main landmark",
        "exactly one h1",
        "duplicate id",
        "accessible label",
        "horizontal overflow",
        "axe.run",
        "wcag22aa",
    ):
        assert rule in audit
