# Software Hub Test Strategy

## Purpose

The test system protects the authentication, CSRF, upload, filesystem, download,
backup and restore boundaries while keeping ordinary catalog changes fast to
validate. Phase 18 turns the previous tests into mandatory CI quality gates.

## Test pyramid

### Unit tests

Pure normalization, policy, hashing, CSRF, session-expiry, path and configuration
logic. Unit tests should not open network listeners or depend on real browser
engines.

### Integration and security tests

Use isolated SQLite databases and private temporary storage. They cover:

- repositories and transactions;
- Alembic upgrade/downgrade and schema drift;
- login, sessions, CSRF and lockout;
- CRUD and audit events;
- upload signatures, size limits and compensation cleanup;
- file lifecycle and physical-storage reconciliation;
- protected download authorization and counters;
- backup/restore and rollback;
- Docker/Nginx configuration invariants.

The default `pytest` command enforces at least 90% branch-aware coverage for the
application package. Warnings and unexpected xpasses fail the suite.

### Browser E2E

The Playwright job starts Uvicorn behind a real Nginx process. It does not mock
form submissions or protected downloads. The critical test performs:

```text
login
→ create category
→ create software
→ publish software
→ create and publish current stable release
→ upload ZIP to quarantine
→ publish file
→ open public page
→ download bytes through Nginx
→ disable file
→ verify download returns 404
```

The browser matrix runs Chromium, Firefox and WebKit at mobile and desktop
viewports. It checks semantic landmarks, heading structure, labels, accessible
names, duplicate IDs, keyboard focus, horizontal overflow and theme persistence.
A pinned axe-core engine also scans WCAG A/AA rules and blocks serious or critical
violations. Automated checks complement, but do not replace, a manual WCAG review.

## CI jobs

### `CI / quality`

- `uv lock --check`;
- Ruff formatting and lint;
- strict mypy;
- pre-commit over the complete repository;
- JavaScript syntax and theme runtime;
- pytest with branch coverage;
- JUnit, mypy and coverage artifacts.

### `CI / security`

- Bandit medium/high severity and confidence gate;
- locked runtime export;
- strict `pip-audit`;
- retained JSON reports.

### `Browser E2E / playwright`

- exact Playwright and axe-core tool versions;
- Chromium, Firefox and WebKit installation;
- real Nginx/Uvicorn flow;
- screenshots, videos and JUnit artifacts.

### `Container Build and Scan / build-scan-smoke`

- development and production Compose validation;
- application and Nginx image builds;
- Trivy filesystem, secret and misconfiguration scan;
- Trivy HIGH/CRITICAL scans of both images;
- running Compose stack health smoke;
- non-root runtime checks.

## Failure policy

No security, test, type, formatting or container vulnerability gate uses
`continue-on-error`. Reports are uploaded with `if: always()` so failed runs
remain diagnosable. A scan exception must be documented with the vulnerability,
impact, compensating control, owner and expiration date before it is added.

## Local limitations

A developer may run unit/integration tests without browser binaries. Browser E2E
is deliberately opt-in through `SOFTWARE_HUB_RUN_E2E=1`. Docker and cross-browser
results remain CI requirements before a release candidate is accepted.
