#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo "prepare-host.sh must run as root" >&2
    exit 1
fi

root="${SOFTWARE_HUB_DATA_ROOT:-/srv/software-hub}"
uid="${SOFTWARE_HUB_UID:-10001}"
gid="${SOFTWARE_HUB_GID:-10001}"

case "${root}" in
    /*) ;;
    *)
        echo "SOFTWARE_HUB_DATA_ROOT must be absolute" >&2
        exit 1
        ;;
esac

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
    install -d -m 0750 -o "${uid}" -g "${gid}" "${directory}"
done

find "${root}" -type d -exec chmod 0750 {} +
find "${root}" -type f -exec chmod 0640 {} +
chown -R "${uid}:${gid}" "${root}"

printf 'Prepared %s for uid=%s gid=%s\n' "${root}" "${uid}" "${gid}"
