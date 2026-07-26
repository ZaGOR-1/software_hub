# Backup and restore runbook

Software Hub backups are private, verified directories stored below
`SOFTWARE_HUB_BACKUP_ROOT`. Backups are not served by Nginx and must also be
copied to another physical disk or host.

## Backup contents

Each backup has the form:

```text
software-hub-backup-YYYYMMDDTHHMMSSffffffZ-xxxxxxxx/
├── manifest.json
├── manifest.sha256
├── database/software-hub.sqlite3
├── storage/
│   ├── software/
│   ├── quarantine/
│   ├── icons/
│   └── import/
└── config/
    ├── .env.example
    ├── alembic.ini
    ├── pyproject.toml
    └── nginx/
```

Temporary upload files are intentionally excluded. The live SQLite file is
copied through `sqlite3.Connection.backup()`, converted to a standalone DELETE
journal database and checked with `PRAGMA integrity_check`. Every copied regular
file has a size and SHA-256 entry in the manifest. The manifest also records the
application version and Alembic database revision. `manifest.sha256` protects the
manifest itself.

## Create and verify

Run the application migrations first, then stop no services for backup creation:
SQLite online backup supports concurrent readers and short writers.

```bash
uv run python -m app.cli create-backup
uv run python -m app.cli list-backups
uv run python -m app.cli verify-backup --backup-id <BACKUP_ID>
```

Creation uses a private temporary directory and publishes the backup with an
atomic rename only after complete verification. An exclusive lock prevents two
backup/restore operations from running together. After an unclean process or host
crash, a stale `.software-hub-backup.lock` may remain. Remove it only after verifying
that no backup or restore process is active.

## Retention

The default policy keeps the newest 14 verified backups. Invalid or unknown
folders are never deleted automatically.

```bash
# Dry-run
uv run python -m app.cli cleanup-backups

# Apply the reported deletion set
uv run python -m app.cli cleanup-backups --apply --yes
```

Configure:

```text
SOFTWARE_HUB_BACKUP_RETENTION_COUNT=14
SOFTWARE_HUB_BACKUP_MIN_FREE_BYTES=1073741824
```

## Restore procedure

Restore is a maintenance-window operation. Stop the application and Nginx app
traffic first so no process holds the SQLite database or writes storage.

```text
1. Stop app containers/processes.
2. Copy the selected backup to BACKUP_ROOT.
3. Verify the backup.
4. Restore with explicit confirmation.
5. Start the application.
6. Check migrations and /health.
7. Test one public page and one protected download.
8. Create and copy a new post-restore backup offsite.
```

Commands:

```bash
uv run python -m app.cli verify-backup --backup-id <BACKUP_ID>
uv run python -m app.cli restore-backup --backup-id <BACKUP_ID> --yes
uv run alembic current
uv run alembic check
```

By default restore first creates a verified safety backup of the current state.
The selected database and storage are copied into sibling staging paths, then
replaced on their own filesystems. If replacement or migration fails, the old
paths are restored. The restored SQLite database receives `alembic upgrade head`
and a final integrity check before success is reported.

For containers, `${SOFTWARE_HUB_DATA_ROOT}/application` must be mounted once at
`/srv/software-hub`. Do not mount `database`, `storage` and `backups` as separate
mount points: Linux cannot atomically rename a mount point during rollback.
Certificate and Certbot directories remain outside `application/`.

Only during a separately verified emergency may the safety backup be disabled:

```bash
uv run python -m app.cli restore-backup \
  --backup-id <BACKUP_ID> --no-safety-backup --yes
```

## Clean-server disaster recovery

```text
clean Ubuntu Server
→ install Docker/uv and project release
→ restore production .env/secrets separately
→ create required parent directories and ownership
→ copy backup into BACKUP_ROOT
→ run verify-backup
→ run restore-backup --yes
→ run alembic current/check
→ start services
→ check /health
→ test admin login and protected download
→ copy a new backup offsite
```

Secrets are not included in backups. Restore them from the separate secret
management process. Never restore `.env`, TLS private keys or credentials from a
public repository.

## Recovery limitations

- A process crash at the exact filesystem replacement boundary is mitigated by
  the automatic safety backup, but operators must still test disaster recovery.
- Backups on the same disk do not protect against disk loss.
- Completion statistics cannot prove a client finished a download.
- Restore must not run concurrently with the application.

## Release-candidate restore evidence

The repository includes `scripts/rehearse-release-candidate.sh`, which creates a
clean temporary installation, bootstraps an administrator, produces and verifies
an online backup, mutates SQLite, restores the snapshot and validates health and
storage reconciliation. This is a deterministic code-level rehearsal.

Production acceptance additionally requires copying a verified backup to a
separate VM or host and restoring it there. A restore into another directory on
the same production disk does not demonstrate disaster recovery.
