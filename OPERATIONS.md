# Operations and maintenance

## Daily checks

```bash
uv run python -m app.cli show-system-status
uv run python -m app.cli verify-storage
uv run python -m app.cli cleanup-temporary-files
```

`verify-storage` is read-only by default and compares all ReleaseFile metadata
with quarantine/permanent storage. It reports missing files, duplicate physical
locations, wrong storage areas, size/checksum mismatches, unsafe entries and
orphans without printing absolute paths.

## Maintenance commands

```bash
create-admin
change-admin-password
revoke-sessions
cleanup-expired-sessions
cleanup-temporary-files
create-backup
list-backups
verify-backup
cleanup-backups
restore-backup
verify-storage
recalculate-checksums
find-orphan-files
show-system-status
```

All commands return non-zero on failure. Passwords are read from a protected
environment variable or an interactive hidden prompt, never a command argument.

### Temporary cleanup

```bash
# Dry-run
uv run python -m app.cli cleanup-temporary-files

# Delete only stale UUID-generated *.upload files
uv run python -m app.cli cleanup-temporary-files --apply --yes
```

### Orphan files

```bash
# List only
uv run python -m app.cli find-orphan-files

# Stage and delete only the exact reported unreferenced regular files
uv run python -m app.cli find-orphan-files --delete --yes
```

No metadata row is changed by orphan cleanup.

### Checksum recalculation

Checksum recalculation is intentionally dry-run first. Updating checksum metadata
can legitimize modified content, so published files are skipped unless a second
explicit flag is supplied.

```bash
uv run python -m app.cli recalculate-checksums
uv run python -m app.cli recalculate-checksums --apply --yes
uv run python -m app.cli recalculate-checksums \
  --apply --include-published --yes
```

The apply pass verifies that the file size, modification timestamp and checksum
have not changed between analysis and the short database transaction.

### Stale backup lock

Backup and restore operations use `BACKUP_ROOT/.software-hub-backup.lock`. If a
process or host crashes, first verify that no maintenance process is running. Only
then remove the stale lock file and rerun `verify-backup` before continuing. Never
remove the lock merely to bypass an active operation.

## Scheduling

Example root-owned systemd timer or cron entry:

```cron
15 3 * * * cd /opt/software-hub && ./scripts/backup.sh
45 3 * * * cd /opt/software-hub && python -m app.cli cleanup-expired-sessions
15 4 * * * cd /opt/software-hub && python -m app.cli cleanup-temporary-files --apply --yes
```

Use a dedicated service account, a protected environment file with mode `0600`,
and Docker/virtual-machine logs with rotation. Copy successful backups offsite.

## Common failures

### `/health` returns 503

Run `show-system-status`, then check database access, storage writability and the
configured disk reserve. The public health body intentionally does not disclose
paths or free-byte values; use the authenticated dashboard or CLI for detail.

### Nginx is healthy but downloads fail

Verify that the file is still `published`, the complete parent hierarchy is
available, the permanent file exists and Nginx has a read-only mount for
`storage/software`. Direct access to `/protected-downloads/` must continue to
return `404`.

### Application container fails at startup

Inspect configuration validation first. Common causes are weak/missing secrets,
a non-HTTPS production origin, wildcard trusted hosts, overlapping storage and
backup roots, incorrect bind-mount ownership or unavailable migrations.

### Certificate renewal fails

Check DNS, port 80 reachability, Certbot webroot mounts and certificate-directory
permissions. Do not disable HTTPS or HSTS as a workaround. Repair renewal and
reload Nginx only after `certbot renew` succeeds.

### Disk reserve blocks uploads or backup

Free space by applying reviewed retention and temporary cleanup. Never delete
quarantine, permanent files or backup folders manually; run reconciliation and
verified retention commands.

## Certificate and disk monitoring

At minimum, monitor:

- `/health` from outside the host;
- filesystem usage and configured reserve;
- last verified backup age;
- TLS certificate expiry and renewal exit status;
- container restart count;
- repeated login failures and critical storage/backup log events.

A warning should fire before the configured disk reserve is reached and at least
30 days before certificate expiry. Alert delivery is infrastructure-specific and
is not implemented inside the MVP application.
