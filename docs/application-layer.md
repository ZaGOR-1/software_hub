# Application layer and repositories

Phase 5 introduces the first domain behavior above the SQLAlchemy model layer.
It keeps HTTP, templates, authentication and storage outside the implementation.

## Layering

```text
future HTTP router / CLI
        │
        ▼
application service
        │ owns transaction boundaries
        ▼
session-bound repository
        │
        ▼
SQLAlchemy ORM / SQLite
```

Routers must not manipulate ORM entities directly. Read operations use a
short-lived `Database.session()`. Every write service opens one
`Database.transaction()`, invokes repositories and returns only after a flush
and successful commit.

## Repository contracts

Repositories are deliberately small. They:

- accept an existing SQLAlchemy `Session`;
- never commit or roll back;
- use parameterized SQLAlchemy expressions;
- flush only when a caller explicitly adds or deletes an entity;
- return typed entities or immutable `Page` results;
- eagerly load relationship graphs required outside the session;
- keep physical storage concerns out of database queries.

Implemented repositories:

```text
BaseRepository
UserRepository
SessionRepository
CategoryRepository
TagRepository
SoftwareRepository
ReleaseRepository
ReleaseFileRepository
DownloadStatRepository
AuditRepository
```

## Pagination

`Pagination` validates one-based page numbers and caps `per_page` at 100.
`Page[T]` exposes:

- `items`;
- `total`;
- `page`;
- `per_page`;
- `pages`;
- `has_previous`;
- `has_next`.

The count query is derived from the filtered statement before limit and offset.
Order clauses are removed from the count subquery.

## Software search

`SoftwareRepository.list_page()` supports:

- normalized free-text query;
- category slug;
- one or more tag slugs;
- software statuses;
- visibility values;
- name, update-time and popularity sorting.

Free-text search covers:

- software name;
- short description;
- developer name;
- category name;
- tag name.

Whitespace is collapsed. Queries shorter than two characters or longer than
100 characters are rejected. `%`, `_` and the escape character are escaped
before use in a bound `LIKE` expression, so user input cannot alter wildcard
semantics. No SQL is constructed by string concatenation.

Catalog queries eager-load category, tags, releases and release-file metadata.
Integration tests assert that relationship access after listing does not issue
additional N+1 queries.

## Lifecycle policies

### Software

```text
draft     → published | hidden | disabled
published → hidden | archived | disabled
hidden    → draft | published | archived | disabled
archived  → published | hidden | disabled
disabled  → draft
```

Publishing sets `published_at` once. Archiving sets `archived_at`. Leaving the
archived state clears `archived_at`.

### Release

```text
draft     → published | archived | disabled
published → archived | disabled
archived  → published | disabled
disabled  → draft
```

A release can be published only while its parent software is `published` or
`hidden`. Any transition away from `published` clears `is_current`.

Only a published stable release under published or hidden software may become
the current stable release. `ReleaseService.set_current_stable()` clears the
old marker and sets the new one in one transaction. The Phase 4 partial unique
index remains the database-level final guard.

### Release file

```text
quarantine → ready | rejected | disabled
ready      → published | rejected | disabled | archived
published  → disabled | archived
disabled   → ready | archived
archived   → ready | disabled
rejected   → quarantine
```

Publication requires:

- file status `ready`;
- parent release status `published`;
- parent software status `published` or `hidden`;
- scanner status other than `infected`.

Publishing sets `published_at`. Disabling sets `disabled_at`. Re-enabling or
archiving clears `disabled_at`.

## Visibility policies

Public catalog listing requires:

```text
Software.status == published
Software.visibility == public
```

A non-admin direct page may show published or archived software with public or
unlisted visibility. A disabled software entry is unavailable even to an admin
through the future public-page policy.

A download authorization check evaluates the complete chain:

```text
Software → Release → ReleaseFile
```

The file must be published, the release must be published or archived and the
software must be published or archived. Private visibility additionally
requires an administrator context. The actual download endpoint is Phase 12.

## Application services

Implemented services:

- `CategoryService`;
- `TagService`;
- `SoftwareService`;
- `ReleaseService`;
- `FileService`.

They provide transaction-safe creation, metadata association, pagination,
search, status transitions, visibility changes, duplicate SHA-256 lookup and
current-release selection. They raise typed application exceptions instead of
HTTP responses.

## Explicitly deferred

Phase 5 does not implement:

- password hashing or login;
- server-side session business logic;
- CSRF;
- audit event creation policy;
- upload or physical file operations;
- public/admin routers;
- forms or templates;
- download counters or X-Accel-Redirect.
