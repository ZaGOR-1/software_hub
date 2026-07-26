# Database foundation

This document describes the SQLite and SQLAlchemy infrastructure introduced in
Phase 3. Domain tables are intentionally deferred to Phase 4.

## Runtime ownership

The FastAPI application factory creates one `Database` object per process. It
owns one SQLAlchemy engine and one configured `sessionmaker`. The object is
stored at `app.state.database` and disposed during application shutdown.

The production MVP uses one application process and one Uvicorn worker. Nginx
will serve static files and protected downloads, so application workers do not
need to scale file transfer throughput.

## SQLite connection policy

Every SQLite DB-API connection receives the following PRAGMAs:

```text
PRAGMA foreign_keys=ON
PRAGMA journal_mode=WAL
PRAGMA busy_timeout=<configured milliseconds>
PRAGMA synchronous=<configured mode>
```

Defaults:

```text
busy_timeout = 5000 ms
synchronous = NORMAL
```

`check_same_thread` is disabled because SQLAlchemy controls connection checkout
and FastAPI may execute synchronous dependencies in worker threads. In-memory
databases use `StaticPool` so tests share one database connection safely.

## Session and transaction policy

- A SQLAlchemy `Session` is short-lived and never global.
- Request handlers receive sessions through `get_db_session`.
- The dependency closes the session after the request.
- It does **not** auto-commit.
- Application services define transaction boundaries.
- `Database.transaction()` commits on successful context exit and rolls back on
  an exception.
- File streaming, hashing, malware scanning and other long operations must occur
  outside database transactions.
- A transaction should contain only the minimum metadata reads and writes needed
  to preserve a business invariant.

This policy prevents upload duration from holding SQLite write locks.

## Date and time policy

Application datetimes are timezone-aware and normalized to UTC. `UTCDateTime`
converts aware values to naive UTC for SQLite storage and restores an explicit
UTC timezone when values are read. Naive application values are rejected.

## Alembic policy

The migration environment imports the application metadata and uses the same
engine hardening as normal runtime connections. It supports:

- online migrations;
- offline SQL generation;
- type and server-default comparison;
- SQLite batch rendering;
- programmatic upgrade, downgrade and revision inspection for tests and future
  maintenance commands.

Revision `0001_phase3_baseline` intentionally creates no domain tables. It
establishes the migration lineage before Phase 4 introduces the complete model.

### Commands

```bash
uv run alembic upgrade head
uv run alembic current
uv run alembic downgrade base
uv run alembic check
```

A production deployment must back up the database before applying migrations.
Destructive migrations require an explicit, tested rollback or restore plan.

## Health semantics

`GET /health` is a readiness endpoint. It executes `SELECT 1` through the
application-owned engine.

Healthy response:

```json
{
  "status": "ok",
  "service": "software-hub",
  "version": "1.0.0-rc.1",
  "checks": {
    "database": "ok"
  }
}
```

If SQLite cannot be opened, the endpoint returns a safe `503` response. The
public response and application warning omit the physical database path and
underlying driver message.

## Configuration

```text
SOFTWARE_HUB_DATABASE_URL
SOFTWARE_HUB_DATABASE_ECHO
SOFTWARE_HUB_SQLITE_BUSY_TIMEOUT_MS
SOFTWARE_HUB_SQLITE_SYNCHRONOUS_MODE
```

Only SQLite URLs are accepted in the MVP. Production requires an absolute path
to a persistent database file. Relative paths and in-memory databases are
allowed only outside production.
