# Phase 4 completion review

**Phase:** Domain models and production schema  
**Status:** Implemented  
**Date:** 2026-07-23

## Scope delivered

Phase 4 introduces the complete MVP relational schema without starting
repositories, CRUD services or business workflows from Phase 5.

Implemented:

- domain `StrEnum` values for software, release and file lifecycle metadata;
- portable validated SQLAlchemy enum storage;
- timestamp mixin with UTC-aware application values;
- `User` and server-side `UserSession` models;
- `Category`, `Tag` and `software_tags` models;
- `Software`, `Release` and `ReleaseFile` hierarchy;
- `DownloadStat` daily aggregate model;
- append-oriented `AuditLog` model;
- integer internal IDs and public UUID for release files;
- explicit relationships and database delete behavior;
- named uniqueness, foreign-key and check constraints;
- search/listing/cleanup indexes;
- partial unique index for one current stable release per software;
- Alembic revision `0002_phase4_domain_schema`;
- schema-drift check through Alembic;
- explicit integration fixtures and schema behavior tests;
- complete data-model documentation.

## Files created

```text
app/models/__init__.py
app/models/associations.py
app/models/audit_log.py
app/models/category.py
app/models/download_stat.py
app/models/enums.py
app/models/mixins.py
app/models/release.py
app/models/release_file.py
app/models/session.py
app/models/software.py
app/models/tag.py
app/models/types.py
app/models/user.py
alembic/versions/0002_phase4_domain_schema_create_domain_schema.py
tests/fixtures/__init__.py
tests/fixtures/models.py
tests/integration/models/__init__.py
tests/integration/models/test_constraints.py
tests/integration/models/test_metadata.py
tests/integration/models/test_models.py
docs/data-model.md
docs/phase-4-review.md
PHASE_4_MANIFEST.txt
```

## Files updated

```text
alembic/env.py
app/database/migrations_helpers.py
tests/integration/database/test_migrations.py
pyproject.toml
README.md
docs/README.md
```

## Decisions confirmed

1. Internal relational IDs remain integers.
2. `ReleaseFile.public_uuid` is the public file identifier.
3. File bytes and absolute filesystem paths never enter SQLite.
4. Enums persist their lowercase values as portable checked strings.
5. Category deletion uses `SET NULL`.
6. User deletion removes sessions but preserves audit history.
7. Dependent catalog metadata uses foreign-key cascades.
8. Physical files are never removed by an ORM cascade.
9. SHA-256 is indexed for duplicate detection but is not globally unique.
10. One current stable release per software is enforced by a partial unique
    index; Phase 5 services will perform the atomic transition.
11. Audit metadata remains generic JSON until the Phase 5 audit service applies
    an allowlist.
12. Generated Alembic revisions are excluded from Ruff formatting, but compile,
    upgrade, downgrade and schema-drift checks are mandatory.

## Verification results

```text
pytest                              108 passed
branch-aware coverage              98.69%
metadata tables                    10 domain tables
Alembic head                       0002_phase4_domain_schema
Alembic schema drift               none
upgrade/downgrade chain            passed
foreign keys and delete actions    passed
unique/check constraints           passed
partial current-stable index       passed
UUID and enum round trip           passed
UTC timestamp round trip           passed
```

## Environment limitation

The sandbox provides Python 3.13.5 while the repository target remains Python
3.14. Network access is unavailable, so the frozen Python 3.14 environment and
Ruff, mypy, Bandit and pip-audit cannot be executed locally. They remain
required GitHub Actions quality gates. No dependencies were added during Phase
4, so `uv.lock` remains unchanged.

## Explicitly deferred to Phase 5

- base and entity repositories;
- pagination abstraction;
- search query construction;
- lifecycle transition policies;
- atomic current-release service logic;
- duplicate-file application handling;
- application transaction boundaries around repositories;
- Pydantic request/response schemas.

## Definition of Done

- [x] All required ORM models exist.
- [x] Software, Release and ReleaseFile remain separate tables.
- [x] Many-to-many tags use a composite-key association table.
- [x] Relationships and database delete behavior are explicit.
- [x] Unique and check constraints are tested.
- [x] Critical indexes are present.
- [x] Public UUID round-trips as `uuid.UUID`.
- [x] Enum values round-trip as typed enums.
- [x] UTC timestamps remain timezone-aware after SQLite reads.
- [x] Clean migration upgrade and downgrade pass.
- [x] Alembic reports no schema drift.
- [x] Documentation and test fixtures are updated.
- [x] Repository and business-service work has not started.
