# Private storage foundation — Phase 9

## Scope

Phase 9 introduces the filesystem security boundary used later by icon upload,
ReleaseFile quarantine, publication, downloads, backup and reconciliation. It
does not accept HTTP uploads and does not expose any stored file publicly.

The application now validates the private storage layout during FastAPI
lifespan startup. Startup fails before serving requests when a required path is
missing and cannot be created, is a symbolic link, is not writable, cannot be
permission-hardened, or does not have the configured free-space reserve.

## Layout

The settings-backed layout is:

```text
STORAGE_ROOT/
├── software/       permanent binaries; private until Nginx internal delivery
├── icons/          software icons
├── import/         operator-controlled future import staging
├── temporary/      incomplete streaming uploads
└── quarantine/     validated but unpublished files

BACKUP_ROOT/         deliberately outside STORAGE_ROOT
```

`software` and `import` are derived from `STORAGE_ROOT`. `temporary`,
`quarantine` and `icons` are explicit settings but must be distinct descendants
of `STORAGE_ROOT`. `BACKUP_ROOT` must remain outside it so a future Nginx
storage mount cannot accidentally expose backups.

The application creates and probes all seven required directories. Directory
mode is normalized to `0750`. Stored regular files are normalized to `0640`;
executable, set-id and world-access bits are removed. Directory execute bits
remain necessary for traversal and do not permit executing uploaded binaries.

## Physical naming

Administrator filenames never become physical paths. The flow is:

```text
"My Useful Tool 2.0.exe"
→ normalized metadata: "My Useful Tool 2.0.exe"
→ extension: .exe
→ internal filename: 7dc7...e91a.exe
→ relative path: 7d/c7/7dc7...e91a.exe
```

The internal filename is a random 128-bit UUID in lowercase hexadecimal form.
Two-level sharding avoids very large single directories. Quarantine and
permanent storage use the same relative path so publication can perform a
same-filesystem atomic rename.

Temporary files use an independent UUID and the exact suffix `.upload`:

```text
6bb6...70c1.upload
```

Only this generated pattern is eligible for automated temporary cleanup.

## Filename policy

Original names are metadata only, but are still normalized defensively for
safe display and future `Content-Disposition` use.

The validator:

- applies Unicode NFKC normalization;
- trims leading whitespace but rejects trailing spaces or dots;
- rejects empty and hidden names;
- rejects `/`, `\\`, NUL and control characters;
- rejects bidi and invisible format controls;
- rejects Windows device names such as `CON`, `NUL`, `COM1` and `LPT1`;
- enforces both 255-character and 255-byte UTF-8 bounds;
- requires the configured final extension allowlist;
- rejects deceptive inner extensions such as `invoice.pdf.exe`,
  `installer.exe.zip` and `script.ps1.zip`;
- permits numeric version suffixes such as `7zip.24.09.exe`.

Extension and magic-byte validation remain separate. Phase 10 will require
both; Phase 9 intentionally does not claim that an allowed filename proves file
content.

## Path containment

All filesystem operations start with an already configured root and a relative
server-generated path. `safe_resolve()` rejects:

- absolute paths;
- empty, `.` or `..` components;
- NUL bytes;
- backslashes, including Windows traversal syntax;
- resolved paths outside the configured root;
- optionally, every symlink component.

This covers plain, URL-decoded and cross-platform traversal payloads. Public or
form input is never accepted as an absolute or relative physical path.

Required storage roots and created shard directories cannot be symlinks.
Filesystem bind mounts remain supported because they appear as real
directories, not symbolic links.

## Startup readiness

`StorageManager.initialize()` performs:

1. layout creation;
2. symlink and directory-type validation;
3. mode normalization to `0750`;
4. an exclusive create/write/fsync/delete probe in every directory;
5. a disk-capacity check for `STORAGE_MIN_FREE_BYTES`;
6. process-level registration in `app.state.storage`.

The writable probe uses a random private name and is deleted immediately. No
configured physical path is emitted to a public error response.

Current settings:

```text
SOFTWARE_HUB_STORAGE_ROOT
SOFTWARE_HUB_TEMPORARY_ROOT
SOFTWARE_HUB_QUARANTINE_ROOT
SOFTWARE_HUB_ICONS_ROOT
SOFTWARE_HUB_BACKUP_ROOT
SOFTWARE_HUB_STORAGE_MIN_FREE_BYTES
SOFTWARE_HUB_TEMPORARY_FILE_MAX_AGE_SECONDS
SOFTWARE_HUB_MAX_UPLOAD_SIZE
SOFTWARE_HUB_ALLOWED_EXTENSIONS
```

The default reserve is 1 GiB. It is configurable because a small development
machine may use a lower value, while production can reserve substantially more.

## Disk-space guard

`ensure_free_space()` accepts the bytes required by one planned operation and
a reserve that must remain afterward:

```text
free - required >= reserve
```

It fails before file streaming or movement when the operation cannot satisfy
the reserve. Phase 10 will call this before and during upload processing where
appropriate; Nginx and application upload limits remain independent controls.

## Atomic move policy

`atomic_move()` accepts source and destination roots plus relative paths. It:

- validates containment;
- rejects symlinks and non-regular source files;
- refuses an existing destination;
- creates private shard parents;
- verifies source and destination are on the same filesystem;
- changes source mode to `0640`;
- fsyncs file contents;
- moves with `os.replace()`;
- fsyncs the destination directory.

The server-generated UUID destination makes a collision extremely unlikely,
but an existing path is still treated as an error. Cross-device copy fallback
is intentionally forbidden because it would not provide the same atomicity.
Production deployment must keep temporary, quarantine and permanent storage on
the same filesystem when the upload workflow relies on atomic rename.

## Temporary cleanup

Cleanup is conservative and dry-run by default. It recursively examines the
configured temporary root without following directory symlinks and selects
only:

- regular files;
- with a lowercase 32-hex UUID name;
- with the `.upload` suffix;
- older than `TEMPORARY_FILE_MAX_AGE_SECONDS`.

Manual files, fresh files, symlinks, directories and nonmatching names are
skipped. The report contains counts and reclaimed bytes, not physical paths.
The maintenance CLI command is intentionally deferred to Phase 16; the tested
manager method is already available for it.

## Application boundaries

Phase 9 adds `app/storage/` as an infrastructure layer. It does not update
ReleaseFile metadata, create transactions, parse multipart bodies, calculate
SHA-256, inspect magic bytes, scan malware or publish downloads.

Those responsibilities remain:

```text
Phase 10: streaming upload, hashes, signatures and quarantine metadata
Phase 11: quarantine → permanent lifecycle and compensation
Phase 12: authorized X-Accel-Redirect downloads
Phase 16: maintenance CLI and reconciliation
Phase 17: Docker ownership and read-only Nginx mounts
```

## Security guarantees and limitations

Guaranteed by Phase 9:

- user filenames are not physical paths;
- path traversal and known symlink escapes are blocked;
- managed directories are private and writable at startup;
- application-created stored files have no executable bits;
- cross-device moves fail instead of silently copying;
- cleanup cannot delete arbitrary operator files;
- backup storage cannot be nested beneath download storage.

Not yet guaranteed:

- content type or magic-byte correctness;
- SHA-256 integrity;
- malware status;
- database/filesystem compensation for upload failures;
- public download authorization;
- reconciliation of legacy or externally modified files.
