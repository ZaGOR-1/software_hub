# Software Hub

Software Hub is a production-oriented personal catalog of software releases and
installer files. It combines a public server-rendered catalog, a protected
administration panel, quarantine-based uploads and direct large-file delivery
through Nginx.

The repository is implemented phase by phase. Phases 0–19 establish the approved
architecture, quality tooling, hardened application core, SQLite persistence,
complete MVP schema, transaction-oriented services, administrator authentication,
CSRF protection, administration catalog, private filesystem and quarantine
pipeline, failure-compensated file lifecycle, Nginx-backed protected downloads,
the public catalog, accessible theme/SEO layer, bounded operations observability,
verified backup/restore/reconciliation tooling and a hardened Docker Compose
deployment package with TLS-ready Nginx.

## Release candidate

The repository version is **`1.0.0-rc.2`**. This candidate closes the blockers
found by the full Linux and VPS audit and is the source revision intended for
the `software.hotzagor.tech` Phase 20 deployment.

## Current state

Implemented:

- architecture decisions, threat model and fixed MVP boundaries;
- FastAPI application factory and typed fail-fast settings;
- structured logging, request IDs and production-safe errors;
- trusted-host, proxy-header and security-header middleware;
- SQLAlchemy 2.x engine, short transactions and Alembic;
- SQLite foreign keys, WAL, busy timeout and UTC datetimes;
- complete User, Session, Category, Tag, Software, Release, ReleaseFile,
  DownloadStat and AuditLog models;
- repositories, bounded pagination and parameterized search;
- lifecycle and visibility policies;
- Argon2id administrator authentication and server-side sessions;
- generic login failures, lockout, rotation, expiry and revocation;
- signed pre-authentication and session-bound CSRF protection;
- server-rendered administration CRUD for categories, tags, software and releases;
- atomic audit logging for catalog mutations;
- private storage startup validation and writable probes;
- Unicode-safe filename normalization and double-extension protection;
- UUID-based physical filenames and sharded relative paths;
- path-containment and symlink defenses;
- disk reserve checks, `0750` directories and `0640` stored files;
- same-filesystem atomic moves and conservative temporary cleanup;
- release-specific multipart upload into private quarantine;
- actual-size enforcement, SHA-256 and EXE/MSI/ZIP/7z signature assessment;
- duplicate-hash warnings and optional non-blocking malware scanning;
- failure-compensated ReleaseFile metadata and upload audit records;
- manual quarantine approve/reject/reopen decisions;
- integrity verification before publication;
- atomic quarantine-to-permanent publication with DB rollback compensation;
- disable, archive and restore-to-ready lifecycle actions;
- separate metadata-only and permanent deletion workflows with explicit phrases;
- public UUID download authorization across Software, Release and ReleaseFile;
- public, unlisted and administrator-only private download policies;
- GET/HEAD routes with safe attachment headers and daily aggregate statistics;
- Nginx `internal` delivery through `X-Accel-Redirect` with Range/resume support;
- public home, catalog, search, category, software and release-history pages;
- public-only facets and immutable presentation models that exclude storage data;
- explicit system/light/dark theme preference with local persistence;
- keyboard skip links, focus states, accessible forms/tables and reduced-motion support;
- trusted canonical, Open Graph and Twitter metadata;
- public-only XML sitemap and final robots/noindex policy;
- authenticated audit log with safe filters and bounded pagination;
- strict allowlisted audit metadata without filesystem paths or secrets;
- operational dashboard metrics for downloads, quarantine, disk and backups;
- public application/database/storage/disk readiness checks;
- verified SQLite/storage backups with manifests, retention and staged restore;
- read-only reconciliation, orphan cleanup and checksum maintenance CLI;
- pytest, coverage, Ruff, mypy, Bandit, pip-audit, pre-commit and CI configuration.
- multi-stage non-root application and Nginx container images;
- hardened Docker Compose services with read-only roots and minimal mounts;
- TLS/Certbot bootstrap, fail-closed admin restriction and deployment runbooks.

Not implemented yet:

- icon upload;
- automated Trivy container-image scanning and the complete Phase 18 quality matrix;
- real Playwright/axe cross-browser CI matrix.

## Requirements

- Python 3.14.x;
- uv 0.10.x or compatible newer release.

## Local setup

```bash
uv python install 3.14
uv sync --all-groups --locked
cp .env.example .env
```

Use absolute writable development paths. For example:

```text
SOFTWARE_HUB_DATABASE_URL=sqlite+pysqlite:////home/user/software-hub-data/database/software-hub.db
SOFTWARE_HUB_STORAGE_ROOT=/home/user/software-hub-data/storage
SOFTWARE_HUB_TEMPORARY_ROOT=/home/user/software-hub-data/storage/temporary
SOFTWARE_HUB_QUARANTINE_ROOT=/home/user/software-hub-data/storage/quarantine
SOFTWARE_HUB_ICONS_ROOT=/home/user/software-hub-data/storage/icons
SOFTWARE_HUB_BACKUP_ROOT=/home/user/software-hub-data/backups
SOFTWARE_HUB_STORAGE_MIN_FREE_BYTES=1073741824
```

The temporary, quarantine and icons roots must be distinct descendants of
`STORAGE_ROOT`. `BACKUP_ROOT` must remain outside it. At startup the application
creates, permission-hardens and write-probes every required directory. Configure
the upload chunk, magic sample and optional ClamAV settings from `.env.example`.

Generate separate high-entropy values for:

```text
SOFTWARE_HUB_APP_SECRET_KEY
SOFTWARE_HUB_CSRF_SECRET
```

Apply migrations:

```bash
uv run alembic upgrade head
uv run alembic current
uv run alembic check
```

Create the first administrator without placing the password in shell history:

```bash
uv run python -m app.cli create-admin --username admin
```

Run the development server:

```bash
uv run uvicorn app.main:app --reload
```

Open:

- health: `http://127.0.0.1:8000/health`;
- admin login: `http://127.0.0.1:8000/admin/login`;
- OpenAPI: `http://127.0.0.1:8000/docs`.

Healthy response:

```json
{
  "status": "ok",
  "service": "software-hub",
  "version": "1.0.0-rc.2",
  "checks": {
    "application": "ok",
    "database": "ok",
    "storage": "ok",
    "disk": "ok"
  }
}
```

The public health response exposes status names only. Capacity, disk reserve,
backup-manifest time and audit activity are available only on the authenticated
admin dashboard. Any critical database, storage or disk failure returns a generic
HTTP `503` without paths or driver details.

## Authentication and CSRF

Core browser routes include login/logout, `/admin`, `/admin/software`,
`/admin/categories`, `/admin/tags` and nested release management.

`POST /admin/login` requires a signed short-lived token bound to an HttpOnly
pre-authentication nonce cookie. Authenticated forms use tokens bound to the
specific server-side session. Missing, invalid, expired or cross-session tokens
return HTTP `403` and no mutation runs.

Every future state-changing admin route must use an approved CSRF dependency. The
release-file upload route uses `UploadCSRFProtectedAdminSession`, which performs the
request-size pre-check first. Same-origin JavaScript may send `X-CSRF-Token` so the
token can be verified before multipart form parsing.

## Private storage

The runtime layout is:

```text
STORAGE_ROOT/
├── software/
├── icons/
├── import/
├── temporary/
└── quarantine/

BACKUP_ROOT/
```

Original filenames are metadata only. Physical files receive a random UUID name
and shard path such as:

```text
7d/c7/7dc7f85a7db34e7198cb5510bc31e91a.exe
```

Storage operations reject traversal, absolute paths, NUL bytes, backslashes and
symlink escapes. Files moved into storage are regular files with mode `0640`.
Atomic movement requires temporary, quarantine and permanent directories to be
on the same filesystem.

See [Private storage foundation](docs/storage-foundation.md) for the complete
path policy.

## Release-file upload

From a release edit page, an administrator can upload one `.exe`, `.msi`, `.zip`
or `.7z` file. The pipeline performs:

```text
CSRF and request-size pre-check
→ bounded multipart spooling
→ application temporary copy in chunks
→ actual byte count + SHA-256 + magic sample
→ extension/signature assessment
→ atomic move to quarantine
→ optional scanner
→ short metadata transaction and audit
```

The browser MIME type is never trusted as the detected type. Unknown or mismatched
signatures stay in `quarantine`; infected files become `rejected`; a valid file
becomes `ready` but remains private in quarantine. A ready file is published only
after a fresh size/SHA-256 check and an atomic move into permanent storage. Published
files can then be authorized by the Phase 12 protected-download route.

See [Release-file upload pipeline](docs/upload-pipeline.md) for exact status,
scanner, transaction and residual-risk semantics.

## Release-file lifecycle

The private file detail page provides explicit, CSRF-protected actions:

```text
quarantine → ready or rejected
rejected → quarantine
ready → published / disabled / archived
published → disabled / archived
disabled or archived → ready
```

Publication requires a published parent release, published or hidden parent
software, a matching persisted magic-byte assessment and a scanner result of
`clean` or `unavailable`. The service recalculates SHA-256 before moving the file
from quarantine to permanent storage. If the metadata transaction fails after the
move, the file is moved back to quarantine.

Deletion is deliberately split:

- **Delete metadata** removes only the database row and preserves the physical file
  as an explicit orphan for later reconciliation.
- **Delete permanently** stages the physical file in private temporary storage,
  commits metadata deletion and then unlinks the staged file. A failed database
  transaction restores the original file.

Published files cannot be deleted directly; they must first be disabled or
archived. See [Release-file lifecycle](docs/file-lifecycle.md).

## Protected downloads

Published files are requested through:

```text
GET  /download/{public_uuid}/{safe_filename}
HEAD /download/{public_uuid}/{safe_filename}
```

FastAPI validates the exact filename, full `Software → Release → ReleaseFile`
status/visibility chain, administrator session for private content, permanent-storage
location and physical size. It returns an empty response with a safe
`X-Accel-Redirect`; Nginx serves the bytes from its `internal` location. Direct access
to `/protected-downloads/` is denied.

`GET` increments the aggregate and UTC daily counters after authorization and before
the internal redirect. This means an **authorized download start**, not confirmed
completion. `HEAD` performs the same access checks but never increments successful
counters. Nginx calculates the real `Content-Length` after the internal redirect and
handles byte ranges/resume.

The session cookie is root-scoped (`Path=/`) so an active administrator session can
authorize private files outside `/admin`. It remains `HttpOnly`, `SameSite=Lax` and
`Secure` in production.

See [Protected download delivery](docs/download-delivery.md).

## Public catalog

The public server-rendered interface now includes:

```text
GET /
GET /software
GET /search
GET /category/{category_slug}
GET /software/{software_slug}
GET /software/{software_slug}/releases
```

General listings include only `published + public` software. Unlisted and archived
entries require their direct slug, private entries require an administrator session,
and disabled entries remain unavailable. Category/tag facets are built only from
publicly listed records.

Search covers names, descriptions, developers, visible categories and tags. Input
is normalized to 2–100 characters, SQL wildcards are escaped and sorting supports
name, update date and public-file popularity. Templates receive immutable public
view models, so storage paths, internal filenames, scanner details and admin notes
are not available to Jinja.

Software pages show current version, changelog, release history, architecture,
package type, size, SHA-256, publication date and download counts. Download buttons
still pass through the Phase 12 authorization endpoint.

See [Public catalog and software pages](docs/public-catalog.md).

## Theme, accessibility and SEO

Every public, administration, login and error surface supports system, light and
dark themes. Explicit light/dark preferences use the `software-hub-theme`
`localStorage` key; system mode remains the no-JavaScript fallback. Navigation,
forms, search and downloads continue to work without JavaScript.

Public pages emit canonical, robots, Open Graph and Twitter metadata built from
`SOFTWARE_HUB_PUBLIC_BASE_URL`, never from the request Host header. `/sitemap.xml`
contains only indexable public pages and `/robots.txt` advertises that trusted
absolute URL. Search/filter duplicates and all private administration surfaces are
explicitly `noindex`.

The shared shells include skip links, focusable main landmarks, current-page
navigation, visible focus, accessible form errors, table captions/regions,
reduced-motion support and responsive layouts.

See [UI, accessibility and SEO hardening](docs/ui-accessibility-seo.md).


## Backup, restore and maintenance

Create and verify backups:

```bash
uv run python -m app.cli create-backup
uv run python -m app.cli list-backups
uv run python -m app.cli verify-backup --backup-id <BACKUP_ID>
```

Maintenance commands are dry-run by default. Destructive actions require the
operation flag and `--yes`:

```bash
uv run python -m app.cli cleanup-backups
uv run python -m app.cli cleanup-backups --apply --yes
uv run python -m app.cli verify-storage
uv run python -m app.cli find-orphan-files
uv run python -m app.cli find-orphan-files --delete --yes
uv run python -m app.cli recalculate-checksums
uv run python -m app.cli cleanup-temporary-files --apply --yes
uv run python -m app.cli show-system-status
```

Restore must run while the application is stopped:

```bash
uv run python -m app.cli restore-backup --backup-id <BACKUP_ID> --yes
```

See [Backup and restore runbook](BACKUP_RESTORE.md),
[Operations](OPERATIONS.md) and
[Phase 16 maintenance architecture](docs/maintenance-backup-reconciliation.md).


## Docker Compose deployment

The production package now contains two mandatory hardened images and an optional
Certbot profile:

```text
nginx (non-root, ports 8080/8443, TLS/static/rate limits/downloads)
→ internal Docker backend network
→ app (non-root, one Uvicorn worker, SQLite and private storage)
```

Local HTTP startup:

```bash
cp .env.example .env
./scripts/prepare-local.sh
SOFTWARE_HUB_UID=$(id -u) SOFTWARE_HUB_GID=$(id -g) \
  docker compose up --build
```

The default listener is `127.0.0.1:8080`. Production uses:

```bash
sudo ./scripts/prepare-host.sh
cp .env.production.example .env.production
# Configure secrets, domain and an admin WireGuard/IP allowlist.
docker compose --env-file .env.production \
  -f docker-compose.yml -f docker-compose.production.yml up -d --build
```

Both main containers use a read-only root filesystem, drop all capabilities,
forbid privilege escalation and write only to explicit bind mounts or bounded
`tmpfs`. The FastAPI service has no host port. Nginx mounts only permanent
published software and certificates read-only; it cannot access quarantine,
SQLite or backups.

See [Deployment runbook](DEPLOYMENT.md), [Security model](SECURITY.md) and
[Phase 17 container architecture](docs/container-deployment.md).

## Database commands

```bash
uv run alembic upgrade head
uv run alembic current
uv run alembic check
uv run alembic downgrade base
```

Revision `0001_phase3_baseline` establishes migration history. Revision
`0002_phase4_domain_schema` creates the complete MVP relational schema. Phases
5–19 do not change the schema.

## Quality commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uvx --from "bandit[toml]==1.9.4" bandit -c pyproject.toml -r app
uvx --from "pip-audit==2.10.1" pip-audit
```

Install Git hooks:

```bash
uv run pre-commit install
uv run pre-commit install --hook-type pre-push
```

## Testing and CI

The default regression suite is deterministic and does not require browser
binaries:

```bash
uv run pytest
```

Production-like browser tests are opt-in locally and mandatory in CI:

```bash
SOFTWARE_HUB_RUN_E2E=1 \
SOFTWARE_HUB_E2E_BROWSERS=chromium,firefox,webkit \
AXE_CORE_PATH="$PWD/node_modules/axe-core/axe.min.js" \
uv run --with "playwright==1.61.0" \
pytest -o addopts="" -m e2e tests/e2e -q
```

The CI pipeline separately blocks on formatting, lint, strict typing, tests,
Bandit, pip-audit, cross-browser Playwright/axe checks, Docker image builds,
Trivy scans and a running non-root Compose smoke test. See the
[test strategy](docs/test-strategy.md).

## Configuration

Settings use the `SOFTWARE_HUB_` prefix. See the [environment reference](docs/environment-variables.md) and `.env.example`. Production starts
only with strong separate secrets, HTTPS, trusted hosts, an absolute persistent
SQLite path and secure writable storage roots.

Important storage settings:

```text
SOFTWARE_HUB_STORAGE_ROOT
SOFTWARE_HUB_TEMPORARY_ROOT
SOFTWARE_HUB_QUARANTINE_ROOT
SOFTWARE_HUB_ICONS_ROOT
SOFTWARE_HUB_BACKUP_ROOT
SOFTWARE_HUB_BACKUP_RETENTION_COUNT
SOFTWARE_HUB_BACKUP_MIN_FREE_BYTES
SOFTWARE_HUB_STORAGE_MIN_FREE_BYTES
SOFTWARE_HUB_TEMPORARY_FILE_MAX_AGE_SECONDS
SOFTWARE_HUB_MAX_UPLOAD_SIZE
SOFTWARE_HUB_ALLOWED_EXTENSIONS
SOFTWARE_HUB_UPLOAD_CHUNK_SIZE
SOFTWARE_HUB_UPLOAD_MAGIC_SAMPLE_SIZE
SOFTWARE_HUB_CLAMAV_ENABLED
SOFTWARE_HUB_CLAMAV_COMMAND
SOFTWARE_HUB_CLAMAV_TIMEOUT_SECONDS
SOFTWARE_HUB_INTERNAL_DOWNLOAD_PREFIX
```

## Documentation

- [Documentation index](docs/README.md)
- [System architecture](ARCHITECTURE.md)
- [Release history](CHANGELOG.md)
- [Environment variable reference](docs/environment-variables.md)
- [Local development guide](docs/local-development.md)
- [Production acceptance runbook](docs/production-acceptance.md)
- [Release candidate evidence](docs/release-candidate.md)
- [Database foundation](docs/database-foundation.md)
- [Data model](docs/data-model.md)
- [Application layer](docs/application-layer.md)
- [Authentication and sessions](docs/authentication-sessions.md)
- [CSRF protection](docs/csrf-protection.md)
- [Administration catalog](docs/admin-catalog.md)
- [Private storage foundation](docs/storage-foundation.md)
- [Release-file upload pipeline](docs/upload-pipeline.md)
- [Release-file lifecycle](docs/file-lifecycle.md)
- [Protected download delivery](docs/download-delivery.md)
- [Public catalog and software pages](docs/public-catalog.md)
- [Phase 13 review](docs/phase-13-review.md)
- [UI, accessibility and SEO hardening](docs/ui-accessibility-seo.md)
- [Phase 14 review](docs/phase-14-review.md)
- [Operations, audit and health observability](docs/operations-observability.md)
- [Phase 15 review](docs/phase-15-review.md)
- [Backup and restore runbook](BACKUP_RESTORE.md)
- [Operations and maintenance](OPERATIONS.md)
- [Phase 16 maintenance architecture](docs/maintenance-backup-reconciliation.md)
- [Phase 16 review](docs/phase-16-review.md)
- [Deployment runbook](DEPLOYMENT.md)
- [Security model](SECURITY.md)
- [Container deployment architecture](docs/container-deployment.md)
- [Phase 17 review](docs/phase-17-review.md)
- [Test strategy and CI quality gates](docs/test-strategy.md)
- [Phase 18 review](docs/phase-18-review.md)
- [Phase 19 review](docs/phase-19-review.md)
- [Threat model](docs/threat-model.md)
- [Release checklist](docs/release-checklist.md)

## Lock-file verification note

`uv.lock` is committed and structurally validated for the Python 3.14 target.
The execution sandbox cannot download Python 3.14 or all locked artifacts, so a
full `uv sync --all-groups --locked` must run in network-enabled CI before merge.
