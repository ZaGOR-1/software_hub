# Phase 18 Review — Testing and CI Hardening

## Status

Phase 18 is implemented. The repository now has separate mandatory CI gates for
Python quality, dependency and static security analysis, production-like browser
E2E, accessibility, container builds, Trivy scans and runtime container smoke.

## Delivered

### Python quality gate

- Python 3.14 environment created from the committed `uv.lock`;
- `uv lock --check`;
- Ruff format and lint;
- strict mypy with JUnit output;
- full-repository pre-commit;
- JavaScript syntax and theme runtime tests;
- pytest with branch coverage, warning-as-error and strict xfail behavior;
- retained JUnit, coverage and type-check artifacts.

### Security gate

- Bandit medium/high severity and confidence gate;
- exact locked runtime dependency export;
- strict pip-audit gate;
- retained JSON reports;
- no `continue-on-error` on security checks.

### Browser E2E and accessibility

A production-like fixture starts an isolated SQLite database and private storage,
then runs Uvicorn behind a real Nginx process. The critical Chromium scenario
covers:

```text
login
→ create category
→ create and publish software
→ create, publish and select current stable release
→ upload ZIP
→ publish quarantine file
→ open the public page
→ download exact bytes through X-Accel-Redirect/Nginx
→ disable the file
→ verify the public URL returns 404
```

The browser matrix covers Chromium, Firefox and WebKit at mobile and desktop
viewports. It checks:

- semantic landmarks and heading order;
- labels and accessible names;
- duplicate IDs and image alternatives;
- keyboard focus and horizontal overflow;
- theme persistence;
- pinned axe-core WCAG A/AA serious/critical violations.

Screenshots, videos, logs and JUnit results are retained on failure.

### Container gate

- development and production Compose model validation;
- application and Nginx image builds;
- Trivy filesystem, secret and misconfiguration scan;
- Trivy HIGH/CRITICAL scan of both images;
- running Compose stack health check;
- non-root UID verification for app and Nginx;
- retained SARIF and runtime artifacts.

## Local acceptance

```text
pytest:                         496 passed
Opt-in browser tests:          10 skipped by default
Branch-aware coverage:         92.82%
Coverage threshold:            passed (90%)
Warnings:                      0
Python compileall:             passed
JavaScript theme runtime:      passed
TOML/YAML parsing:             passed
uv lock presence/offline:      passed
uv frozen runtime export:      passed
```

The local Chromium binary is controlled by an enterprise policy containing a
blanket URL block list. It can render in-memory HTML but refuses navigation even
to loopback URLs with `ERR_BLOCKED_BY_ADMINISTRATOR`. Therefore the cross-browser
suite is implemented and collected successfully, but its real navigation result
is not claimed as locally passed. The authoritative browser result is the clean
GitHub runner job.

The sandbox also has no Docker daemon and does not contain Ruff, mypy, Bandit or
pip-audit executables. Those checks are implemented as blocking CI jobs but are
not falsely reported as locally executed.

## Database and scope

No schema change was required. The Alembic head remains:

```text
0002_phase4_domain_schema
```

Phase 18 does not change business behavior, authorization policy, upload rules or
storage layout. It hardens verification of the existing system.

## Definition of done

- [x] Default regression suite remains green.
- [x] Branch coverage remains above the documented 90% threshold.
- [x] Warnings and unexpected XPASS results fail pytest.
- [x] Ruff, mypy, pre-commit and pytest are blocking CI gates.
- [x] Bandit and pip-audit are blocking security gates.
- [x] Critical admin/upload/publish/download/disable flow exists in Playwright.
- [x] Chromium, Firefox and WebKit accessibility matrix exists.
- [x] Deterministic DOM and axe-core audits are blocking E2E gates.
- [x] Docker images are built before acceptance.
- [x] Trivy scans repository configuration and both images.
- [x] Runtime container health and non-root behavior are checked.
- [x] Failure artifacts are retained for diagnosis.
- [x] Environment limitations are documented without overstating results.
