#!/bin/sh
set -eu

mode="${SOFTWARE_HUB_NGINX_MODE:-development}"
domain="${SOFTWARE_HUB_DOMAIN:-localhost}"
if [ "${mode}" = "production" ]; then
    url="https://127.0.0.1:8443/health"
    exec wget \
        --quiet \
        --no-check-certificate \
        --header="Host: ${domain}" \
        --output-document=/dev/null \
        "${url}"
fi
exec wget \
    --quiet \
    --header="Host: ${domain}" \
    --output-document=/dev/null \
    http://127.0.0.1:8080/health
