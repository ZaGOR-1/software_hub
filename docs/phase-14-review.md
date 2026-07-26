# Phase 14 completion review

## Scope

Phase 14 completes the explicit light/dark/system theme selector, accessibility
hardening, canonical/Open Graph metadata, sitemap, robots policy and responsive
presentation polish. It does not add observability, backup, container or TLS
runtime work from later phases.

## Components added

```text
app/core/seo.py
app/static/css/theme.css
app/static/css/system.css
app/static/js/theme-bootstrap.js
app/static/js/theme.js
tests/browser/theme_runtime_test.js
tests/unit/core/test_seo_phase14.py
tests/unit/test_theme_assets_phase14.py
tests/integration/public/test_seo_accessibility_phase14.py
docs/ui-accessibility-seo.md
```

The public catalog repository and service gained a bounded public-only sitemap
projection. Public, admin, login and error shells were updated to share the
accessible theme controls and noindex rules appropriate to each surface.

## Theme implementation

- three states: system, light and dark;
- persisted explicit choice in `localStorage`;
- system fallback when storage or JavaScript is unavailable;
- early same-origin bootstrap script to reduce theme flash;
- cross-tab synchronization through the `storage` event;
- no `innerHTML`, dynamic style injection or inline scripts;
- shared button state, accessible name and visible label on every UI surface.

## Accessibility implementation

- skip links and focusable main landmarks;
- semantic navigation with current-page indication;
- visible keyboard focus;
- responsive table regions with captions and scoped headings;
- descriptive file-download labels;
- accessible login errors and live form/result notices;
- reduced-motion and forced-colors support;
- mobile navigation and administration layout refinements;
- static WCAG 2.x normal-text contrast checks for approved color pairs.

## SEO implementation

- canonical, description, robots, Open Graph and Twitter metadata;
- canonical origin built only from configured `PUBLIC_BASE_URL`;
- `article` Open Graph type for software detail pages;
- noindex policy for search/filter duplicates and private surfaces;
- bounded public-only XML sitemap;
- robots file advertising the trusted sitemap URL;
- sitemap exclusion of private, unlisted, archived, draft, hidden and disabled
  software.

## Automated result

```text
pytest:                         446 passed
Branch coverage:               94.47%
Warnings:                      0
Python compileall:             passed
JavaScript syntax:             passed
Theme DOM-runtime checks:      passed
Python lines over 100 chars:   0
Jinja templates:               35 passed
Alembic upgrade/check:         passed
Alembic downgrade/re-upgrade:  passed
Alembic schema drift:          absent
Migration head:                0002_phase4_domain_schema
uv export --frozen --no-dev:   passed
Uvicorn HTTP/static/SEO smoke:   passed
Markdown internal links:        64 passed
```

The suite verifies trusted URL construction, metadata escaping, public-only
sitemap contents, noindex policies, keyboard-oriented markup, CSP compatibility,
contrast, no unsafe DOM sinks and theme persistence behavior.

## Browser-test limitation

A live Uvicorn process and HTTP/static-asset smoke tests pass. The sandbox could
not start a stable headless Chromium process because of container-level browser
restrictions. Chromium/Firefox/WebKit and automated axe validation therefore
remain explicit Phase 18 CI work and are not represented as completed here.

The Node runtime harness executes the production theme scripts against a minimal
DOM/local-storage implementation and verifies system → light → dark cycling,
persistence, early reload bootstrap and storage-event synchronization.

## Deferred work

- richer dashboard, health and operational observability — Phase 15;
- backup, restore, reconciliation and maintenance CLI — Phase 16;
- final Nginx cache/TLS and container hardening — Phase 17;
- Playwright browser matrix, axe checks and full Python 3.14 quality matrix —
  Phase 18.

## Environment limitation

Tests ran on Python 3.13.5 because the offline sandbox does not contain the target
Python 3.14 runtime or cached Ruff, mypy, Bandit and pip-audit executables. Those
remain required GitHub Actions checks.

## Definition of done

- [x] System, light and dark preferences are available
- [x] Explicit theme preference persists without becoming required functionality
- [x] Public, admin, login and error surfaces share theme support
- [x] Main flows remain usable without JavaScript
- [x] Skip links, focus states and semantic landmarks are present
- [x] Forms, live notices and tables expose accessible relationships
- [x] Reduced-motion, forced-colors and responsive behavior are implemented
- [x] Canonical and social metadata use the trusted configured origin
- [x] Search/filter and private surfaces use an explicit noindex policy
- [x] Public-only sitemap and robots advertisement are implemented
- [x] Templates remain compatible with strict same-origin script/style CSP
- [x] No database migration is required and Alembic has no drift
- [x] Phase 14 documentation and release checks are updated
- [ ] Real Playwright/axe cross-browser matrix — deferred to Phase 18 CI
