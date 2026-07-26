#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "${project_root}"

requirements_file=$(mktemp)
trap 'rm -f -- "${requirements_file}"' EXIT HUP INT TERM
uv export --frozen --no-dev --output-file "${requirements_file}"

uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uvx --from 'bandit[toml]==1.9.4' bandit -c pyproject.toml -r app
uvx --from 'pip-audit==2.10.1' pip-audit --requirement "${requirements_file}"
uv run python -m alembic upgrade head
uv run python -m alembic check
uv run python -m pytest -o addopts='' tests/infrastructure/test_release_candidate_phase19.py -q
PYTHON="$(pwd)/.venv/bin/python" ./scripts/rehearse-release-candidate.sh
