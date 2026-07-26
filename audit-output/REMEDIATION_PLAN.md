# Remediation plan — Software Hub 1.0.0-rc.1

Поточний стан: **7/7 P1, 2/2 P2, 1/1 P3 RESOLVED; FULL RE-AUDIT PENDING**.  
Мета: створити новий відтворюваний RC, а не повторно позначити `1.0.0-rc.1` готовим.

## Focused remediation completion — 2026-07-26

- SH-AUDIT-001: resolved — clean Python 3.14 lock/sync/import.
- SH-AUDIT-002: resolved — Ruff format/lint clean.
- SH-AUDIT-003: resolved — locked Playwright + green strict mypy/pytest graph.
- SH-AUDIT-004: resolved — current UTF-8 infrastructure assertion.
- SH-AUDIT-005: resolved — Starlette 1.3.1 + bounded login parser/body limits.
- SH-AUDIT-006: resolved — frozen runtime requirements audited in CI/release verifier.
- SH-AUDIT-007: resolved — installed container healthcheck path.
- SH-AUDIT-008: resolved — 15/15 third-party Actions pinned to reviewed commit SHA;
  weekly reviewed update automation configured.
- SH-AUDIT-009: resolved — exact RC tag/commit gate, deterministic archive/checksums,
  evidence manifest, signed rehearsal/provenance, persisted Sigstore bundle + ID/URL and
  immutable artifact naming.
- SH-AUDIT-010: resolved — explicit UTF-8/platform capability guards; latest Windows
  full suite 500 passed, 17 intentional skips, coverage 92.16%.

Наступний активний етап — clean Ubuntu re-audit і фактичний protected-tag evidence run;
історичні waves нижче збережено як traceability виконаних рішень.

## Wave 0 — stop-ship

1. Заблокувати promotion/tagging/deployment поточного RC.
2. Зареєструвати SH-AUDIT-001…007 у issue tracker і призначити owners.
3. Зберегти цей audit package як baseline evidence.
4. Не послаблювати branch protection, coverage, Ruff, security audit або container gates заради green status.

Exit criteria:

- Немає deployment/promotion поточного RC.
- Для кожного P1 є owner, fix PR і verification evidence.

## Wave 1 — security/data integrity

### 1.1 Patch runtime dependency vulnerability

- Оновити сумісний FastAPI/Starlette dependency set до Starlette ≥1.3.1.
- Перегенерувати lock, не редагувати lock вручну.
- Додати regression для `application/x-www-form-urlencoded` field flood.
- В Nginx задати малий body limit для `/admin/login` і звичайних `/admin/` forms; upload route лишити з окремою керованою межею.

### 1.2 Fix dependency audit semantics

- Створювати frozen runtime export у CI.
- Аудитити саме export через pinned pip-audit.
- Зберігати machine-readable report.
- Додати negative control або fixture workflow test, що відома vulnerable dependency робить gate red.

### 1.3 Prove recovery

- На production-like Ubuntu filesystem виконати backup→verify.
- Модифікувати manifest/file і довести tamper rejection.
- Виконати restore із safety backup.
- Перевірити SQLite `integrity_check`, Alembic head, file checksums і public behavior.
- Виконати rollback та retention cleanup.

Exit criteria:

- Runtime audit без High/Critical advisories або formal accepted mitigation.
- Form-flood test не блокує service.
- Повний restore rehearsal задокументований.

## Wave 2 — deployment/reproducibility

### 2.1 Repair Python 3.14 frozen environment

- Оновити Pydantic/pydantic-core/jiter до Python 3.14-compatible set.
- Перевірити доступність wheels для target Linux architecture або успішний reproducible source build.
- `uv lock --check` і clean `uv sync --all-groups --locked`.
- Runtime import/version/health smoke.

### 2.2 Repair container workflow

- Змінити app healthcheck path на `/usr/local/bin/software-hub-healthcheck.py`.
- Виконати no-cache app/nginx builds.
- Перевірити image user, filesystem, capabilities, mounts, health.
- Запустити Compose production overlay з test TLS/domain config.

### 2.3 Edge and security scans

- Trivy filesystem/app/nginx images.
- Nginx direct `/protected-downloads` denial, authorized X-Accel delivery, Range/HEAD.
- TLS redirect, protocols, HSTS, cert paths/expiry.
- Перевірити default-deny admin access include й explicit allow override.

Exit criteria:

- Clean target sync і both images build.
- Container workflow повністю green.
- Trivy threshold та Nginx/TLS acceptance green.

## Wave 3 — quality/operations

### 3.1 Restore executable quality gates

- Pin Ruff з `py314` support.
- Запустити formatter для 46 files у reviewable commit.
- Розібрати 687 lint findings за категоріями; fixes і narrowly justified ignores окремо.
- Не знижувати rule set лише для проходження gate.

### 3.2 Normalize test dependency graph

- Визначити `e2e` dependency group із pinned Playwright або isolate E2E modules від standard collection.
- Виправити mypy package-base/missing import configuration.
- Замінити stale phrase assertion у Phase 18 infrastructure test.
- На Linux запустити full pytest з coverage ≥90%.

### 3.3 Browser/accessibility and operations

- Full flow у Chromium/Firefox/WebKit, mobile/desktop.
- axe-core serious/critical = 0, keyboard/focus/theme tests.
- Перевірити health failure modes, disk pressure, graceful restart, log fields/redaction.
- Прогнати CLI dry-run/apply/yes guards для maintenance commands.

Exit criteria:

- Ruff/mypy/pytest/coverage/pre-commit green.
- Browser/axe matrix green.
- Operations checklist має фактичні artifacts.

## Wave 4 — low-priority improvements

1. **DONE:** Pin усі third-party GitHub Actions повними SHA та контролювати updates через
   reviewed Dependabot PR.
2. **DONE:** Додати explicit `encoding="utf-8"` у text-reading tests.
3. **DONE:** Маркувати POSIX-only filesystem tests і документувати supported local platforms.
4. Review/suppress із поясненнями Bandit Low false positives.
5. Додати third-party license inventory/NOTICE, якщо це вимагає distribution policy.
6. Переглянути Click/idna/python-dotenv advisories після dependency update навіть якщо vulnerable APIs зараз не reachable.

Exit criteria:

- Supply-chain references immutable.
- Test results не містять platform/encoding noise.
- Legal/trust acceptance підписана owner.

## Final re-audit gate

Новий RC може отримати повторний аудит лише якщо надано:

- commit SHA + tag;
- `uv.lock` і frozen runtime export;
- green CI URLs/artifacts;
- Docker image digests;
- Trivy reports;
- Playwright/axe artifacts;
- backup/restore rehearsal log;
- RC archive/checksums, evidence manifest, immutable artifact ID and verified provenance;
- список resolved finding IDs і residual-risk approvals.

Після цього повторити весь master audit, а не лише сім regression checks.
