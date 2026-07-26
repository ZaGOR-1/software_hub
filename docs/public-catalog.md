# Public catalog and software pages

## Purpose

Phase 13 adds the public server-rendered Software Hub experience. It exposes only
presentation models assembled by `PublicCatalogService`; Jinja templates never
receive raw `Software`, `Release` or `ReleaseFile` ORM entities.

This boundary prevents accidental disclosure of:

- physical and relative storage paths;
- server-generated storage filenames;
- quarantine, ready, rejected or disabled files;
- draft and disabled releases;
- administrative notes and scanner details;
- private or unlisted files in public listings.

## Routes

```text
GET /
GET /software
GET /software/{software_slug}
GET /software/{software_slug}/releases
GET /category/{category_slug}
GET /search
GET /robots.txt
GET /favicon.ico
```

The existing protected-download routes remain the only public file-delivery
entry points.

## Listing visibility

General catalog listings, category pages, search results, featured sections and
popularity sections include only software satisfying both conditions:

```text
status = published
visibility = public
```

`archived` and `unlisted` software is intentionally excluded from every listing.
It can still be opened by its exact slug. `private` software requires a valid
administrator session. `disabled` software always behaves as not found,
including for an administrator.

Hidden categories are not exposed as facets, do not appear on cards and do not
participate in public category-name search. Tags become public facets only when
attached to at least one publicly listed software record.

## Direct page visibility

| Software state | Anonymous direct page | Administrator direct page |
|---|---:|---:|
| published + public | yes | yes |
| published + unlisted | yes, `noindex` | yes |
| published + private | no | yes, `noindex` |
| archived + public/unlisted | yes | yes |
| draft/hidden | no | yes |
| disabled | no | no |

Direct access does not weaken file-level policy. A public visitor sees only
`published + public` files. An authenticated administrator may see published
files with public, unlisted or private visibility. Every button still points to
the Phase 12 authorization endpoint, which re-evaluates the complete metadata
chain and storage integrity.

## Search and filtering

Search covers:

- software name;
- short description;
- developer name;
- visible category name;
- associated tag name.

Input is whitespace-normalized, limited to 2–100 characters and passed only
through SQLAlchemy expressions and bind parameters. `%`, `_` and backslashes are
escaped before `LIKE` matching, so wildcard text is interpreted literally.

Supported filters and sorts:

```text
category slug
single tag slug
updated date
case-insensitive name
public-file download popularity
```

Popularity counts only published, publicly listable files under published or
archived releases. Private and unlisted file counts cannot influence the public
ranking.

Pagination is one-based, capped defensively and uses 18 cards per page. The
repository uses one count query, one page query and bounded select-in eager
loads, avoiding per-card N+1 queries.

## Presentation projection

The public service creates immutable dataclasses for:

- category and tag facets;
- software cards;
- software details;
- releases;
- downloadable files;
- home and catalog pages.

The projection explicitly selects fields safe for browser output. File view
models contain the public UUID, display filename, architecture, package type,
size, SHA-256, publication date, signature label and download count. They never
contain storage names, paths, admin notes or scanner diagnostics.

## Current release and recommended file

The current release is the published release marked `is_current`. If data has no
explicit current release, the latest non-archived published stable release is a
safe display fallback.

The recommended file is the first publicly listable file under deterministic
preference ordering:

```text
x64 → ARM64 → x86 → universal → other
installer → MSI → portable → archive → other
filename
```

The recommendation is a convenience only. The download route remains the final
authorization boundary.

## HTML safety

- Jinja autoescape remains enabled.
- Software descriptions and changelogs are rendered as plain text with preserved
  line breaks.
- No user-authored HTML is marked safe.
- External links originate from the validated admin write path and use
  `rel="noopener noreferrer"`.
- The public UI has no inline scripts and needs no JavaScript for navigation,
  search, filtering or download links.
- Private and unlisted direct pages emit `noindex, nofollow`.

## Deferred to Phase 14

Phase 13 includes responsive foundations and system light/dark styling but does
not yet claim completion of the Phase 14 UI acceptance scope. Phase 14 will add:

- explicit light/dark/system theme controls and persistence;
- full accessibility audit and automated axe coverage;
- canonical and Open Graph metadata;
- refined responsive behavior and cross-browser review;
- optional sitemap and final SEO policy.
