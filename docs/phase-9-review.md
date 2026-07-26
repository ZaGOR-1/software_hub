# Phase 9 completion review

## Result

Phase 9 is complete. Software Hub now owns a tested private filesystem boundary
for temporary uploads, quarantine, permanent software files, icons, import
staging and backups. No upload or download HTTP route was introduced.

## Delivered

- typed `StoragePaths` layout derived from validated settings;
- startup creation and readiness validation for every managed directory;
- symlink-component rejection and writable-directory probes;
- exact private modes: `0750` directories and `0640` stored files;
- configurable minimum free-space reserve;
- Unicode NFKC filename normalization;
- NUL, control, bidi, reserved-name and path-separator rejection;
- configurable extension allowlist and deceptive double-extension policy;
- UUID-based internal filenames and two-level path sharding;
- independent generated `.upload` temporary filenames;
- safe resolved-path containment for Linux and Windows-style traversal;
- server-generated upload path planning independent of original names;
- same-filesystem atomic moves with file and directory fsync;
- explicit cross-device refusal and destination collision protection;
- conservative dry-run temporary cleanup;
- storage manager registration in FastAPI lifespan;
- storage settings and local-development documentation;
- unit, integration and adversarial security tests.

## Database

No schema change was required. Alembic head remains:

```text
0002_phase4_domain_schema
```

Physical storage paths remain metadata fields already defined in the Phase 4
schema. Phase 10 will begin creating ReleaseFile records.

## Verification

```text
pytest:                         358 passed
branch-aware coverage:         95.21%
warnings:                      0
Python compileall:             passed
storage startup smoke:         passed
safe-path adversarial tests:   passed
filename confusion tests:      passed
permissions checks:            passed
atomic two-step move smoke:    passed
temporary cleanup safety:      passed
Alembic upgrade/check:         passed
Alembic downgrade/re-upgrade:  passed
TOML/YAML parsing:             passed
lock metadata alignment:       passed
uv.lock existence check:       passed
uv export --frozen:            unavailable locally (Python 3.14 absent)
Markdown internal links:       passed
```

The integrated filesystem smoke covers:

```text
initialize private layout
→ normalize original EXE name
→ allocate UUID temporary/quarantine/permanent paths
→ write temporary bytes
→ atomic move temporary → quarantine
→ atomic move quarantine → permanent
→ verify byte content and 0640 mode
→ verify no original filename occurs in a physical path
```

## Security tests

Adversarial coverage includes:

- `../` traversal;
- URL-encoded and double-encoded traversal after decoding;
- Windows backslash traversal;
- absolute paths;
- existing symlink escape;
- symlinked configured roots and shard components;
- NUL and control characters;
- Unicode full-width separator normalization;
- right-to-left override and other format controls;
- deceptive names such as `invoice.pdf.exe` and `archive.exe.zip`;
- Windows device names;
- UTF-8 byte-length overflow;
- executable permission removal;
- existing destination refusal;
- non-regular source refusal;
- simulated cross-device move refusal;
- stale cleanup that skips manual files, fresh files and symlinks.

## Environment limitations

The sandbox runs Python 3.13.5 while the project target remains Python 3.14.
Ruff, mypy, Bandit and pip-audit are not available in the local tool cache and
cannot be downloaded without network access. They remain mandatory GitHub
Actions quality gates.

## Deferred items

- streaming multipart upload;
- Content-Length and actual byte-count enforcement;
- extension plus magic-byte validation;
- SHA-256 calculation and duplicate lookup;
- optional malware scanner interface;
- ReleaseFile metadata and compensation cleanup;
- icon upload;
- maintenance CLI exposure for temporary cleanup;
- reconciliation of metadata and physical files;
- Nginx protected downloads.

## Definition of Done

```text
[x] Typed storage roots
[x] Startup directory creation and validation
[x] Writable probes and private permissions
[x] Path containment
[x] Symlink rejection
[x] Server-generated storage names
[x] Unicode filename normalization
[x] NUL and double-extension protection
[x] Disk free-space guard
[x] Same-filesystem atomic move
[x] No executable bits on stored files
[x] Conservative temporary cleanup
[x] Application lifespan integration
[x] Unit, integration and security tests
[x] Documentation and environment variables updated
[x] No database migration required
[x] No upload/download route added prematurely
```

Next phase: streaming upload, actual-size enforcement, signatures, SHA-256,
duplicate detection, scanner abstraction and quarantine metadata.
