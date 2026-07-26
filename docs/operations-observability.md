# Operations, audit and health observability

Phase 15 adds bounded operational visibility without introducing an external
metrics stack or exposing infrastructure details publicly.

## Public readiness endpoint

`GET /health` checks four components:

```json
{
  "status": "ok",
  "service": "software-hub",
  "version": "1.0.0-rc.3",
  "checks": {
    "application": "ok",
    "database": "ok",
    "storage": "ok",
    "disk": "ok"
  }
}
```

The response deliberately contains no database URL, SQLite path, storage path,
free-space byte count, exception text or backup metadata. A failed database,
storage or disk-reserve check returns generic HTTP `503` through the existing
safe error envelope.

The storage check confirms that every application-owned directory still exists,
is a real directory rather than a symbolic link and is accessible to the
process. The disk check uses `SOFTWARE_HUB_STORAGE_MIN_FREE_BYTES` as the
readiness threshold.

## Administration dashboard

The authenticated dashboard now shows bounded counters for:

- programs, releases, files, categories and tags;
- total authorized download starts;
- authorized and blocked download attempts for the current UTC day;
- files in quarantine/review states;
- disabled files;
- database and storage readiness;
- disk free space, configured reserve and utilization percentage;
- the newest recognized backup manifest;
- ten recent audit events.

The dashboard never renders physical storage paths, the database URL, session
identifiers, raw IP addresses or scanner diagnostics.

## Backup manifest discovery

Phase 15 does not create backups. It only recognizes the future Phase 16 manifest
contract:

```text
BACKUP_ROOT/
└── software-hub-backup-<timestamp>/
    └── manifest.json
```

A regular root-level file named
`software-hub-backup-<timestamp>.manifest.json` is also recognized. Symlinks are
ignored. Until Phase 16 writes a manifest, the dashboard explicitly reports that
no confirmed manifest has been found.

## Audit metadata policy

Audit action identifiers are centralized in `AuditAction`. The audit service
accepts only an explicit set of flat metadata keys used by current workflows.
Unknown keys and security-sensitive names are dropped. Values are restricted to
bounded JSON scalars or short scalar sequences. Strings are truncated to 256
characters.

The allowlist excludes physical paths, filenames, passwords, cookies, session
values, CSRF material, authorization headers and arbitrary nested mappings.

## Audit browser

`GET /admin/audit` requires an active administrator session and provides:

- action filter;
- success/failure filter;
- administrator filter;
- entity-type filter;
- inclusive UTC date range;
- 50-row bounded pagination;
- eagerly loaded usernames;
- escaped allowlisted metadata;
- request ID correlation.

Invalid dates produce a server-rendered `422` form error without stack traces or
submitted secrets. Filters remain SQLAlchemy bind parameters.

## Structured events

Existing request-completion logs continue to include request ID, method, route,
status and duration. Phase 15 adds bounded events for unhealthy system snapshots,
failed disk checks and failed public health checks. These events contain only
component names and safe status values.

## Operational limitations

- No Prometheus, Grafana or external alert manager is introduced in the MVP.
- Download completion is still not inferred; statistics count authorized GET
  starts as defined in Phase 12.
- Backup creation, checksum verification, restore and retention are Phase 16.
- Audit retention cleanup is not automatic yet; Phase 16 operations tooling will
  own retention and maintenance commands.
