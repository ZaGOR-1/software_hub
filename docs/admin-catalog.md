# Administration catalog — Phase 8

## Scope

Phase 8 replaces the authentication placeholder with a server-rendered
administration interface for catalog metadata. It deliberately does not include
file upload, icon storage, public catalog pages, download delivery or the full
operations dashboard.

## Route groups

### Dashboard

```text
GET /admin
```

The dashboard displays bounded counters for programs, releases, files,
categories and tags, plus the ten newest audit events. Detailed storage,
backup, quarantine and disk-health widgets remain Phase 15 work.

### Categories

```text
GET  /admin/categories
POST /admin/categories
GET  /admin/categories/{id}/edit
POST /admin/categories/{id}/edit
POST /admin/categories/{id}/delete
```

Deleting a category removes only category metadata. Existing software rows are
kept and their `category_id` becomes `NULL` through the database foreign-key
policy.

### Tags

```text
GET  /admin/tags
POST /admin/tags
GET  /admin/tags/{id}/edit
POST /admin/tags/{id}/edit
POST /admin/tags/{id}/delete
```

Deleting a tag removes its many-to-many association rows. Software metadata is
not deleted.

### Software

```text
GET  /admin/software
GET  /admin/software/new
POST /admin/software
GET  /admin/software/{id}/preview
GET  /admin/software/{id}/edit
POST /admin/software/{id}/edit
POST /admin/software/{id}/publish
POST /admin/software/{id}/hide
POST /admin/software/{id}/archive
POST /admin/software/{id}/disable
POST /admin/software/{id}/restore
```

New software always starts as `draft`. The form may configure visibility and
metadata, but lifecycle state changes use dedicated service methods and policy
checks. The preview is administrator-only; it is not the future public software
page.

Supported editable metadata includes:

- name and slug;
- short and full plain-text descriptions;
- developer and license;
- official and source URLs;
- category and tags;
- supported operating systems and system requirements;
- visibility and featured flag.

Only absolute HTTP or HTTPS URLs are accepted. URL credentials, control
characters and other schemes are rejected. The application never fetches these
URLs.

### Releases

```text
GET  /admin/software/{software_id}/releases/new
POST /admin/software/{software_id}/releases
GET  /admin/releases/{id}/edit
POST /admin/releases/{id}/edit
POST /admin/releases/{id}/publish
POST /admin/releases/{id}/archive
POST /admin/releases/{id}/disable
POST /admin/releases/{id}/restore
POST /admin/releases/{id}/current
POST /admin/releases/{id}/current/clear
```

A release starts as `draft`. Publication requires its parent software to be
`published` or `hidden`. Only a published stable release may become current.
The service clears the previous current stable release in the same transaction.

## Transaction and audit model

Routers do not manipulate ORM entities directly. They validate browser form
payloads and call transaction-oriented services. Each successful write and its
audit event are persisted inside the same database transaction.

New audit actions:

```text
category_created
category_updated
category_deleted
tag_created
tag_updated
tag_deleted
software_created
software_updated
software_status_changed
software_visibility_changed
release_created
release_updated
release_status_changed
release_current_changed
```

Audit metadata contains bounded identifiers such as slug, version and status
transition. Passwords, cookies, CSRF tokens and submitted descriptions are not
recorded.

## Slugs and text

An empty slug is generated from the display name. Ukrainian Cyrillic is
transliterated to deterministic ASCII before normalization. Explicit slugs
accept lowercase ASCII letters, digits and single hyphens.

Descriptions are plain text. Jinja autoescape remains enabled and no user
content is passed through `safe`. A tested script payload is rendered as text,
not executable markup.

## Form security

Every `POST` route uses `CSRFProtectedAdminSession`. A route inventory test
enumerates every unsafe route and fails when an approved CSRF dependency is
missing.

Other controls:

- all administrator pages require a valid server-side session;
- form and action responses use `Cache-Control: no-store`;
- Pydantic errors are rendered without submitted input values;
- invalid non-HTTP URL values are not reflected back into form attributes;
- destructive category and tag actions require an explicit confirmation
  checkbox;
- lifecycle operations use policy services rather than hidden-button trust;
- PRG redirects prevent accidental form resubmission.

## UI architecture

The interface uses Jinja2, semantic HTML and one external CSS file under
`/static/css/admin.css`. There are no inline scripts or styles, so the current
Content Security Policy remains valid. The layout includes keyboard focus,
a skip link, responsive tables/forms and mobile navigation.

## Deferred work

The following remain intentionally outside Phase 8:

- icon upload and preview;
- ReleaseFile upload and quarantine;
- physical file deletion;
- public catalog and public preview;
- audit-log filtering page;
- full disk/storage/backup dashboard;
- image optimization and final visual design polish.
