# Software Hub architecture

**Release candidate:** `1.0.0-rc.1`
**Architecture style:** modular monolith
**Primary domain:** `https://software.hotzagor.tech`

This document describes the architecture that is actually implemented in the
repository. It is the operational overview for maintainers; lower-level design
notes remain in `docs/ADR`, the component documents and the threat model.

## 1. System context

```text
Anonymous browser                    Administrator browser
        │                                      │
        └──────────── HTTPS ───────────────────┘
                           │
                           ▼
                     Non-root Nginx
             ┌─────────────┼──────────────┐
             │             │              │
        static assets   reverse proxy   internal files
             │             │              │
             │             ▼              ▼
             │        FastAPI app     permanent storage
             │             │
             │       ┌─────┴──────────┐
             │       ▼                ▼
             │    SQLite       private filesystem
             │                 temp/quarantine/icons
             │
             └── security headers, rate limits, TLS
```

The application is deliberately a single deployable unit. Nginx is a separate
edge process because it terminates TLS, applies network policy and serves large
files without routing their bytes through Python.

## 2. Runtime components

### Nginx

Nginx owns the public network boundary:

- redirects HTTP to HTTPS;
- terminates TLS 1.2/1.3;
- applies security headers and request limits;
- restricts `/admin` by a fail-closed include in production;
- serves versioned static assets;
- proxies dynamic requests to one Uvicorn worker;
- serves approved binaries through an `internal` location after receiving an
  `X-Accel-Redirect` response from FastAPI;
- never mounts SQLite, quarantine or backups.

### FastAPI application

The application is assembled by `app.main:create_app`. It provides:

- public catalog and download authorization;
- administrator authentication and server-side sessions;
- CSRF-protected server-rendered administration forms;
- catalog, release and file lifecycle services;
- streaming upload validation and quarantine;
- audit, health, backup, restore and reconciliation commands.

The application container runs as UID/GID `10001`, has a read-only root
filesystem and receives write access only to declared persistent mounts.

### SQLite

SQLite is the MVP metadata store. Every connection enables:

```text
foreign_keys = ON
journal_mode = WAL
busy_timeout = configured value
synchronous = configured mode
```

The design assumes one application instance and one Uvicorn worker. Transactions
remain short; uploaded and downloaded bytes are never stored in SQLite.

### Private filesystem

The host data root defaults to `/srv/software-hub`:

```text
/srv/software-hub/
├── database/
├── storage/
│   ├── software/
│   ├── icons/
│   ├── import/
│   ├── temporary/
│   └── quarantine/
├── backups/
├── certbot/
└── letsencrypt/
```

Physical filenames are generated UUID values with sharded directories. Original
filenames exist only as metadata. Paths are containment-checked and symlink
components are rejected.

## 3. Application layers

```text
HTTP router
  → application service
    → repository / storage service
      → SQLite / filesystem
```

### Routers

`app/routers` owns HTTP concerns only: parsing, dependencies, responses,
templates and redirects. Routers do not directly commit ORM objects.

### Services

`app/services` owns use cases and transaction boundaries. Important services
include authentication, sessions, software, releases, release files, downloads,
audit, system status, backup and reconciliation.

### Repositories

`app/repositories` contains parameterized SQLAlchemy queries, bounded pagination,
eager-loading plans and persistence operations. Repositories never own a commit.

### Storage

`app/storage` handles names, paths, signatures, hashing, scanner integration,
atomic moves, disk checks and cleanup. It never accepts a user-supplied physical
path.

### Presentation models

Public templates receive immutable view models rather than ORM graphs. This
prevents private storage fields, scanner diagnostics and administrative notes
from becoming accidentally renderable.

## 4. Core data model

```text
User ──< UserSession
  └────< AuditLog

Category ──< Software >── Tag
                 │
                 └──< Release
                         │
                         └──< ReleaseFile
                                  │
                                  └──< DownloadStat
```

The primary publication hierarchy is:

```text
Software → Release → ReleaseFile
```

A download is allowed only when the complete hierarchy satisfies its status and
visibility policy. A public UUID identifies a release file; no physical path is
part of the public contract.

## 5. Critical flows

### Administrator login

```text
GET login
→ signed pre-auth CSRF token
→ POST credentials
→ generic authentication response
→ Argon2id verification
→ failed-attempt lockout policy
→ opaque server-side session
→ secure cookie
→ audit event
```

Only a hash of the session token is stored in SQLite. Login rotates the session;
logout and password changes revoke server-side records.

### Upload

```text
admin + session CSRF
→ bounded multipart parser
→ chunked copy to private temporary file
→ actual-size enforcement
→ filename normalization
→ extension and magic-byte assessment
→ SHA-256
→ duplicate lookup
→ optional malware scanner
→ atomic temporary-to-quarantine move
→ short metadata transaction
```

Unknown or scanner-error files remain in quarantine. Infected files are rejected.
Archives are not extracted and Windows binaries are never executed.

### Publish

```text
manual review
→ physical size and SHA-256 recheck
→ parent-state validation
→ atomic quarantine-to-software move
→ short database transaction
→ compensation move on transaction failure
→ audit event
```

### Download

```text
GET/HEAD public UUID
→ verify Software, Release and ReleaseFile
→ verify visibility and physical file
→ update bounded aggregate statistics for GET
→ empty FastAPI response with X-Accel-Redirect
→ Nginx serves bytes and Range requests
```

### Backup and restore

A backup uses the SQLite online backup API, copies persistent storage, records
all sizes and SHA-256 values, performs SQLite integrity checking and publishes a
timestamped directory atomically. Restore verifies the complete manifest before
using staged replacement and compensation rollback.

## 6. Trust boundaries and security controls

The primary boundaries are Internet→Nginx, Nginx→FastAPI, browser→admin session,
uploaded bytes→quarantine, quarantine→published storage and host→offsite backup.

Controls include:

- TLS and trusted-host validation;
- proxy-header trust restricted to the Nginx network;
- Argon2id, lockout and opaque server-side sessions;
- pre-auth and session-bound CSRF tokens;
- Jinja autoescape and a CSP without `unsafe-inline`;
- SQLAlchemy expressions and bounded pagination;
- extension plus signature validation;
- containment and symlink checks;
- non-root containers and minimal mounts;
- append-oriented audit events with metadata allowlists;
- tested backup, restore and reconciliation workflows.

See [SECURITY.md](SECURITY.md) and [the threat model](docs/threat-model.md).

## 7. Deployment topology

The supported production topology is one Ubuntu Server VPS or one isolated
Ubuntu Server VM in Proxmox:

```text
Internet
  → host firewall 80/443
    → Docker Compose Nginx
      → private backend network
        → one FastAPI/Uvicorn container
```

Recommended starting resources are 2 vCPU, 2–4 GiB RAM, a 20–30 GiB system disk
and a separate persistent volume for software files. Proxmox management must not
be exposed publicly; the VM should use a DMZ or isolated VLAN when possible.

## 8. Scaling boundaries

The MVP intentionally does not include Redis, Celery, PostgreSQL, S3, CDN,
Kubernetes or multiple application instances.

A move beyond the current topology should be triggered by measured need:

- PostgreSQL when concurrent write load or multiple application instances are
  required;
- object storage when one host filesystem is no longer sufficient;
- CDN when public download geography or bandwidth justifies it;
- background workers when tasks become too expensive for bounded request/CLI
  execution.

Business services and repositories are kept separate from SQLite-specific setup
so these changes do not require replacing the HTTP and domain layers.

## 9. Source map

| Area | Main location |
|---|---|
| Application factory and core | `app/main.py`, `app/core` |
| ORM and migrations | `app/models`, `app/database`, `alembic` |
| Use cases | `app/services` |
| Persistence queries | `app/repositories` |
| Filesystem safety | `app/storage` |
| HTTP routes | `app/routers` |
| Server-rendered UI | `app/templates`, `app/static` |
| Edge proxy | `nginx` |
| Containers | `Dockerfile`, `docker`, `docker-compose*.yml` |
| Operations | `app/cli.py`, `scripts`, root runbooks |
| Tests and quality gates | `tests`, `.github/workflows` |

## 10. Architecture invariants

A release must preserve these rules:

1. User input never becomes a physical path.
2. Uploaded bytes remain private until explicit publication.
3. Python never streams approved large downloads.
4. Routers do not own business transactions.
5. Repositories do not commit transactions.
6. Public templates do not receive private ORM fields.
7. Production secrets are never generated at container startup.
8. A backup is not accepted until manifest, file checksums and SQLite integrity
   all pass.
9. Production `/admin` access remains fail-closed until an explicit network
   policy is mounted.
10. One SQLite deployment uses one Uvicorn worker and one application instance.
