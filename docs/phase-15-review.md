# Phase 15 review — audit, dashboard, health and observability

## Status

Phase 15 is complete. The application now exposes safe public readiness checks
and an authenticated operational dashboard and audit browser.

## Implemented

- centralized audit action identifiers, including Phase 16 backup actions;
- strict flat allowlist and bounded value policy for audit metadata;
- eager audit user loading;
- action, result, user, entity and UTC date filters;
- 50-row audit pagination;
- protected `/admin/audit` UI;
- catalog, download, quarantine and disabled-file dashboard metrics;
- database and private-storage state;
- disk reserve and utilization state;
- safe backup-manifest discovery;
- recent audit activity;
- public application/database/storage/disk readiness checks;
- generic `503` responses with no infrastructure detail;
- structured unhealthy-component log events.

## Database impact

No schema change was needed. The current Alembic head remains:

```text
0002_phase4_domain_schema
```

## Automated acceptance

```text
pytest:                         460 passed
branch coverage:               94.10%
warnings:                      0
Python compileall:             passed
Jinja template compilation:    36 passed
Python lines over 100 chars:   0
trailing whitespace:           0
TOML/YAML parsing:             passed
JavaScript syntax:             passed
Node theme runtime:            passed
Alembic upgrade/current/check: passed
Alembic downgrade/re-upgrade:  passed
Alembic schema drift:          absent
uv export --frozen --no-dev:   passed
real Uvicorn Phase 15 smoke:   passed
```

The test suite covers:

- 120-row filtered audit pagination;
- user eager loading after the SQLAlchemy session closes;
- audit metadata allowlist, truncation and secret/path rejection;
- invalid date form handling;
- public health success envelope;
- database failure;
- missing storage directory;
- disk space below the configured reserve;
- empty dashboard state;
- download/quarantine/disabled metrics;
- recognized backup manifest;
- absence of physical paths and capacity details in public responses.

## Real HTTP smoke

A real Uvicorn process was started against a migrated file-backed SQLite database
and private temporary storage. The following flow passed:

```text
GET /health
→ GET /admin/login
→ POST /admin/login
→ GET /admin
→ GET /admin/audit
```

The audit page displayed the successful login event, while the dashboard showed
healthy database, storage and disk states.

## Security notes

- Public readiness output contains status names only.
- Dashboard details require an authenticated server-side session.
- Audit metadata cannot store arbitrary dictionaries or filesystem paths.
- Audit filters use SQLAlchemy expressions and bound values.
- Backup discovery ignores symlinks and does not expose manifest names or paths.
- Health failures use the existing generic production-safe error envelope.

## Environment limitations

The local runtime is Python 3.13.5; the project target remains Python 3.14.
Ruff, mypy, Bandit and pip-audit executables are not installed in the offline
sandbox, so those checks remain mandatory GitHub Actions quality gates.
