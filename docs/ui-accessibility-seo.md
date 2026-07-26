# UI, accessibility and SEO hardening

## Purpose

Phase 14 completes the first production-oriented presentation pass for public,
administration, authentication and error pages. The server-rendered interface
continues to work without JavaScript; JavaScript adds only the optional persisted
theme preference.

## Theme model

Software Hub supports three preferences:

```text
system → light → dark → system
```

The preference is controlled by the button marked with `data-theme-toggle` and is
stored under the local-storage key `software-hub-theme`.

- `system` removes the explicit `data-theme` attribute and follows
  `prefers-color-scheme`;
- `light` sets `data-theme="light"`;
- `dark` sets `data-theme="dark"`;
- an unavailable or blocked `localStorage` falls back to system mode;
- a browser `storage` event synchronizes the choice between tabs;
- the button updates its visible label, icon, `title` and accessible name.

`theme-bootstrap.js` runs before the stylesheets and applies a stored explicit
preference early, reducing a light/dark flash during navigation. It contains no
inline data and remains compatible with the current `script-src 'self'` CSP.

Navigation, forms, catalog filtering, authentication and downloads do not depend
on JavaScript. With JavaScript disabled, the theme button stays hidden and the
operating-system color preference remains active.

## Accessibility controls

The shared shells now provide:

- `lang="uk"` and a responsive viewport;
- skip links to a focusable main region;
- semantic header, navigation, main and footer landmarks;
- `aria-current="page"` on active navigation links;
- persistent, high-visibility `:focus-visible` outlines;
- labeled search and administration forms;
- `aria-invalid` and `aria-describedby` for login validation errors;
- live regions for form notices and result updates;
- table captions, scoped column headings and keyboard-focusable table regions;
- descriptive download-button accessible names;
- reduced-motion behavior via `prefers-reduced-motion: reduce`;
- forced-colors adjustments for high-contrast environments;
- responsive public and administration layouts;
- minimum contrast checks for the approved light and dark text/background pairs.

ARIA is used only where native HTML does not already communicate the required
state. No user-provided value is inserted with `innerHTML`, `outerHTML` or
`document.write`.

## SEO metadata

Public pages receive one immutable `PageMetadata` projection containing:

- title;
- description;
- canonical URL;
- robots policy;
- Open Graph type;
- site name;
- `uk_UA` locale.

Canonical and Open Graph URLs are built from the validated
`SOFTWARE_HUB_PUBLIC_BASE_URL`. The request `Host` header is never used as the
canonical origin, preventing host-header poisoning of search and social metadata.

The public shell emits:

```text
<title>
meta description
meta robots
canonical link
Open Graph locale/type/site/title/description/url
Twitter summary card/title/description
```

Search and filtered catalog pages are `noindex, follow` to reduce duplicate
indexing. Direct unlisted and private pages remain `noindex, nofollow`.
Administrator, login and error pages emit `noindex, nofollow`.

## Sitemap and robots policy

`GET /sitemap.xml` returns a bounded XML sitemap containing only indexable pages:

- `/`;
- `/software`;
- visible public categories;
- published public software detail pages;
- release-history pages for published public software.

Private, unlisted, archived, draft, hidden and disabled software is excluded.
The repository limit is 24,000 software rows so the generated document remains
comfortably below the 50,000-URL sitemap limit after detail and release-history
entries are included.

`GET /robots.txt` advertises the configured absolute sitemap URL and disallows:

```text
/admin
/protected-downloads
/internal
/backups
```

Both responses use a one-hour public cache policy.

## CSP compatibility

Templates contain no inline `<style>` blocks and no inline executable scripts.
Theme scripts and styles are same-origin static assets, so the existing policy
can remain:

```text
script-src 'self'
style-src 'self'
```

No `unsafe-inline` exception was introduced.

## Validation

Automated coverage includes:

- trusted canonical URL generation and query encoding;
- Open Graph and robots metadata;
- sitemap exclusion rules;
- noindex behavior for search, private and administrative pages;
- skip links, focusable main regions, form labels and table semantics;
- approved contrast pairs;
- absence of inline styles/scripts and unsafe DOM sinks;
- JavaScript syntax;
- theme cycle, persistence, reload bootstrap and cross-tab storage updates in a
  Node DOM-runtime harness;
- template compilation and full HTTP integration tests.

The current execution sandbox could not launch a stable Chromium process because
of container-level browser restrictions. This is not reported as a passed browser
E2E run. A real Playwright/axe and cross-browser matrix remains a Phase 18 CI gate.
