#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "${project_root}"

env_file="${SOFTWARE_HUB_COMPOSE_ENV_FILE:-.env.production}"
backup_id="${1:-}"

if [ -z "${backup_id}" ]; then
    echo "Usage: scripts/rollback.sh <backup-id>" >&2
    exit 2
fi
if [ ! -r "${env_file}" ]; then
    echo "Missing deployment environment file: ${env_file}" >&2
    exit 1
fi

compose_files="-f docker-compose.yml -f docker-compose.production.yml"
docker compose ${compose_files} --env-file "${env_file}" stop app nginx
docker compose ${compose_files} --env-file "${env_file}" \
    run --rm --no-deps -e SOFTWARE_HUB_RUN_MIGRATIONS=false app \
    python -m app.cli restore-backup --backup-id "${backup_id}" --yes
docker compose ${compose_files} --env-file "${env_file}" up -d app nginx

echo "Rollback restore completed from ${backup_id}. Verify /health and critical flows."
