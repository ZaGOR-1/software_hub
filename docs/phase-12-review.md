# Phase 12 completion review

## Scope

Phase 12 implements the protected public download boundary for published
`ReleaseFile` records. FastAPI authorizes metadata and records aggregate starts;
Nginx serves the file through an `internal` location. The phase intentionally does
not add the public catalog UI, TLS/certbot or final Docker permissions.

## Implemented application components

```text
app/routers/public/
├── __init__.py
└── downloads.py

app/services/download_service.py
app/repositories/download_stat_repository.py
```

The application now exposes:

```text
GET  /download/{public_uuid}/{safe_filename}
HEAD /download/{public_uuid}/{safe_filename}
```

Each grant validates:

- public UUID lookup;
- exact display filename;
- full Software → Release → ReleaseFile status and visibility chain;
- active administrator session for private files;
- permanent-storage location;
- physical size equality.

Unknown, disabled, archived, draft, private-without-session and filename-mismatch
cases use a generic `404` response.

## Nginx integration

Added:

```text
nginx/nginx.conf
nginx/conf.d/default.conf
nginx/snippets/proxy_headers.conf
```

The internal location maps only permanent software storage:

```nginx
location ^~ /protected-downloads/ {
    internal;
    alias /srv/software-hub/storage/software/;
    autoindex off;
}
```

The `/download/` authorization route has a dedicated request-rate zone. Phase 17
will place these files into the final container image, configure shared storage
UID/GID permissions, TLS, HTTP redirect and production security headers.

## ASGI Content-Length correction

An early real-server smoke test exposed an invalid design: setting the physical
file length on FastAPI's intentionally empty upstream response causes Uvicorn to
raise `Response content shorter than Content-Length`.

The application now omits the physical length. Starlette emits an upstream length
of zero, Nginx consumes `X-Accel-Redirect`, stats the internal file and emits the
actual client-facing `Content-Length`. This behavior is covered by the real Nginx
smoke test.

## Session cookie amendment

The administrator session cookie path changed from `/admin` to `/`. This is needed
because private download authorization occurs under `/download/...`. The cookie
remains opaque and `HttpOnly`; production requires `Secure` and `SameSite=Lax`.
Only routes with an explicit auth dependency resolve the session.

Updated documentation:

- ADR-0003 server-side sessions;
- technical decisions;
- authentication/session guide;
- `.env.example`.

## Download statistics semantics

Authorized GET requests atomically increment:

- `ReleaseFile.download_count`;
- daily `download_count`;
- daily `successful_download_count`.

This means an authorized start before Nginx transfer, not confirmed completion.
Range GET requests count once. HEAD does not increment successful or total counts.
Known policy denials increment only daily `blocked_download_count`; unknown UUIDs
and storage integrity failures do not create client-policy statistics.

No schema migration was required. The existing `download_stats` table and indexes
already support the implementation.

## Security behavior

- physical paths never come from URL input;
- the public UUID is a lookup key, not sufficient authorization;
- requested filename must exactly match metadata;
- quarantine, temporary and missing files cannot be granted;
- direct requests to the internal Nginx URI return `404`;
- `Content-Disposition` has a safe ASCII fallback and UTF-8 `filename*`;
- invalid media types fall back to `application/octet-stream`;
- private responses use `private, no-store`;
- public/unlisted responses use `no-store`;
- blocked responses do not expose the failed condition;
- Nginx, not Python, handles body bytes and ranges.

## Automated test result

```text
pytest:                         428 passed
Branch coverage:               93.99%
Warnings:                      0
Python compileall:             passed
Function annotations:          passed
Python lines over 100 chars:   0
Jinja templates:               27 passed
Alembic upgrade/check:         passed
Alembic downgrade/re-upgrade:  passed
Alembic schema drift:          absent
Migration head:                0002_phase4_domain_schema
TOML/YAML parsing:             passed
uv lock metadata alignment:    passed
uv export --frozen --no-dev:   passed
Markdown internal links:       passed
```

## Real Uvicorn → Nginx acceptance

A production-like local topology used a real Uvicorn process, real Nginx process,
file-backed SQLite database and permanent storage file.

```text
direct internal URI:           404
full GET:                      200
full Content-Length:           36
full bytes:                    exact match
Range bytes=5-9:              206
range body:                    56789
HEAD:                          200
HEAD Content-Length:           36
database counters:             2 / 2 / 2 / 0
```

The two successful starts are the full GET and range GET. HEAD did not increment
the counters.

## Files added or materially changed

```text
app/core/config.py
app/main.py
app/repositories/download_stat_repository.py
app/routers/public/__init__.py
app/routers/public/downloads.py
app/services/download_service.py
nginx/nginx.conf
nginx/conf.d/default.conf
nginx/snippets/proxy_headers.conf
tests/unit/services/test_download_service_phase12.py
tests/integration/repositories/test_download_stats_phase12.py
tests/integration/downloads/test_download_routes_phase12.py
tests/security/test_download_security_phase12.py
.env.example
README.md
docs/download-delivery.md
docs/phase-12-review.md
docs/threat-model.md
docs/release-checklist.md
docs/technical-decisions.md
docs/authentication-sessions.md
docs/ADR/0003-server-side-sessions.md
docs/ADR/0004-x-accel-redirect.md
```

## Deferred work

- public catalog pages and visible download buttons — Phase 13;
- complete responsive public UI, theme, accessibility and SEO — Phase 14;
- operational dashboard and richer health checks — Phase 15;
- reconciliation and backup/restore — Phase 16;
- final Docker, shared UID/GID, read-only Nginx mount, TLS and production headers —
  Phase 17;
- full Python 3.14 CI quality/security matrix — Phase 18.

## Environment limitation

Tests were executed locally with Python 3.13.5 because the offline sandbox does
not have Python 3.14 or cached Ruff, mypy, Bandit and pip-audit installations.
The target remains Python 3.14. GitHub Actions must run the configured format,
lint, strict typing, dependency audit and static security jobs before merge.

## Definition of done

- [x] Public UUID GET and HEAD routes exist
- [x] Full metadata-chain authorization is centralized
- [x] Public, unlisted and private behavior is tested
- [x] Disabled, archived, draft, missing and quarantine files are denied
- [x] FastAPI never streams the file body
- [x] Nginx internal redirect is configured
- [x] Direct internal URI is denied
- [x] Real Content-Length is produced by Nginx
- [x] Range/resume returns `206 Partial Content`
- [x] GET and HEAD accounting semantics are documented and tested
- [x] Safe attachment and media-type headers are tested
- [x] No schema migration is required and Alembic has no drift
- [x] Threat model, ADRs, checklist and main README are updated
