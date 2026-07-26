# Phase 17 container architecture

## Images

### Application image

`Dockerfile` uses a dependency-builder and a minimal runtime stage based on
`python:3.14.6-slim-bookworm`. Dependencies are exported from the committed
`uv.lock` and installed with hashes into `/opt/software-hub/venv`. Runtime copies
only the virtual environment, application package and Alembic files.

The runtime user is `softwarehub` with configurable default UID/GID `10001`.
Entrypoint behavior is deliberately small:

1. refuse UID 0;
2. set umask `027`;
3. optionally execute `alembic upgrade head`;
4. start one Uvicorn worker;
5. accept forwarding headers only from the configured Nginx address;
6. use a 25-second graceful-shutdown timeout.

### Nginx image

`nginx/Dockerfile` is based on `nginx:1.30.4-alpine3.24`. It copies only Nginx
configuration, static assets and two entrypoint/health scripts. It also runs as
UID/GID `10001` on high ports 8080 and 8443, so no bind-service capability is
required inside the container.

At startup the entrypoint renders exactly one trusted template into `/tmp`, checks
certificate readability in production, runs `nginx -t`, then executes Nginx.
Environment substitution is restricted to four Software Hub variables so Nginx
variables such as `$request_id` and `$request_uri` cannot be erased.

## Compose networks

```text
frontend bridge:
  nginx
  optional certbot

backend internal bridge (default 172.30.0.0/24):
  nginx 172.30.0.10
  app   172.30.0.20
```

The app has no host port and does not join the frontend network. Static backend
addresses let Uvicorn and the app trust one exact proxy address rather than a wide
Docker subnet. If the subnet is changed, the Nginx IP, app IP and trusted-proxy
environment variables must change together.

## Mount matrix

| Service | Mount | Mode |
|---|---|---|
| app | `/srv/software-hub/database` | read/write |
| app | `/srv/software-hub/storage` | read/write |
| app | `/srv/software-hub/backups` | read/write |
| nginx | `/srv/software-hub/storage/software` | read-only |
| nginx | `/var/www/certbot` | read-only |
| nginx | `/etc/letsencrypt` (production) | read-only |
| nginx | admin allowlist file | read-only |
| certbot | certificate/challenge/log directories | read/write |

Application and Nginx root filesystems are read-only. Their only ephemeral write
location is a size-bounded, `noexec,nosuid,nodev` `/tmp` tmpfs.

## Nginx ownership of HTTP concerns

The app's browser-security middleware is disabled in Compose so Nginx is the single
production owner of browser headers. The app still validates trusted hosts,
application authorization, CSRF and all domain permissions.

The upload location disables Nginx request buffering and extends proxy timeouts.
Nginx still applies the hard request-size limit before the request reaches
Starlette. Download responses contain no Python body; the internal alias serves the
permanent file and supports Nginx range handling.

## Health and shutdown

The app healthcheck uses the Python standard library and requires all public health
components to be `ok`. Nginx health checks its proxied `/health` endpoint with the
configured Host header. Compose starts Nginx only after the app becomes healthy.

`init: true` supplies a minimal init process, and Compose grants 35 seconds to the
app and 15 seconds to Nginx for orderly shutdown.

## Local development

```bash
cp .env.example .env
./scripts/prepare-local.sh
SOFTWARE_HUB_UID=$(id -u) SOFTWARE_HUB_GID=$(id -g) \
  docker compose up --build
```

The default HTTP listener binds only to `127.0.0.1:8080`.
