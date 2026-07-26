# Phase 16 maintenance architecture

Phase 16 adds two application services and expands the CLI. It does not add a
public route and does not change the database schema.

## BackupService

Responsibilities:

- SQLite online backup API;
- storage/config copy without following symlinks;
- deterministic versioned manifest with application and Alembic revisions;
- SHA-256 and SQLite integrity verification;
- atomic publication of completed backup directories;
- exclusive backup/restore lock;
- count-based retention with dry-run;
- pre-restore safety backup;
- staged database/storage replacement and rollback;
- migrations and post-restore integrity verification;
- safe audit events.

The backup directory is the artifact. No untrusted tar extraction is required,
which avoids archive path traversal and decompression-bomb risk during restore.

## ReconciliationService

The read-only verification pass detects:

- metadata without a physical file;
- one relative path present in both quarantine and permanent storage;
- status/storage-area mismatch;
- persisted size mismatch;
- SHA-256 mismatch;
- physical files with no ReleaseFile metadata;
- symlinks or non-regular unsafe entries.

Absolute paths are never included in CLI JSON output. Destructive orphan cleanup
uses the existing private deletion-staging flow. Checksum updates are dry-run by
default and protect published files unless the operator explicitly includes them.

## Transaction boundaries

Large copies and hashes occur outside database transactions. Only audit writes and
checksum metadata updates use short transactions. Restore runs with the app stopped
and uses filesystem staging before replacing live paths.


## Failure model

Completed backups are immutable directory artifacts. Temporary backup directories
are removed after handled failures, while a completed directory is visible only
after verification and atomic publication. The operation lock intentionally fails
closed; after an unclean host/process crash, an operator may remove a stale lock
only after confirming that no backup or restore process is alive.
