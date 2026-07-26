# syntax=docker/dockerfile:1.7

ARG NGINX_IMAGE=nginx:1.30.4-alpine3.24
FROM ${NGINX_IMAGE}

ARG APP_UID=10001
ARG APP_GID=10001

RUN apk add --no-cache gettext \
    && addgroup -S -g "${APP_GID}" softwarehub \
    && adduser -S -D -H -u "${APP_UID}" -G softwarehub softwarehub \
    && mkdir -p \
      /tmp/nginx/conf.d \
      /tmp/nginx/client_temp \
      /tmp/nginx/proxy_temp \
      /tmp/nginx/fastcgi_temp \
      /tmp/nginx/uwsgi_temp \
      /tmp/nginx/scgi_temp \
      /var/www/certbot \
    && chown -R softwarehub:softwarehub /tmp/nginx /var/www/certbot

COPY nginx/nginx.conf /etc/nginx/nginx.conf
COPY nginx/templates /etc/software-hub/nginx/templates
COPY nginx/snippets /etc/software-hub/nginx/snippets
COPY app/static /usr/share/nginx/html/static
COPY docker/nginx-entrypoint.sh /usr/local/bin/software-hub-nginx-entrypoint
COPY docker/nginx-healthcheck.sh /usr/local/bin/software-hub-nginx-healthcheck

RUN chmod 0555 \
      /usr/local/bin/software-hub-nginx-entrypoint \
      /usr/local/bin/software-hub-nginx-healthcheck \
    && find /usr/share/nginx/html/static -type d -exec chmod 0555 {} + \
    && find /usr/share/nginx/html/static -type f -exec chmod 0444 {} +

USER softwarehub:softwarehub
EXPOSE 8080 8443

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD ["/usr/local/bin/software-hub-nginx-healthcheck"]

ENTRYPOINT ["/usr/local/bin/software-hub-nginx-entrypoint"]
CMD ["nginx", "-g", "daemon off;"]
