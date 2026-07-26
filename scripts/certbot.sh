#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "${project_root}"

env_file="${SOFTWARE_HUB_COMPOSE_ENV_FILE:-.env.production}"
action="${1:-renew}"

if [ ! -r "${env_file}" ]; then
    echo "Missing deployment environment file: ${env_file}" >&2
    exit 1
fi

set -a
# shellcheck disable=SC1090
. "${env_file}"
set +a

: "${SOFTWARE_HUB_DOMAIN:?SOFTWARE_HUB_DOMAIN is required}"
compose_files="-f docker-compose.yml -f docker-compose.production.yml"

case "${action}" in
    issue)
        : "${SOFTWARE_HUB_CERTBOT_EMAIL:?SOFTWARE_HUB_CERTBOT_EMAIL is required}"
        docker compose ${compose_files} --env-file "${env_file}" --profile certbot \
            run --rm certbot certonly \
            --webroot --webroot-path /var/www/certbot \
            --domain "${SOFTWARE_HUB_DOMAIN}" \
            --email "${SOFTWARE_HUB_CERTBOT_EMAIL}" \
            --agree-tos --no-eff-email
        ;;
    renew)
        docker compose ${compose_files} --env-file "${env_file}" --profile certbot \
            run --rm certbot renew --webroot --webroot-path /var/www/certbot
        docker compose ${compose_files} --env-file "${env_file}" exec nginx nginx -s reload
        ;;
    *)
        echo "Usage: scripts/certbot.sh [issue|renew]" >&2
        exit 2
        ;;
esac
