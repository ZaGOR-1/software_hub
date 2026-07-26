# Historical release blockers and remediation — Software Hub 1.0.0-rc.1

Вердикт: **NO-GO (full re-audit pending)**  
P0: 0  
P1: **0 open / 7 resolved**
P2: **0 open / 2 resolved**  
P3: **0 open / 1 resolved**

Цей файл зберігає початкові stop-ship P1 та обов’язкові acceptance conditions. Усі сім
P1, обидва P2 та P3 виправлено 2026-07-26; Docker/browser/recovery і фактичний
protected-tag provenance run ще не виконано.

## SH-AUDIT-001 — Clean Python 3.14 sync не збирається

- Status: **RESOLVED** — clean `uv sync --all-groups --locked` та imports PASS на CPython 3.14.
- Owner: Python/dependency maintainer + release engineering.
- Fix: Оновити сумісний FastAPI/Pydantic/pydantic-core/jiter set, зберігши Python `>=3.14,<3.15`; перегенерувати `uv.lock`.
- Verification: На чистому Ubuntu runner `uv lock --check`, `uv sync --all-groups --locked`, imports і `docker build --no-cache` — exit 0.
- Estimated complexity: M.

## SH-AUDIT-002 — Ruff gate несумісний і baseline не clean

- Status: **RESOLVED** — locked Ruff 0.15.22; format/lint PASS.
- Owner: Python maintainers.
- Fix: Pin Ruff з підтримкою `py314`; виконати контрольоване format/lint cleanup для 46/687 results; не маскувати errors глобальними ignores.
- Verification: Frozen `uv run ruff format --check .` і `uv run ruff check .` — exit 0.
- Estimated complexity: M.

## SH-AUDIT-003 — Playwright відсутній у standard quality graph

- Status: **RESOLVED** — Playwright 1.61.0 locked; mypy/pytest collection and execution PASS.
- Owner: QA/CI maintainer.
- Fix: Створити pinned E2E dependency group або ізолювати E2E imports/collection/type-check від standard job; одна dependency strategy має бути відтворюваною.
- Verification: Clean `uv sync --all-groups --locked`; `uv run mypy`; `uv run pytest` без manual install — exit 0; окремий E2E job також green.
- Estimated complexity: S.

## SH-AUDIT-004 — Stale Phase 18 infrastructure assertion

- Status: **RESOLVED** — explicit UTF-8/current flow; infrastructure 24 passed.
- Owner: QA maintainer.
- Fix: Прибрати fragile phrase-presence assertion або синхронізувати її з реальним flow; краще перевіряти route/actions/behavior.
- Verification: `pytest -o addopts='' tests/infrastructure -q` на Ubuntu — exit 0.
- Estimated complexity: XS.

## SH-AUDIT-005 — High Starlette form-parsing DoS

- Status: **RESOLVED** — Starlette 1.3.1; login bounded to 64 fields; regression PASS.
- Owner: Security + Python dependency maintainer + Nginx owner.
- Fix: Оновити Starlette щонайменше до 1.3.1 через сумісний FastAPI lock. Додати per-route малий `client_max_body_size` для login/звичайних admin forms, не зачіпаючи upload route.
- Verification: Frozen runtime `pip-audit` без GHSA-82w8-qh3p-5jfq; urlencoded field-flood regression; application health responsive під negative test.
- Estimated complexity: M.

## SH-AUDIT-006 — CI dependency audit дає false green

- Status: **RESOLVED** — frozen no-dev export audited; 27 dependencies, 0 vulnerabilities.
- Owner: Security/CI maintainer.
- Fix: `uv export --frozen --no-dev` у dedicated artifact і `pip-audit -r` цього exact runtime set або еквівалентний audit lock.
- Verification: Negative-control vulnerable version робить gate red; patched lock — green; JSON/SARIF/report artifact збережений.
- Estimated complexity: S.

## SH-AUDIT-007 — Неправильний container healthcheck path

- Status: **RESOLVED** — workflow uses `/usr/local/bin/software-hub-healthcheck.py`.
- Owner: Container/CI maintainer.
- Fix: У workflow викликати `/usr/local/bin/software-hub-healthcheck.py` або Docker health status.
- Verification: Full container workflow проходить build, scan, up, public health, non-root та app/nginx health.
- Estimated complexity: XS.

## Mandatory release acceptance conditions

Ці умови не підміняють P1 fixes і мають бути виконані до нового рішення:

1. **Clean Linux reproducibility**
   - Exact supported Python/uv.
   - Frozen sync/export.
   - Ruff, mypy, pytest with coverage ≥90%, Bandit, correct runtime pip-audit.

2. **Container and edge runtime**
   - No-cache app/nginx builds.
   - Compose config/up/health.
   - Non-root/read-only/capability checks.
   - Trivy filesystem + both images with agreed severity threshold.
   - Real Nginx `internal` direct denial, Range/HEAD, TLS redirect, TLS 1.2/1.3, HSTS and admin-access deny fallback.

3. **Browser/accessibility**
   - Chromium, Firefox, WebKit.
   - Desktop/mobile viewports.
   - Full admin→upload→publish→public→download flow.
   - axe-core serious/critical = 0 and keyboard/focus checks.

4. **Data recovery**
   - Production-like backup creation and verification.
   - Tamper detection.
   - Restore with safety backup.
   - Post-restore schema/current/integrity/content checks.
   - Rollback rehearsal and retention evidence.

5. **Immutable release evidence**
   - Protected commit and signed/approved tag.
   - RC workflow validates exact tag/commit identity.
   - Deterministic RC archive + SHA-256 + evidence manifest.
   - Persisted GitHub/Sigstore bundle and build-provenance attestation ID/URL verify for the expected repository.
   - Immutable artifact ID/name and tag workflow run URL are recorded.
   - CI run URLs, JUnit, coverage, audit/Trivy reports, Compose status, browser artifacts.
   - Acceptance record із власниками й residual-risk approvals.

Усі P1/P2/P3 fixes виконано. Реліз дозволено повторно оцінювати після виконання п’яти acceptance
groups вище на чистому Ubuntu runner і формування immutable evidence package.
