# Phase 5 completion review

## Scope

Phase 5 implements repositories, bounded pagination, parameterized software
search, domain visibility rules and transaction-oriented application services.
It does not add HTTP routes, authentication, CSRF, storage operations or UI.

## Implemented files

```text
app/repositories/
├── __init__.py
├── base.py
├── user_repository.py
├── session_repository.py
├── category_repository.py
├── tag_repository.py
├── software_repository.py
├── release_repository.py
├── release_file_repository.py
├── download_stat_repository.py
└── audit_repository.py

app/schemas/
├── __init__.py
└── pagination.py

app/services/
├── __init__.py
├── normalization.py
├── policies.py
├── category_service.py
├── tag_service.py
├── software_service.py
├── release_service.py
└── file_service.py
```

Additional changes:

- typed `EntityConflict` and `ValidationError` application exceptions;
- reusable migrated `domain_database` pytest fixture;
- repository, service, policy, pagination and normalization tests;
- application-layer documentation;
- README and documentation index updates.

## Acceptance results

```text
[PASS] Repositories do not commit transactions
[PASS] Services own short write transactions
[PASS] Pagination rejects unsafe bounds
[PASS] Search whitespace normalization works
[PASS] Search minimum/maximum length works
[PASS] LIKE wildcard characters are escaped
[PASS] Search uses SQLAlchemy bind parameters
[PASS] Name/description/developer/category/tag search works
[PASS] Category/tag/status/visibility filters work
[PASS] Name/update/popularity sorting works
[PASS] Relationship access has no N+1 queries
[PASS] Duplicate SHA-256 lookup is indexed
[PASS] Software transitions are enforced
[PASS] Release transitions are enforced
[PASS] Release-file transitions are enforced
[PASS] Current stable replacement is atomic
[PASS] Invalid transitions roll back
[PASS] Visibility policies cover the full parent chain
[PASS] No database migration is required
```

## Test result

```text
233 tests passed
98.61% branch-aware coverage
0 warnings
```

The suite includes unit tests for pure policies and integration tests against a
real migrated file-backed SQLite database.

## Quality checks performed locally

```text
python -m compileall app tests
python -m pytest
python -m alembic upgrade head
python -m alembic check
Python import smoke checks
TOML/YAML parsing
line-length and generated-artifact checks
archive checksum and ZIP integrity
```

The sandbox still does not provide Python 3.14 or cached Ruff/mypy executables.
Their authoritative run remains the existing GitHub Actions quality gate using
the committed lock file.

## Known limitations

- Search is SQL `LIKE` based; full-text search is intentionally out of scope.
- Popularity sorting uses aggregate `ReleaseFile.download_count` metadata.
- SQLite serializes writes; the service transaction and unique partial index
  protect current stable selection for the single-instance MVP.
- File lifecycle changes affect metadata only. Physical moves begin in Phase 9
  and Phase 11.
- Audit repositories exist, but audit event policy is implemented later.

## Definition of Done

```text
[x] No critical TODO or placeholder logic
[x] Existing and new tests pass
[x] Coverage remains above the documented threshold
[x] No schema drift
[x] Documentation updated
[x] No new environment variables
[x] No secrets or user-controlled SQL fragments
[x] Invalid writes roll back
[x] Phase boundaries respected
```

## Next phase

Phase 6 implements Argon2id password handling, administrator provisioning,
server-side session creation/rotation/revocation, login lockout and protected
admin dependencies.
