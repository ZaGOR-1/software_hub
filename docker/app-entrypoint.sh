#!/bin/sh
set -eu

umask 027

if [ "$(id -u)" -eq 0 ]; then
    echo "software-hub: refusing to run the application as root" >&2
    exit 1
fi

forwarded_allow_ips="${SOFTWARE_HUB_FORWARDED_ALLOW_IPS:-172.30.0.10}"
run_migrations="${SOFTWARE_HUB_RUN_MIGRATIONS:-true}"

case "${run_migrations}" in
    true|1|yes)
        python -m alembic upgrade head
        ;;
    false|0|no)
        ;;
    *)
        echo "software-hub: SOFTWARE_HUB_RUN_MIGRATIONS must be true or false" >&2
        exit 1
        ;;
esac

if [ "$#" -eq 0 ]; then
    set -- uvicorn app.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --workers 1 \
        --proxy-headers \
        --forwarded-allow-ips "${forwarded_allow_ips}" \
        --no-access-log \
        --timeout-graceful-shutdown 25
elif [ "$1" = "uvicorn" ]; then
    set -- "$@" --forwarded-allow-ips "${forwarded_allow_ips}"
fi

exec "$@"
