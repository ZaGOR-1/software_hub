#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "${project_root}"

compose_files="-f docker-compose.yml -f docker-compose.production.yml"
env_file="${SOFTWARE_HUB_COMPOSE_ENV_FILE:-.env.production}"

if [ ! -r "${env_file}" ]; then
    echo "Missing deployment environment file: ${env_file}" >&2
    exit 1
fi

set -a
# shellcheck disable=SC1090
. "${env_file}"
set +a

backup_output=$(docker compose ${compose_files} --env-file "${env_file}" \
    run --rm --no-deps -e SOFTWARE_HUB_RUN_MIGRATIONS=false app \
    python -m app.cli create-backup 2>/dev/null || true)
backup_id=$(printf '%s\n' "${backup_output}" | tail -n 1 | python -c \
    'import json, sys; print(json.load(sys.stdin).get("backup_id", ""))' \
    2>/dev/null || true)

if [ -n "${backup_id}" ]; then
    printf 'Pre-deploy backup: %s\n' "${backup_id}"
else
    echo "No pre-deploy backup was created; continue only for an initial empty deployment." >&2
fi

docker compose ${compose_files} --env-file "${env_file}" build --pull
docker compose ${compose_files} --env-file "${env_file}" up -d --remove-orphans

docker compose ${compose_files} --env-file "${env_file}" ps
curl --fail --silent --show-error \
    --retry 12 --retry-delay 5 \
    "https://${SOFTWARE_HUB_DOMAIN}/health" >/dev/null

printf 'Deployment health check passed for https://%s/health\n' "${SOFTWARE_HUB_DOMAIN}"
