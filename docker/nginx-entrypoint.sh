#!/bin/sh
set -eu

umask 027

if [ "$(id -u)" -eq 0 ]; then
    echo "software-hub-nginx: refusing to run as root" >&2
    exit 1
fi

mode="${SOFTWARE_HUB_NGINX_MODE:-development}"
domain="${SOFTWARE_HUB_DOMAIN:-localhost}"
tls_certificate="${SOFTWARE_HUB_TLS_CERTIFICATE:-/etc/letsencrypt/live/${domain}/fullchain.pem}"
default_tls_key="/etc/letsencrypt/live/${domain}/privkey.pem"
tls_certificate_key="${SOFTWARE_HUB_TLS_CERTIFICATE_KEY:-${default_tls_key}}"
default_admin_access="/etc/software-hub/nginx/snippets/admin-access-open.conf"
admin_access_file="${SOFTWARE_HUB_ADMIN_ACCESS_FILE:-${default_admin_access}}"

template="/etc/software-hub/nginx/templates/${mode}.conf.template"
rendered="/tmp/nginx/conf.d/default.conf"

case "${mode}" in
    development|production)
        ;;
    *)
        echo "software-hub-nginx: invalid SOFTWARE_HUB_NGINX_MODE=${mode}" >&2
        exit 1
        ;;
esac

if [ ! -r "${template}" ]; then
    echo "software-hub-nginx: missing template ${template}" >&2
    exit 1
fi
if [ ! -r "${admin_access_file}" ]; then
    echo "software-hub-nginx: unreadable admin access file ${admin_access_file}" >&2
    exit 1
fi
if [ "${mode}" = "production" ]; then
    if [ "${domain}" = "localhost" ] || [ "${domain}" = "_" ]; then
        echo "software-hub-nginx: production requires SOFTWARE_HUB_DOMAIN" >&2
        exit 1
    fi
    if [ ! -r "${tls_certificate}" ] || [ ! -r "${tls_certificate_key}" ]; then
        echo "software-hub-nginx: TLS certificate or private key is unreadable" >&2
        exit 1
    fi
fi

mkdir -p \
    /tmp/nginx/conf.d \
    /tmp/nginx/client_temp \
    /tmp/nginx/proxy_temp \
    /tmp/nginx/fastcgi_temp \
    /tmp/nginx/uwsgi_temp \
    /tmp/nginx/scgi_temp

export SOFTWARE_HUB_DOMAIN="${domain}"
export SOFTWARE_HUB_TLS_CERTIFICATE="${tls_certificate}"
export SOFTWARE_HUB_TLS_CERTIFICATE_KEY="${tls_certificate_key}"
export SOFTWARE_HUB_ADMIN_ACCESS_FILE="${admin_access_file}"

substitution_variables='$SOFTWARE_HUB_DOMAIN $SOFTWARE_HUB_TLS_CERTIFICATE'
substitution_variables="${substitution_variables} \$SOFTWARE_HUB_TLS_CERTIFICATE_KEY"
substitution_variables="${substitution_variables} \$SOFTWARE_HUB_ADMIN_ACCESS_FILE"
envsubst "${substitution_variables}" \
    < "${template}" > "${rendered}"

nginx -t -c /etc/nginx/nginx.conf
exec "$@"
