# Environment variable reference

All application settings use the `SOFTWARE_HUB_` prefix and are parsed by
`app.core.config.AppSettings`. Names are case-insensitive, but production files
should use the uppercase forms below. `.env.example` is for local development;
`.env.production.example` is the deployment template.

## Required production values

| Variable | Purpose |
|---|---|
| `SOFTWARE_HUB_APP_ENVIRONMENT` | Must be `production`. |
| `SOFTWARE_HUB_APP_SECRET_KEY` | Strong persistent application/session secret. |
| `SOFTWARE_HUB_CSRF_SECRET` | Separate strong persistent CSRF secret. |
| `SOFTWARE_HUB_DATABASE_URL` | Absolute persistent SQLite SQLAlchemy URL. |
| `SOFTWARE_HUB_PUBLIC_BASE_URL` | Canonical HTTPS origin. |
| `SOFTWARE_HUB_TRUSTED_HOSTS` | Comma-separated accepted hostnames. |
| `SOFTWARE_HUB_TRUSTED_PROXY_NETWORKS` | Only the internal Nginx proxy network. |
| `SOFTWARE_HUB_STORAGE_ROOT` | Private storage root. |
| `SOFTWARE_HUB_TEMPORARY_ROOT` | Temporary upload directory. |
| `SOFTWARE_HUB_QUARANTINE_ROOT` | Quarantine directory. |
| `SOFTWARE_HUB_ICONS_ROOT` | Icon storage directory. |
| `SOFTWARE_HUB_BACKUP_ROOT` | Backup root, separate from storage. |

Generate secrets once and retain them across restarts:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Do not use the same value for the application and CSRF secrets.

## Application

| Variable | Default | Notes |
|---|---:|---|
| `SOFTWARE_HUB_APP_NAME` | `Software Hub` | Display and API name. |
| `SOFTWARE_HUB_APP_VERSION` | package version | Normally do not override. |
| `SOFTWARE_HUB_APP_ENVIRONMENT` | `development` | `development`, `test`, or `production`. |
| `SOFTWARE_HUB_APP_DEBUG` | `false` | Forbidden in production. |
| `SOFTWARE_HUB_DOCS_ENABLED` | `true` | Disable API docs in production. |

## Authentication and CSRF

| Variable | Default | Notes |
|---|---:|---|
| `SOFTWARE_HUB_APP_SECRET_KEY` | unset | Required and validated in production. |
| `SOFTWARE_HUB_CSRF_SECRET` | unset | Required and distinct in production. |
| `SOFTWARE_HUB_CSRF_FORM_FIELD_NAME` | `csrf_token` | Hidden form field. |
| `SOFTWARE_HUB_CSRF_HEADER_NAME` | `X-CSRF-Token` | Header-first upload protection. |
| `SOFTWARE_HUB_CSRF_TOKEN_TTL_SECONDS` | configured default | Authenticated form token lifetime. |
| `SOFTWARE_HUB_CSRF_TOKEN_MAX_LENGTH` | configured default | Parsing bound. |
| `SOFTWARE_HUB_LOGIN_CSRF_COOKIE_NAME` | `software_hub_login_csrf` | Pre-auth cookie. |
| `SOFTWARE_HUB_LOGIN_CSRF_COOKIE_PATH` | `/admin/login` | Pre-auth cookie scope. |
| `SOFTWARE_HUB_LOGIN_CSRF_COOKIE_SAME_SITE` | `strict` | `lax` or `strict`. |
| `SOFTWARE_HUB_LOGIN_CSRF_TTL_SECONDS` | configured default | Login-token lifetime. |
| `SOFTWARE_HUB_SESSION_COOKIE_NAME` | `software_hub_session` | Opaque token cookie. |
| `SOFTWARE_HUB_SESSION_COOKIE_PATH` | `/` | Needed for private downloads. |
| `SOFTWARE_HUB_SESSION_COOKIE_SAME_SITE` | `lax` | `lax` or `strict`. |
| `SOFTWARE_HUB_SESSION_COOKIE_SECURE` | environment-derived | Must be true in production. |
| `SOFTWARE_HUB_SESSION_IDLE_TIMEOUT_SECONDS` | `1800` | Sliding inactivity expiry. |
| `SOFTWARE_HUB_SESSION_ABSOLUTE_TIMEOUT_SECONDS` | `43200` | Hard lifetime. |
| `SOFTWARE_HUB_SESSION_TOUCH_INTERVAL_SECONDS` | configured default | Limits SQLite writes. |
| `SOFTWARE_HUB_LOGIN_MAX_FAILED_ATTEMPTS` | `5` | Per-account threshold. |
| `SOFTWARE_HUB_LOGIN_LOCKOUT_SECONDS` | `900` | Temporary lockout. |
| `SOFTWARE_HUB_PASSWORD_MIN_LENGTH` | configured default | CLI-created passwords. |
| `SOFTWARE_HUB_PASSWORD_MAX_LENGTH` | configured default | Input bound. |
| `SOFTWARE_HUB_ARGON2_TIME_COST` | `3` | Tune only after measurement. |
| `SOFTWARE_HUB_ARGON2_MEMORY_COST_KIB` | `65536` | Tune only after measurement. |
| `SOFTWARE_HUB_ARGON2_PARALLELISM` | `4` | Tune only after measurement. |
| `SOFTWARE_HUB_ADMIN_PASSWORD` | unset | Temporary CLI input; do not persist. |

## Database

| Variable | Default | Notes |
|---|---:|---|
| `SOFTWARE_HUB_DATABASE_URL` | `/srv/.../software-hub.db` | SQLite only for the MVP. |
| `SOFTWARE_HUB_DATABASE_ECHO` | `false` | Never enable in production. |
| `SOFTWARE_HUB_SQLITE_BUSY_TIMEOUT_MS` | configured default | Applied per connection. |
| `SOFTWARE_HUB_SQLITE_SYNCHRONOUS_MODE` | `normal` | SQLite synchronous mode. |

## Public origin and proxy

| Variable | Default | Notes |
|---|---:|---|
| `SOFTWARE_HUB_PUBLIC_BASE_URL` | `http://localhost:8000` | HTTPS canonical URL in production. |
| `SOFTWARE_HUB_INTERNAL_DOWNLOAD_PREFIX` | `/protected-downloads/` | Must match Nginx. |
| `SOFTWARE_HUB_TRUSTED_HOSTS` | local defaults | Comma-separated. No wildcard in production. |
| `SOFTWARE_HUB_TRUSTED_PROXY_NETWORKS` | local defaults | Restrict to Nginx. |
| `SOFTWARE_HUB_FORWARDED_ALLOW_IPS` | `172.30.0.10` | Uvicorn entrypoint setting. |

## Storage and backups

| Variable | Default | Notes |
|---|---:|---|
| `SOFTWARE_HUB_STORAGE_ROOT` | `/srv/software-hub/storage` | Contains permanent software and subroots. |
| `SOFTWARE_HUB_TEMPORARY_ROOT` | storage temporary | Must share a filesystem for atomic moves. |
| `SOFTWARE_HUB_QUARANTINE_ROOT` | storage quarantine | Private and writable by app only. |
| `SOFTWARE_HUB_ICONS_ROOT` | storage icons | Private application-managed icons. |
| `SOFTWARE_HUB_BACKUP_ROOT` | `/srv/software-hub/backups` | Must not overlap storage or DB. |
| `SOFTWARE_HUB_BACKUP_RETENTION_COUNT` | `14` | Verified backups retained. |
| `SOFTWARE_HUB_BACKUP_MIN_FREE_BYTES` | `1073741824` | Backup reserve. |
| `SOFTWARE_HUB_STORAGE_MIN_FREE_BYTES` | configured default | Upload/health reserve. |
| `SOFTWARE_HUB_TEMPORARY_FILE_MAX_AGE_SECONDS` | configured default | Cleanup threshold. |

## Upload and malware scanning

| Variable | Default | Notes |
|---|---:|---|
| `SOFTWARE_HUB_MAX_UPLOAD_SIZE` | `2147483648` | Must match Nginx request limit. |
| `SOFTWARE_HUB_UPLOAD_CHUNK_SIZE` | configured default | Bounded copy chunks. |
| `SOFTWARE_HUB_UPLOAD_MAGIC_SAMPLE_SIZE` | configured default | Signature sample bound. |
| `SOFTWARE_HUB_ALLOWED_EXTENSIONS` | `.exe,.msi,.zip,.7z` | Comma-separated allowlist. |
| `SOFTWARE_HUB_CLAMAV_ENABLED` | `false` | Optional for low-memory hosts. |
| `SOFTWARE_HUB_CLAMAV_COMMAND` | `clamscan` | Local command, no user shell data. |
| `SOFTWARE_HUB_CLAMAV_TIMEOUT_SECONDS` | configured default | Scanner timeout. |

## Logging, health and headers

| Variable | Default | Notes |
|---|---:|---|
| `SOFTWARE_HUB_LOG_LEVEL` | `info` | Structured application level. |
| `SOFTWARE_HUB_LOG_JSON` | `true` | Recommended in production. |
| `SOFTWARE_HUB_REQUEST_ID_HEADER` | `X-Request-ID` | Correlation header. |
| `SOFTWARE_HUB_REQUEST_ID_MAX_LENGTH` | configured default | Untrusted header bound. |
| `SOFTWARE_HUB_SECURITY_HEADERS_ENABLED` | `true` | App fallback; Nginx owns production headers. |
| `SOFTWARE_HUB_CONTENT_SECURITY_POLICY` | hardened default | Keep synchronized with frontend assets. |
| `SOFTWARE_HUB_HEALTH_PATH` | `/health` | Used by containers and Nginx. |

## Compose and Nginx deployment variables

These values are consumed by Compose or shell entrypoints rather than
`AppSettings`:

| Variable | Purpose |
|---|---|
| `SOFTWARE_HUB_DOMAIN` | TLS server name and public host. |
| `SOFTWARE_HUB_CERTBOT_EMAIL` | Let's Encrypt account email. |
| `SOFTWARE_HUB_DATA_ROOT` | Host persistent root. |
| `SOFTWARE_HUB_UID` / `SOFTWARE_HUB_GID` | Non-root host ownership. |
| `SOFTWARE_HUB_APP_IMAGE` | Optional pinned app image. |
| `SOFTWARE_HUB_NGINX_APP_IMAGE` | Optional pinned Nginx image. |
| `SOFTWARE_HUB_NGINX_MODE` | `development` or `production`. |
| `SOFTWARE_HUB_TLS_CERTIFICATE` | Certificate path inside Nginx. |
| `SOFTWARE_HUB_TLS_CERTIFICATE_KEY` | Private key path inside Nginx. |
| `SOFTWARE_HUB_ADMIN_ACCESS_FILE` | Mounted Nginx allow/deny include. |
| `SOFTWARE_HUB_RUN_MIGRATIONS` | Entry-point migration switch. |
| `SOFTWARE_HUB_COMPOSE_ENV_FILE` | Deployment script env-file path. |

## Secret handling rules

- never commit `.env` or `.env.production`;
- protect secret files with mode `0600`;
- do not pass passwords as CLI arguments;
- do not rotate signing secrets during routine deploys;
- change a leaked secret and revoke all administrator sessions;
- store offsite backup credentials outside this application configuration.
