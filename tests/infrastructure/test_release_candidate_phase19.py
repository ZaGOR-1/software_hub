"""Release-candidate documentation and packaging invariants for Phase 19."""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path

from app import __version__
from app.core.config import AppSettings
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_VERSION = "1.0.0-rc.2"


def test_release_candidate_version_is_consistent() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    assert __version__ == EXPECTED_VERSION
    assert pyproject["project"]["version"] == EXPECTED_VERSION
    locked_project = next(
        package for package in lock["package"] if package["name"] == "software-hub"
    )
    assert Version(locked_project["version"]) == Version(EXPECTED_VERSION)
    assert f"## [{EXPECTED_VERSION}]" in changelog


def test_runtime_dependency_declaration_matches_lock_metadata() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8")
    declared = {
        re.split(r"[<>=!~ ]", dependency, maxsplit=1)[0]
        for dependency in pyproject["project"]["dependencies"]
    }
    metadata_block = lock.split("[package.metadata]", maxsplit=1)[1].split(
        "[package.metadata.requires-dev]", maxsplit=1
    )[0]
    locked = set(re.findall(r'\{ name = "([^"]+)", specifier = ', metadata_block))

    assert declared == locked


def test_required_release_candidate_documents_exist() -> None:
    required = {
        "ARCHITECTURE.md",
        "CHANGELOG.md",
        "SECURITY.md",
        "DEPLOYMENT.md",
        "BACKUP_RESTORE.md",
        "OPERATIONS.md",
        "docs/environment-variables.md",
        "docs/local-development.md",
        "docs/production-acceptance.md",
        "docs/release-candidate.md",
        "docs/release-checklist.md",
        "docs/threat-model.md",
    }

    assert not [name for name in sorted(required) if not (ROOT / name).is_file()]


def test_environment_reference_covers_every_application_setting() -> None:
    reference = (ROOT / "docs/environment-variables.md").read_text(encoding="utf-8")
    missing = [
        f"SOFTWARE_HUB_{field_name.upper()}"
        for field_name in AppSettings.model_fields
        if f"SOFTWARE_HUB_{field_name.upper()}" not in reference
    ]

    assert missing == []


def test_rehearsal_scripts_are_executable_and_fail_fast() -> None:
    for relative in (
        "scripts/rehearse-release-candidate.sh",
        "scripts/verify-release-candidate.sh",
    ):
        path = ROOT / relative
        content = path.read_text(encoding="utf-8")
        if os.name != "nt":
            assert path.stat().st_mode & 0o111
        assert content.startswith("#!/bin/sh\nset -eu\n")


def test_production_acceptance_preserves_phase_boundary() -> None:
    runbook = (ROOT / "docs/production-acceptance.md").read_text(encoding="utf-8")

    assert "Only Phase 20" in runbook
    assert "software.hotzagor.tech" in runbook
    assert "fail-closed" in runbook
    assert "offsite" in runbook


def test_release_candidate_workflow_builds_immutable_evidence() -> None:
    text = (ROOT / ".github/workflows/release-candidate.yml").read_text(encoding="utf-8")

    for required in (
        "tags:",
        '"v*-rc.*"',
        "scripts/rehearse-release-candidate.sh",
        'test "${GITHUB_REF_TYPE}" = "tag"',
        'test "${GITHUB_REF_NAME}" = "v${version}"',
        'git rev-list -n 1 "${GITHUB_REF_NAME}"',
        "git archive",
        "gzip -n",
        "sha256sum",
        "evidence-manifest.json",
        '"commit_sha": os.environ["GITHUB_SHA"]',
        '"run_url":',
        "attestations: write",
        "id-token: write",
        "artifact-metadata: write",
        "actions/attest@f7c74d28b9d84cb8768d0b8ca14a4bac6ef463e6 # v4.2.0",
        "subject-path:",
        "test-results/release-candidate/rehearsal.json",
        "${{ steps.attest.outputs.attestation-id }}",
        "${{ steps.attest.outputs.attestation-url }}",
        "${{ steps.attest.outputs.bundle-path }}",
        "provenance.sigstore.json",
        "attestation-reference.json",
        "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4.6.2",
        "software-hub-release-candidate-${{ github.sha }}-${{ github.run_attempt }}",
        "retention-days: 90",
    ):
        assert required in text
