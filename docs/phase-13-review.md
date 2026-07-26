# Phase 13 completion review

## Scope

Phase 13 implements the public Software Hub browsing experience: home page,
catalog, search, category and tag filtering, software details, release history
and visible download buttons. File delivery itself remains delegated to the
Phase 12 protected-download boundary.

## Components added

```text
app/repositories/public_catalog_repository.py
app/services/public_catalog_service.py
app/schemas/public_catalog.py
app/routers/public/common.py
app/routers/public/catalog.py
app/templates/public/base.html
app/templates/public/home.html
app/templates/public/catalog.html
app/templates/public/software_detail.html
app/templates/public/releases.html
app/templates/components/public_software_card.html
app/templates/components/public_file_table.html
app/templates/components/public_pagination.html
app/static/css/public.css
app/static/icons/favicon.svg
```

`SoftwareRepository` gained explicit public-query options for featured filtering,
visible-category search and public-only popularity accounting. No database schema
change was required.

## Public features

- bounded home sections for categories, featured, latest and popular software;
- full catalog with 18 items per page;
- search by name, description, developer, category and tag;
- category and tag filters;
- name, update and popularity ordering;
- software cards with current version and recommended download;
- direct public, unlisted, archived and administrator-private pages;
- current release, changelog and complete release history;
- public file tables with architecture, package type, size, SHA-256, publication
  date, signature state and download count;
- empty states, Ukrainian interface copy, responsive CSS and system color scheme;
- `robots.txt` and legacy favicon handling.

## Security boundary

Templates receive immutable public view models rather than ORM objects. The
projection omits storage paths, server storage names, scanner details, admin
notes, draft releases and all non-published files.

Catalog discovery includes only `published + public` software. Unlisted and
archived entries require an exact slug. Private entries require a valid
administrator session. Disabled entries return a non-enumerating `404` even for
an administrator.

Public visitors see only files with `published + public`. Administrators can see
published private/unlisted files on authorized direct pages, but every button
still passes through the Phase 12 download service.

Search wildcard characters are escaped and all filtering uses SQLAlchemy bind
parameters. Hidden categories and tags attached only to private software are not
exposed as public facets.

## Automated test result

```text
pytest:                         436 passed
Branch coverage:               94.36%
Warnings:                      0
Python compileall:             passed
Python AST parsing:            passed
Python lines over 100 chars:   0
Jinja templates:               35 passed
Public query-count bound:      passed
Alembic upgrade/check:         passed
Alembic downgrade/re-upgrade:  passed
Alembic schema drift:          absent
Migration head:                0002_phase4_domain_schema
uv export --frozen --no-dev:   passed
```

The test suite covers:

- home and catalog exclusion of draft, archived, unlisted and private entries;
- hidden-category and private-tag non-disclosure;
- search normalization, literal `%` matching and invalid input bounds;
- category/tag filtering and all sort modes;
- pagination and bounded query count;
- current release and historical release rendering;
- XSS autoescaping;
- omission of storage paths, storage names, admin notes and draft file metadata;
- direct unlisted/archive behavior;
- administrator-only private and draft previews;
- disabled behavior for anonymous and administrator requests;
- robots, favicon and static public assets.

## Production-like Uvicorn acceptance

A real Uvicorn process used a file-backed migrated SQLite database and seeded
public software graph.

```text
GET /                              200
GET /software                      200
GET /software/smoke-tool           200
GET /software/smoke-tool/releases  200
```

Every page contained the expected detached public metadata and the process shut
down cleanly.

## Deferred work

- explicit theme selector, persisted preference and final accessibility audit —
  Phase 14;
- canonical/Open Graph metadata, sitemap and complete SEO review — Phase 14;
- richer operational dashboard and health checks — Phase 15;
- reconciliation and backup/restore — Phase 16;
- final Nginx TLS/container/static-cache configuration — Phase 17;
- full Python 3.14 lint/type/security CI matrix — Phase 18.

## Environment limitation

Tests ran with Python 3.13.5 because the offline sandbox does not contain Python
3.14 or cached Ruff, mypy, Bandit and pip-audit executables. Ruff download also
returned `503 Service Unavailable`. GitHub Actions remains the mandatory target
Python 3.14 quality gate.

## Definition of done

- [x] Public home page exists
- [x] Public catalog, search, filters, sorting and pagination work
- [x] Categories and public tags cannot leak private catalog metadata
- [x] Software cards expose current version and recommended file
- [x] Direct software pages enforce public/unlisted/private/archive rules
- [x] Release history exposes only published or archived releases
- [x] File tables contain trust metadata but no physical storage metadata
- [x] Jinja autoescape protects descriptions, changelogs and filenames
- [x] Public download links use the existing protected-download endpoint
- [x] N+1 behavior is bounded by eager loading and tested query limits
- [x] Empty catalog and empty search states render correctly
- [x] Robots and favicon routes are present
- [x] No schema migration is required and Alembic has no drift
- [x] Public catalog and Phase 13 review documentation are complete
