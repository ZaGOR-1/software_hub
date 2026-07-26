#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
root="${SOFTWARE_HUB_DATA_ROOT:-${project_root}/.runtime}"

for directory in \
    "${root}/database" \
    "${root}/storage/software" \
    "${root}/storage/icons" \
    "${root}/storage/import" \
    "${root}/storage/temporary" \
    "${root}/storage/quarantine" \
    "${root}/backups" \
    "${root}/certbot/www" \
    "${root}/certbot/logs" \
    "${root}/certbot/lib" \
    "${root}/letsencrypt"; do
    mkdir -p "${directory}"
    chmod 0750 "${directory}"
done

printf 'Prepared local runtime at %s\n' "${root}"
printf 'Use SOFTWARE_HUB_UID=%s SOFTWARE_HUB_GID=%s when building.\n' "$(id -u)" "$(id -g)"
