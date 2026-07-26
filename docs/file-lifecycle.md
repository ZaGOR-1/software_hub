# Release-file lifecycle

## Purpose

Phase 11 turns private quarantine metadata into an explicit operator-controlled
lifecycle. It does not add public downloads. Every physical operation stays inside
the configured private storage roots and every state-changing HTTP route requires
an authenticated administrator session plus session-bound CSRF.

## Physical storage states

A `ReleaseFile.relative_storage_path` is server-generated and may resolve in
exactly one of two roots:

```text
quarantine/<relative_storage_path>
software/<relative_storage_path>
```

The service rejects an action when the file is missing, is not a regular file,
uses a symlink path, or exists in both locations. Absolute paths are never stored
or rendered.

Expected normal placement:

| Lifecycle state | Expected area |
|---|---|
| `quarantine` | quarantine |
| `ready` | quarantine |
| `rejected` | quarantine |
| `published` | software |
| `disabled` | quarantine or software, depending on prior state |
| `archived` | quarantine or software, depending on prior state |

Restoring a disabled or archived file to `ready` moves content from permanent
software storage back to quarantine when necessary.

## Manual review

Administrators may perform these review transitions:

```text
quarantine → ready
quarantine → rejected
ready → rejected
rejected → quarantine
```

An infected file cannot be approved as `ready`. Manual approval of an unknown
magic signature does not bypass publication checks: publication still requires a
persisted signature assessment of `match`.

## Integrity verification

The `Verify SHA-256` action:

1. resolves the private physical file;
2. verifies regular-file and containment properties;
3. compares physical size with metadata;
4. recalculates SHA-256 with bounded memory;
5. records `file_verified` in the audit log.

The same size and checksum verification is mandatory immediately before
publication.

## Publication transaction

Publication is allowed only when:

- file status is `ready`;
- stored extension and detected MIME reconstruct a matching magic assessment;
- scanner status is `clean` or `unavailable`;
- parent release is `published`;
- parent software is `published` or `hidden`;
- the physical file is uniquely present in quarantine;
- size and SHA-256 still match metadata.

Sequence:

```text
preflight metadata and checksum validation
→ atomic quarantine → software move
→ short database transaction
   → lock/reload metadata
   → repeat state validation
   → set status published and published_at
   → append file_published audit event
→ commit
```

If the database transaction fails after the move, the service atomically restores
the file from software storage to quarantine. If that compensation itself fails,
the action fails closed with a high-severity log entry and an operator-visible
storage error.

## Disable, archive and restore

`disable` and `archive` change metadata only after proving that exactly one
physical file exists and its size matches metadata. They never delete bytes.

`restore` changes `disabled` or `archived` to `ready`. If the file is in permanent
software storage, it is first moved back to quarantine. A subsequent database
failure moves it back to software storage.

## Deletion policies

Published files cannot be deleted directly. They must first be disabled or
archived.

### Delete metadata only

Confirmation phrase:

```text
DELETE METADATA
```

This removes the `ReleaseFile` database row and intentionally preserves an
existing physical file. The result is an explicit orphan for later reconciliation.
The admin UI warns about this outcome. The audit event is
`file_metadata_deleted` and records whether bytes were preserved and in which
logical storage area, without recording an absolute path.

### Delete permanently

Confirmation phrase:

```text
DELETE FILE
```

Sequence:

```text
verify file and metadata
→ atomic move to temporary/deletions/<random>.delete
→ short database transaction
   → delete ReleaseFile metadata
   → append file_permanently_deleted audit event
→ commit
→ unlink staged regular file
→ fsync staging directory
```

If the database transaction fails, the staged file is atomically restored to its
original root and relative path. This avoids the common failure mode where
metadata survives but bytes have already been destroyed.

A final unlink failure after a successful database commit cannot be rolled back.
The service returns a storage error and emits a critical log. The inaccessible
staged file remains for operator cleanup rather than risking silent data loss.
Phase 16 reconciliation/maintenance tooling will formalize recovery of such
residual artifacts.

## Admin routes

```text
POST /admin/files/{id}/review/approve
POST /admin/files/{id}/review/reject
POST /admin/files/{id}/review/reopen
POST /admin/files/{id}/verify
POST /admin/files/{id}/publish
POST /admin/files/{id}/disable
POST /admin/files/{id}/archive
POST /admin/files/{id}/restore
POST /admin/files/{id}/delete-metadata
POST /admin/files/{id}/delete-permanently
```

All are POST-only, authenticated, session-CSRF protected and covered by the route
inventory security test.

## Audit actions

```text
file_reviewed
file_verified
file_published
file_disabled
file_archived
file_restored
file_metadata_deleted
file_permanently_deleted
```

Audit metadata contains only safe identifiers, status transitions, logical
storage area, release ID and non-sensitive size information.

## Public URL preview

The private detail page displays the future canonical public URL based on
`PUBLIC_BASE_URL`, public UUID and encoded display filename. It is informational
only in Phase 11. The public endpoint, authorization chain, statistics and
`X-Accel-Redirect` delivery are implemented in Phase 12.

## Residual risks

- SQLite and filesystem cannot participate in one true cross-resource ACID
  transaction; compensation narrows but cannot eliminate crash windows.
- A metadata-only delete intentionally creates an orphan.
- A crash after database commit but before staged unlink may leave an inaccessible
  deletion artifact.
- Scanner `unavailable` is accepted because antivirus remains optional for MVP.
- A trusted administrator can approve a quarantined unknown file as `ready`, but
  cannot publish it until the persisted signature assessment is a match.
