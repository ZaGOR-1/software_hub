# Незалежний release-аудит Software Hub 1.0.0-rc.1

Вердикт: **NO-GO (оригінальний аудит; повний re-audit очікується)**  
Release readiness score: **47/100 (оригінальний, не перераховувався)**  
P0: **0**  
P1: **7 historical / 0 open after remediation**  
P2: **2 historical / 0 open after remediation**  
P3: **1 historical / 0 open after remediation**  
Checks PASS: **10**  
Checks FAIL: **3**  
Checks BLOCKED: **8**

Дата: 2026-07-26  
Режим: початковий read-only audit + focused P1/P2/P3 remediation passes.

## Remediation update — 2026-07-26

Усі сім P1, обидва P2 та P3 виправлено. Актуальна локальна перевірка на
frozen CPython 3.14:

- clean locked sync та import smoke — PASS;
- Ruff format/lint — PASS;
- strict mypy — PASS, 188 source files;
- standard pytest — 500 passed, 17 intentional skips, coverage 92.16%;
- P2/P3 infrastructure regressions — 15 passed;
- frozen runtime pip-audit — 27 dependencies, 0 vulnerabilities;
- Bandit — 0 findings;
- 15/15 third-party Action invocations use full commit SHA + version comment;
- RC workflow enforces exact tag/commit identity, deterministic archive/checksums,
  evidence manifest, signed GitHub provenance and immutable artifact naming.

Статус focused remediation: **P1/P2/P3 RESOLVED / FULL RE-AUDIT PENDING**. Оригінальний `NO-GO`
не перетворюється на `GO` без чистого Ubuntu evidence для Docker/Compose/Nginx/TLS/Trivy,
реального Playwright/axe matrix, backup/restore rehearsal та фактичного protected-tag run,
який опублікує налаштовані RC artifact і attestation.

## 1. Executive summary

Початковий аудит визначив, що Software Hub **не готовий до production release**. Найсильніші сторони кандидата — чіткі архітектурні межі, fail-closed auth/session/CSRF, path containment, quarantine, policy-gated lifecycle, авторизована видача через `X-Accel-Redirect`, SQLite constraints/PRAGMA та змістовна документація.

Сім зафіксованих P1 були незалежними release blockers; focused remediation passes закрили
всі десять P1/P2/P3 findings. Історичні reproduction/evidence нижче збережені, а актуальний
статус кожного — `resolved`.

Рахунок 47/100 складається з Security 14/25, Data integrity/backup 12/20, Deployment/reproducibility 2/15, Functional correctness 11/15, Test/CI evidence 1/10, Operations 4/10, Documentation/accessibility 3/5. Матриця також містить 9 PARTIAL checks, які не включено до трьох headline-лічильників.

## 2. Scope

Перевірено snapshot `D:\work\software_hub`: requirements і PHASE evidence, metadata/lock, архітектуру, static quality, SQLite schema/migrations, auth/session/CSRF/admin authorization, upload/storage/lifecycle/download, public UI/SEO, audit/health, backup/restore/reconciliation, CLI, Docker/Compose, Nginx/TLS, supply chain, CI, tests, accessibility evidence, документацію, RC rehearsal, legal/trust baseline та обов’язкові attack scenarios.

Під час початкового read-only audit не змінювалися `app/`, `tests/`, workflows, manifests,
docs або deployment configs. Focused remediation pass після запиту користувача змінив source,
tests, lock і CI/deployment configs та оновив ті самі сім audit artifacts.

## 3. Environment

| Item | Value |
|---|---|
| Host | Windows NT 10.0.26100, x64 |
| Shell | PowerShell 7.6.3 |
| Timezone | Europe/Kiev |
| System Python | 3.12.10 |
| Target audit Python | uv-managed CPython 3.14.3 |
| Fallback Python | uv-managed CPython 3.13.12 |
| uv | 0.10.0, ізольовано у temporary audit tooling |
| Git | 2.54; repository metadata `.git` відсутня |
| Docker / Nginx / Trivy | не встановлені |
| Browser | in-app browser ізольований від host loopback |

Python 3.13 використовувався лише як fallback для збору часткових доказів після доведеного blocker на цільовому Python 3.14. Fallback PASS не замінює target PASS.

## 4. Evidence sources

- 354 source snapshot files у 70 directories; 190 Python files, 36 Jinja templates, 84 test modules.
- `pyproject.toml`, `.python-version`, `uv.lock`, `app/__init__.py`, README/CHANGELOG/architecture/release docs.
- 19 `PHASE-*.manifest` і `docs/phase-0-review.md`.
- `app/`, `alembic/`, `tests/`, `Dockerfile`, Compose, Nginx templates, scripts.
- 4 GitHub Actions workflows.
- Реальні command results: lock/export/sync, Ruff/mypy/pytest/coverage, Bandit/pip-audit, migrations, CLI, shell syntax, health endpoint, rehearsal.
- Official advisory: [GHSA-82w8-qh3p-5jfq](https://github.com/advisories/GHSA-82w8-qh3p-5jfq).

Відсутні у наданому snapshot: Git history/tag/commit identity, зовнішні CI run
URLs/artifacts та Docker/Trivy/browser runtime evidence. Workflow для точного RC
tag/archive/checksum/manifest/signed provenance реалізований, але має бути фактично виконаний
на protected tag до GO.

## 5. Overall verdict

**NO-GO (original full-audit verdict).** P1 findings SH-AUDIT-001…007 тепер закриті.
Практичні restore, clean Docker deployment, Nginx/TLS, Playwright/axe matrix і protected-tag
attestation run ще не виконані, тому focused remediation не є новим повним GO-аудитом.

## 6. Release blockers

1. Clean target dependency sync не збирає `pydantic-core==2.33.1` на Python 3.14.
2. Locked Ruff 0.11.7 не парсить `target-version = "py314"`; сучасний Ruff показує 687 lint errors і 46 unformatted files.
3. Playwright не задекларований у standard dev graph, але імпортується під час звичайних pytest/mypy.
4. Phase 18 infrastructure test має застаріле текстове expectation і падає незалежно від платформи.
5. Starlette 1.1.0 уразливий до unauthenticated urlencoded form-parsing DoS (CVSS 7.5).
6. CI `pip-audit` перевіряє isolated tool environment і дає false green.
7. Container CI викликає `docker/healthcheck.py`, якого немає в image.

Обов’язкові acceptance conditions після виправлень: green clean Linux CI, Docker/Compose/Nginx/TLS/Trivy runtime evidence, Chromium/Firefox/WebKit + axe, практичний backup/restore rehearsal і immutable RC archive/checksum, прив’язані до конкретного commit/tag.

## 7. Findings by severity

### SH-AUDIT-001

ID: SH-AUDIT-001  
Severity: P1  
Area: dependencies/reproducibility  
Title: Чисте locked-встановлення на цільовому Python 3.14 не збирається  
Status: resolved — clean Python 3.14 locked sync/import PASS  
Release blocker: yes

Requirement: `uv sync --all-groups --locked` має проходити на заявленому `>=3.14,<3.15`.  
Evidence: CPython 3.14.3, uv 0.10.0: build `pydantic-core==2.33.1` падає, бо PyO3 0.24.0 підтримує максимум Python 3.13; ABI-forward retry падає на `jiter==0.9.0`.  
Affected files: `pyproject.toml:6`, `uv.lock` packages `pydantic-core`/`jiter`, `Dockerfile:1-25`.  
Reproduction steps: `uv python install 3.14`; `uv lock --check`; `uv sync --all-groups --locked`.  
Observed result: exit 1 до створення runnable environment.  
Expected result: frozen install exit 0 на новому runner.  
Security or operational impact: Неможливо відтворити app image, CI або реліз із lock.  
Exploitability: Operational; гарантовано відтворюється на clean target.  
Recommendation: Оновити сумісний Pydantic dependency set і lock.  
Verification after fix: clean sync, import smoke і no-cache Docker build на Linux.

### SH-AUDIT-002

ID: SH-AUDIT-002  
Severity: P1  
Area: code quality/CI  
Title: Frozen Ruff gate не може стартувати, а baseline не clean  
Status: resolved — locked Ruff format/lint PASS  
Release blocker: yes

Requirement: Ruff format/lint critical gate має бути executable і green.  
Evidence: Ruff 0.11.7 exit 2: unknown `py314`; Ruff 0.15.22 exit 1: 687 errors, 46 files would reformat.  
Affected files: `pyproject.toml:29,35-76`, `uv.lock:556-577`, 46 Python files.  
Reproduction steps: `uvx --from ruff==0.11.7 ruff check .`; повтор із Ruff 0.15.22.  
Observed result: frozen gate не парсить config; supported tool знаходить великий debt.  
Expected result: обидва project Ruff gates exit 0.  
Security or operational impact: Critical CI gate не дає жодного reliable release signal.  
Exploitability: Не security exploit; детермінований release process failure.  
Recommendation: Оновити/pin Ruff з py314 support і очистити baseline.  
Verification after fix: frozen `ruff format --check` та `ruff check` exit 0.

### SH-AUDIT-003

ID: SH-AUDIT-003  
Severity: P1  
Area: tests/CI  
Title: Standard dev graph не містить Playwright для безумовних imports  
Status: resolved — Playwright locked; mypy and pytest standard graph PASS  
Release blocker: yes

Requirement: documented `uv sync --all-groups --locked` має бути достатнім для стандартних mypy/pytest.  
Evidence: clean fallback all-groups environment: pytest collection `ModuleNotFoundError: playwright`; mypy missing `playwright.sync_api` у двох files.  
Affected files: `pyproject.toml:20-31`, `tests/e2e/conftest.py:20`, `tests/e2e/accessibility.py:9`, `.github/workflows/ci.yml:55-59`.  
Reproduction steps: встановити exact all-groups export без manual Playwright; виконати `pytest` і `mypy`.  
Observed result: collection/type-check exit non-zero.  
Expected result: standard quality job повністю визначений lock graph.  
Security or operational impact: Main CI не може дійти до test execution.  
Exploitability: Operational, детерміновано на clean environment.  
Recommendation: Окрема pinned e2e group або коректне exclusion/lazy import.  
Verification after fix: clean standard pytest/mypy без ad-hoc dependency install.

### SH-AUDIT-004

ID: SH-AUDIT-004  
Severity: P1  
Area: tests/CI  
Title: Infrastructure-тест Phase 18 детерміновано застарів  
Status: resolved — UTF-8/current-flow infrastructure gate PASS  
Release blocker: yes

Requirement: Infrastructure quality gates мають перевіряти актуальну E2E поведінку і проходити.  
Evidence: `test_e2e_suite_contains_critical_flow_and_accessibility_matrix` очікує фразу `Створити категорію`, відсутню у current `test_full_flow.py`; 21 infrastructure tests PASS, цей test FAIL.  
Affected files: `tests/infrastructure/test_quality_gates_phase18.py:72-94`, `tests/e2e/test_full_flow.py`.  
Reproduction steps: `pytest -o addopts='' tests/infrastructure -q`.  
Observed result: assertion failure до browser execution.  
Expected result: stable behavioral/structural gate exit 0.  
Security or operational impact: Після інших fixes CI все одно лишається red.  
Exploitability: Operational; platform-independent.  
Recommendation: Замінити phrase matching на structural/behavioral assertion.  
Verification after fix: infrastructure suite exit 0 на Ubuntu.

### SH-AUDIT-005

ID: SH-AUDIT-005  
Severity: P1  
Area: security/dependencies  
Title: Starlette 1.1.0 має застосовну High DoS-вразливість  
Status: resolved — Starlette 1.3.1, bounded login parser and field-flood regression PASS  
Release blocker: yes

Requirement: Runtime dependencies не повинні мати немітигованих High vulnerabilities.  
Evidence: frozen export містить Starlette 1.1.0; pip-audit знаходить GHSA-82w8-qh3p-5jfq/CVE-2026-54283, CVSS 7.5, fixed 1.3.1. Код покладається на `request.form(max_fields=...)` у `app/routers/auth/dependencies.py:77-81`; Nginx global limit — 2g, Uvicorn workers — 1.  
Affected files: `uv.lock:588-596`, `app/routers/auth/dependencies.py:68-87`, `nginx/templates/production.conf.template:28`, `Dockerfile:67`.  
Reproduction steps: `pip-audit -r <frozen-runtime-requirements>`; перевірити advisory та code path.  
Observed result: attacker-controlled urlencoded body може обійти intended field limits і блокувати event loop/пам’ять.  
Expected result: patched parser або доведена compensating control.  
Security or operational impact: Unauthenticated availability loss.  
Exploitability: Network-reachable login/admin form endpoints; великий proxy body limit посилює ризик.  
Recommendation: Starlette >=1.3.1 і small per-route form body limits.  
Verification after fix: clean audit плюс regression/load test.

### SH-AUDIT-006

ID: SH-AUDIT-006  
Severity: P1  
Area: supply chain/CI  
Title: Dependency audit дає false green, бо перевіряє tool environment  
Status: resolved — CI/release verifier audit frozen runtime requirements  
Release blocker: yes

Requirement: CI audit має перевіряти саме frozen runtime dependency set.  
Evidence: exact CI command без `-r` дає 0 vulnerabilities; audit exported runtime requirements знаходить 7 advisory records у 4 packages, включно з High Starlette.  
Affected files: `.github/workflows/ci.yml:61-65`.  
Reproduction steps: порівняти `uvx --from pip-audit==2.10.1 pip-audit` та `... pip-audit -r <export>`.  
Observed result: green CI signal не відповідає deployable environment.  
Expected result: gate fails на відомій runtime vulnerability.  
Security or operational impact: Вразливі dependencies можуть бути схвалені до release.  
Exploitability: Supply-chain control failure.  
Recommendation: Audit frozen export/lock і зберігати report artifact.  
Verification after fix: negative-control vulnerable lock робить job red.

### SH-AUDIT-007

ID: SH-AUDIT-007  
Severity: P1  
Area: containers/CI  
Title: Container workflow запускає відсутній healthcheck path  
Status: resolved — installed container healthcheck path is used  
Release blocker: yes

Requirement: Container runtime job має виконуватися на actual image filesystem.  
Evidence: workflow викликає `python docker/healthcheck.py`; Dockerfile копіює script лише у `/usr/local/bin/software-hub-healthcheck.py`.  
Affected files: `.github/workflows/container-build.yml:102-108`, `Dockerfile:49-64`.  
Reproduction steps: побудувати image і `docker compose exec -T app ls /app/docker`.  
Observed result: `/app/docker/healthcheck.py` не створюється Dockerfile.  
Expected result: job використовує installed healthcheck path.  
Security or operational impact: Mandatory container CI fails; non-root/health evidence не завершується.  
Exploitability: Operational; deterministic після build.  
Recommendation: Викликати `/usr/local/bin/software-hub-healthcheck.py`.  
Verification after fix: full container workflow green.

### SH-AUDIT-008

ID: SH-AUDIT-008  
Severity: P2  
Area: supply chain  
Title: Third-party GitHub Actions не закріплені commit SHA  
Status: resolved — all third-party action refs are full commit SHAs; update automation enabled  
Release blocker: no

Requirement: CI dependencies мають бути immutable.  
Historical evidence: checkout@v5, upload-artifact@v4, trivy-action@v0.36.0 були mutable.  
Resolution evidence: усі 15 `uses:` у чотирьох workflows мають 40-hex commit SHA і version
comment; Trivy pinned до peeled commit `ed142fd…`; `.github/dependabot.yml` відкриває weekly
reviewed GitHub Actions updates.  
Affected files: усі 4 `.github/workflows/*.yml`.  
Reproduction steps: `rg -n "uses:" .github/workflows`.  
Observed result after fix: static regression scan — 15 refs, 0 mutable refs, 0 missing comments.  
Expected result: full commit SHA + version comment.  
Security or operational impact: Upstream tag movement може змінити trusted CI code.  
Exploitability: Залежить від компрометації upstream/tag.  
Recommendation: Pin SHA та автоматизувати reviewed updates.  
Verification after fix: workflow scan без mutable third-party tags.

### SH-AUDIT-009

ID: SH-AUDIT-009  
Severity: P2  
Area: release evidence  
Title: Кандидат не має наданого provenance та immutable RC evidence  
Status: resolved — immutable evidence generation and signed provenance are enforced in workflow  
Release blocker: no, але це mandatory acceptance condition

Requirement: Release має бути прив’язаний до конкретного commit/tag/archive/checksum та CI evidence.  
Historical evidence: `.git` відсутня; не було CI URLs/artifacts, archive,
checksum/signature, restore/Docker/browser evidence.  
Resolution evidence: RC workflow вимагає tag `v<app version>`, перевіряє його commit проти
`GITHUB_SHA`, будує deterministic `git archive | gzip -n`, створює SHA-256 та JSON manifest
із repository/tag/commit/run URL/digest, підписує чотири evidence subjects через
  `actions/attest`, зберігає Sigstore bundle та attestation ID/URL і завантажує унікальний
  commit/attempt artifact на 90 днів. Для private/internal repository ця GitHub capability
  вимагає Enterprise Cloud; неeligible tag run fail-closed, а не пропускає provenance.  
Affected files: `.github/workflows/release-candidate.yml`, `docs/release-candidate.md`,
`docs/production-acceptance.md`, `docs/release-checklist.md`.  
Reproduction steps: inventory snapshot і `git status/log/tag`.  
Observed result after fix: mechanism and static regressions PASS; фактичний signed artifact
буде створено лише наступним protected-tag run і лишається mandatory external acceptance.  
Expected result: audited immutable artifact із traceable green evidence.  
Security or operational impact: Неможливо довести, що deployed bits дорівнюють audited bits.  
Exploitability: Release integrity/provenance risk.  
Recommendation: Зібрати RC package на protected tagged commit.  
Verification after fix: незалежна checksum/tag/CI artifact verification.

### SH-AUDIT-010

ID: SH-AUDIT-010  
Severity: P3  
Area: test portability  
Title: Частина tests залежить від POSIX semantics/default encoding  
Status: resolved — explicit UTF-8 and platform-capability guards; Windows suite PASS  
Release blocker: no

Requirement: Test limitations мають бути явними й deterministic.  
Evidence: fallback full run — 460 passed, 43 failed, 10 skipped; більшість failures — chmod/symlink/fsync/executable-bit на Windows; theme test — cp1251 decode через `read_text()` без encoding.  
Affected files: `tests/unit/test_theme_assets_phase14.py:55-65`, storage/backup/infrastructure tests.  
Reproduction steps: повний pytest на Windows Python 3.13 fallback.  
Observed result: platform noise маскує cross-platform signal.  
Expected result: platform capability markers та explicit UTF-8.  
Security or operational impact: Низький; погіршує reliability локальної перевірки.  
Exploitability: Not applicable.  
Recommendation: Mark Linux-only semantics, explicit encoding.  
Verification after fix: documented platform jobs без accidental failures.

## 8. Requirements traceability

| Phase | Status | Independent evidence |
|---|---|---|
| 0 | PARTIAL | Scope/threat/decisions documented; Git baseline unavailable |
| 1 | PASS | Package skeleton, version and health imports statically consistent |
| 2 | PASS | Strict production config validators and config tests |
| 3 | PASS | SQLite PRAGMA/concurrency foundation and migration rehearsal |
| 4 | PASS | Domain schema, FK/unique/check constraints, Alembic head |
| 5 | PASS | Auth/session/lockout targeted tests |
| 6 | PASS | Admin auth/CSRF/common layout evidence |
| 7 | PASS | Category/tag CRUD service/route tests in fallback suite |
| 8 | PASS | Normalization/search/validation tests |
| 9 | PARTIAL | Storage containment tests; Windows symlink limits |
| 10 | PARTIAL | Upload pipeline 57 PASS/1 platform failure; real proxy/scanner absent |
| 11 | PARTIAL | Lifecycle policies and compensation reviewed/tested; target FS absent |
| 12 | PARTIAL | App download auth tests PASS; Nginx runtime absent |
| 13 | PASS | Public catalog integration tests PASS |
| 14 | PARTIAL | SEO/template checks PASS; browser/axe absent |
| 15 | PASS | Audit sanitization, request IDs, health evidence |
| 16 | PARTIAL | Backup/reconciliation design strong; restore not proven |
| 17 | BLOCKED | Docker unavailable; static CI path defect found |
| 18 | FAIL | Ruff/Playwright/stale infrastructure blockers; browser blocked |
| 19 | FAIL | Baseline status; provenance mechanism fixed, external tagged run/rehearsal pending |

Попередні claims:

- Version `1.0.0-rc.1` — CONFIRMED.
- Lock consistency (`uv lock --check`) — CONFIRMED.
- Clean Python 3.14 sync — CONTRADICTED.
- “503 tests passed” — NOT REPRODUCIBLE: 503 non-E2E cases executed, але 460 PASS / 43 FAIL на current host.
- Coverage 92.82% — NOT REPRODUCIBLE: 86.29% у fallback run із host-specific failures.
- Migration head/current/check — CONFIRMED на fallback SQLite.
- Docker/Trivy/browser matrix, protected Nginx delivery, backup restore, RC archive/checksum — NOT PROVIDED або BLOCKED.

## 9. Architecture

Статичний review підтвердив Router → Service → Repository/Storage separation. Repositories використовують `flush`, але не `commit`; caller-owned transaction реалізовано через `Database.transaction()` у `app/database/session.py:86-91`. Upload streaming/scanning відбувається до metadata transaction, а filesystem compensation обробляється на service boundaries. Raw SQL обмежений health `SELECT 1`, SQLite pragmas та partial-index declarations; user-controlled SQL string concatenation не знайдено.

Broad `except Exception` присутні лише на outer middleware/compensation/rollback/status boundaries і документовані `noqa`; silent broad swallowing у domain paths не виявлено.

## 10. Security

Bandit 1.9.4: 0 High, 0 Medium, 6 Low; reviewed findings — test/config string false positives, `xml.sax.escape`, fixed-command scanner subprocess без shell. Current-tree secret scan не знайшов private keys, cloud tokens або production secrets; знайдені лише явно test/rehearsal secrets. Git history secret scan неможливий без `.git`.

Runtime pip-audit знаходить 7 advisory records у click 8.1.8, idna 3.10, python-dotenv 1.1.0, Starlette 1.1.0. Click/idna/python-dotenv vulnerable APIs не імпортуються application code або не мають доведеного runtime reachability; вони залишаються dependency debt. Starlette High DoS є застосовним release blocker.

Attack scenarios:

| Scenario | Result | Evidence |
|---|---|---|
| Upload path traversal / `..` / backslash / NUL | PASS | `_reject_unsafe_relative_path`, storage security tests |
| Double extension, MIME/signature spoof | PASS | filename/signature/upload tests |
| Oversize multipart / Content-Length | PASS at app level | request guard/stream tests |
| URL-encoded field flood | FAIL | SH-AUDIT-005 |
| Interrupted upload/cleanup | PASS | upload stream/compensation tests |
| Symlink escape | PARTIAL | static reject/resolve; Windows creation privilege blocked full attack |
| Private/disabled/quarantine/rejected download | PASS app level | critical download tests |
| Wrong safe filename / invalid UUID | PASS | download route/service tests |
| Direct `/protected-downloads` | BLOCKED runtime | Nginx `internal` static PASS |
| HEAD increments counter | PASS | HEAD tests; route passes `count_download=False` |
| Unauthorized admin/IDOR | PASS | route dependencies and integration tests |
| Missing/invalid/oversized/cross-session CSRF | PASS | targeted CSRF suite |
| Lockout/expired/revoked session | PASS | targeted auth/session suite |
| Backup tamper/symlink | PARTIAL | checksum/regular-file code/tests; production FS run absent |
| Restore incompatible/corrupt backup | BLOCKED runtime | verify-before-restore static evidence |
| Host header poisons SEO | PASS static/tests | configured `public_base_url`, not Host |
| Error leaks secrets/path | PASS static/tests | safe handlers/log sanitization |
| Production admin IP fallback | PARTIAL | `.env.production.example` defaults deny; Nginx runtime absent |

## 11. Database/migrations

SQLite connections enable `foreign_keys=ON`, `busy_timeout`, WAL і configured synchronous mode. Schema має FK cascade/set-null, unique constraints, non-negative checks і partial unique current-stable release index.

Fresh temp SQLite rehearsal:

1. `alembic upgrade head` — PASS.
2. `alembic current` — `0002_phase4_domain_schema (head)`.
3. `alembic check` — no new upgrade operations.
4. `alembic downgrade base` — PASS.
5. Repeat upgrade/check — PASS.

Результат сильний, але виконаний на Python 3.13 fallback, бо target dependency graph не встановлюється.

## 12. Upload/storage/download

Upload stream bounded, SHA-256/magic assessment зберігаються, path plan генерує server-side names, файл спочатку переходить у quarantine, scanner працює поза event loop. Publish policies не дозволяють infected/error/invalid state; scanner unavailable свідомо приймається як documented MVP residual risk. Жодного extraction/execution uploaded content не знайдено.

Storage paths reject absolute/empty/dot/backslash/NUL components, resolve containment і можуть reject symlinks. Download authorizes state/visibility/storage size і повертає sanitized `Content-Disposition`, `Content-Type`, ETag, no-store та internal redirect. GET increments authorized-start aggregate; HEAD не increment.

Залишок: real Nginx `internal`, Range/resume, direct path denial і production filesystem semantics не прогнані.

## 13. Auth/session/CSRF

Passwords — Argon2id, dummy hash path для unknown user, generic failure semantics, rehash support. Login має failure count і timed lockout. Session token зберігається як hash; є idle й absolute expiry, revocation, user active check, bounded touch, hashed IP/User-Agent comparison. Production config вимагає distinct app/CSRF secrets, secure cookie і HTTPS.

CSRF має pre-auth login token та session-bound token з HMAC compare, TTL і size bounds. Inventory unsafe routes показує CSRF dependencies на admin mutations. Targeted auth/session/CSRF/download/public set — 56/56 PASS.

Окремо SH-AUDIT-005 стосується parser resource limits до CSRF verification, а не криптографічної CSRF схеми.

## 14. Backup/restore

Backup code використовує SQLite backup API, integrity check, manifest version, per-file SHA-256, manifest checksum, regular-file/symlink checks, atomic publish, retention lock і audit events. Restore verify-before-write, створює safety backup за замовчуванням, stages replacements, виконує migration upgrade та має rollback paths.

Практичний production-like Linux backup→tamper→verify→restore→rollback цикл не виконано. Windows run зустрів POSIX fsync/mode semantics. Тому backup — PARTIAL, restore — BLOCKED BY ENVIRONMENT і mandatory release acceptance condition.

## 15. Docker/Nginx

Static positives: non-root UID/GID, `cap_drop: ALL`, no-new-privileges, read-only root, tmpfs, pids limits, internal backend network, no Docker socket/privileged/host network. App image копіює мінімальний runtime, має one worker. Production Nginx: TLS 1.2/1.3, HSTS, `internal` download alias, symlink disable, dot/env/database/storage deny, security headers. Production example admin access defaults to deny include.

Runtime Docker/Nginx/TLS checks заблоковані відсутністю Docker/Nginx. Додатково app image build буде заблоковано SH-AUDIT-001, а workflow runtime — SH-AUDIT-007. Global `client_max_body_size 2g` недостатній проти SH-AUDIT-005 для urlencoded forms.

## 16. CI/supply chain

Чотири workflows покривають quality, E2E, containers і RC; critical steps не мають
`continue-on-error`. Усі third-party Actions pinned до reviewed commit SHA. RC job має
мінімальні `contents: read` та потрібні для Sigstore provenance `id-token: write` і
`attestations: write`; інші workflows зберігають `contents: read`.

Історичні workflow defects SH-AUDIT-001…009 виправлено. Регресійні tests блокують mutable
Action refs, неправильний runtime dependency audit, неправильний healthcheck path та
неповний RC evidence workflow. Фактичні Trivy/SARIF/tag-attestation artifacts мають бути
отримані на зовнішньому Ubuntu/GitHub runner.

## 17. Tests/accessibility

Знайдено 366 test functions і 513 collected cases: 503 non-E2E + 10 E2E. На fallback:

- exact locked graph до ручного Playwright: collection FAIL;
- після temporary Playwright: 460 PASS, 43 FAIL, 10 SKIP;
- coverage run: 86.29%, нижче 90%, через host-specific failures;
- critical auth/session/CSRF/download/public set: 56 PASS;
- upload/storage security set: 57 PASS, 1 mode failure;
- infrastructure subset: 21 PASS, 3 FAIL, з них один platform-independent stale assertion.

E2E suite містить three-browser matrix, mobile/desktop viewports, keyboard/DOM audit та axe-core WCAG A/AA serious/critical check. Фактичний Playwright/axe run blocked: browsers не встановлені, in-app browser не бачить host loopback.

## 18. Documentation

README, architecture, threat model, security, operations, deployment, backup/reconciliation, release candidate і acceptance docs є детальними та загалом відповідають коду. Вони чесно фіксують one-instance SQLite, optional ClamAV, one worker і CI-only gaps.

Водночас claims про 503 PASS, 92.82% coverage і release gates застаріли відносно current lock/suite. `pyproject.toml` декларує proprietary license; окремих LICENSE/NOTICE/third-party notices у snapshot немає. Для внутрішнього proprietary deployment це не автоматичний blocker, але юридична/third-party license перевірка має входити в acceptance.

## 19. Production operations

Local fallback Uvicorn `/health` повернув HTTP 200 з application/database/storage/disk `ok`. CLI parser має всі 14 required commands; destructive operations захищені `--yes` або `--apply`. Shell scripts проходять `bash -n`.

RC rehearsal через Git Bash не відтворив production path через Windows SQLite URL semantics. Немає rollback rehearsal, TLS certificate check, resource/disk pressure test, real log rotation/backup retention run або CI acceptance record.

## 20. Residual risks

- Optional ClamAV disabled by default: signed/magic/hash/quarantine controls не доводять відсутність malware.
- Single-instance SQLite/one worker — documented capacity and availability boundary.
- Offsite backup transport залежить від operator infrastructure.
- Symlink/permissions/fsync поведінка потребує Linux evidence.
- Direct Nginx internal/Range/TLS/admin-IP behavior перевірено лише статично.
- Git history/historical secret scan і exact RC identity відсутні у snapshot; наступний
  protected-tag workflow тепер fail-closed створює checksum manifest та signed provenance.
- Runtime dependency audit після remediation не знаходить відомих vulnerabilities; нові advisory
  можуть з’явитися до моменту promotion, тому frozen audit треба повторити в RC pipeline.

## 21. Final recommendation

Усі P1/P2/P3 закрито. Не просувати поточний `1.0.0-rc.1` лише на підставі focused remediation:
на новому Ubuntu runner ще потрібно виконати clean locked sync, повний quality/test/security
pipeline, no-cache Docker builds, Compose/Nginx/TLS/Trivy, three-browser axe matrix і практичний
backup/restore. Потім запустити новий protected RC tag, перевірити автоматично створені archive
SHA-256/evidence manifest/Sigstore attestation та повний CI evidence package і повторити
незалежний release audit.
