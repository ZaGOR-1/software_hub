# Release Readiness Matrix — Software Hub 1.0.0-rc.1

Дата аудиту: 2026-07-26
Вердикт: **NO-GO (original full audit; re-audit pending)**
Рахунок статусів: **PASS 10 / FAIL 3 / BLOCKED BY ENVIRONMENT 8 / PARTIAL 9**

> Focused remediation update (2026-07-26): **7/7 P1, 2/2 P2 and 1/1 P3 resolved;
> 0 open P1/P2/P3**. Матриця й score нижче є baseline початкового аудиту та не
> перераховуються без повного Ubuntu Docker/Nginx/Trivy/Playwright/recovery re-audit.

| Remediation gate | Current status | Evidence |
|---|---|---|
| Python 3.14 frozen graph | PASS | clean locked sync/import |
| Ruff + strict mypy | PASS | 192 formatted files; 188 typed source files |
| Standard pytest / P3 portability | PASS | 500 passed, 17 intentional skips, coverage 92.16% on Windows |
| Runtime dependency audit | PASS | 27 dependencies, 0 vulnerabilities |
| Bandit | PASS | 0 findings |
| Container workflow path | PASS (static) | installed healthcheck path asserted |
| GitHub Actions supply chain | PASS (static) | 15/15 refs pinned to 40-hex SHA; version comments + Dependabot |
| RC provenance workflow | PASS (static) | exact tag/commit, deterministic archive, manifest/rehearsal attestation, persisted bundle + ID/URL, immutable artifact name |
| Full Linux production acceptance | BLOCKED BY ENVIRONMENT | pending new Ubuntu runner |

| Area | Status | Evidence | Blocker | Notes |
|---|---|---|---|---|
| requirements | PARTIAL | 19 PHASE manifests, `docs/phase-0-review.md`, phase review docs | Умова | Traceability наявна, але частина попередніх claims не відтворилася; Git/CI evidence не надано |
| architecture | PASS | `app/routers`, `app/services`, `app/repositories`, `app/storage`; scan commit/raw SQL | Ні | Repository не володіє commit; транзакції — у `Database.transaction()`/services; довгі file operations поза DB transaction |
| code quality | FAIL | Locked Ruff exit 2; Ruff 0.15.22: 687 errors, 46 unformatted; mypy exit 2 | Так | SH-AUDIT-002, SH-AUDIT-003 |
| dependencies | FAIL | `uv lock --check` PASS; clean `uv sync --locked` FAIL; pip-audit runtime FAIL | Так | SH-AUDIT-001, SH-AUDIT-005 |
| migrations | PASS | fresh upgrade/current/check/downgrade/upgrade/check — exit 0 на SQLite | Ні | Head `0002_phase4_domain_schema`; виконано на Python 3.13 fallback через blocker Python 3.14 |
| auth | PASS | Targeted auth/security tests: у складі 56/56 PASS | Ні | Argon2, dummy verification, generic failure, inactive user, lockout |
| sessions | PASS | Session service tests PASS; static review timeout/absolute expiry/revocation | Ні | Token hash у DB; HttpOnly/SameSite/Secure production validation |
| CSRF | PASS | CSRF inventory/cross-session/header/logout tests PASS | Ні | Unsafe admin routes використовують CSRF dependencies; окремо існує form-parser DoS у dependency |
| admin authorization | PASS | RequiredAdminSession/CSRFProtectedAdminSession inventory; route tests PASS | Ні | Не знайдено unsafe admin mutation без session/CSRF |
| upload | PARTIAL | 57 PASS, 1 OS-specific mode FAIL; static stream/signature/quarantine/scan review | Умова | Real Nginx multipart pipeline і ClamAV не виконані |
| storage | PARTIAL | Containment/traversal/filename tests; `safe_resolve()` review | Умова | Symlink attack повністю не доведено на Windows через privilege limitation |
| file lifecycle | PARTIAL | Policy/service tests у fallback suite; staged move/rollback review | Умова | Production filesystem semantics не прогнані |
| downloads | PARTIAL | Critical download tests PASS; X-Accel headers/static Nginx internal config | Умова | Real Nginx Range/internal-direct-access runtime заблокований |
| public UI | PASS | Public catalog/SEO integration tests у targeted set PASS | Ні | Server-rendered routes перевірено через TestClient |
| accessibility | BLOCKED BY ENVIRONMENT | E2E/axe suite існує; browser loopback недоступний | Умова | Chromium/Firefox/WebKit + axe не виконані |
| SEO | PASS | Canonical/sitemap/robots tests; canonical базується на `public_base_url` | Ні | Host-header poisoning у SEO статично не виявлено |
| audit/logging | PASS | Sanitization/request-id/static audit review; integration tests | Ні | Metadata bounded/sanitized; секретні keys відфільтровуються |
| health | PASS | Local Uvicorn fallback `/health` HTTP 200; DB/storage/disk checks `ok` | Ні | Не є доказом container health на target image |
| backup | PARTIAL | Manifest/checksum/integrity/atomic publish review; частина tests PASS | Умова | Повний Linux backup run не виконано; Windows fsync semantics спричинили failures |
| restore | BLOCKED BY ENVIRONMENT | Restore/rollback/tamper code review; production-like run відсутній | Так, умова | Без практичного restore GO заборонений |
| reconciliation | PARTIAL | Service/CLI/tests inventory | Умова | Повний production filesystem run не виконано |
| CLI | PARTIAL | `--help` для 14 required commands — exit 0 | Умова | Поведінку всіх destructive paths окремо не виконано; guards `--yes`/`--apply` наявні |
| Docker | BLOCKED BY ENVIRONMENT | Static Dockerfile/Compose review; `docker` відсутній | Так, умова | Clean build/runtime не виконано; SH-AUDIT-001 передбачувано блокує build |
| Nginx | BLOCKED BY ENVIRONMENT | Static production template review; `nginx`/Docker відсутні | Так, умова | `internal`, deny paths, HSTS/TLS налаштовані; runtime не доведено |
| TLS | BLOCKED BY ENVIRONMENT | TLS 1.2/1.3, HSTS, cert paths статично | Так, умова | Сертифікат, handshake, redirect і expiry не перевірено |
| CI | FAIL | Workflow review + локальне відтворення команд | Так | SH-AUDIT-001/002/003/004/006/007 |
| Trivy | BLOCKED BY ENVIRONMENT | Workflow має Trivy jobs; CLI/daemon відсутні | Так, умова | Немає SARIF або зовнішнього green evidence |
| Playwright | BLOCKED BY ENVIRONMENT | 10 E2E cases collected; browser binaries/loopback недоступні | Так, умова | SH-AUDIT-003 також ламає стандартний dev graph |
| documentation | PARTIAL | README, architecture, security, runbooks, phase docs | Умова | Документація повна, але release claims про sync/tests/coverage зараз не підтверджені |
| production rehearsal | BLOCKED BY ENVIRONMENT | Script syntax PASS; Git Bash run не відкрив Windows SQLite path | Так, умова | Немає clean Linux RC rehearsal, tag, archive/checksum та acceptance record |

## Score

| Category | Earned | Maximum | Rationale |
|---|---:|---:|---|
| Security | 14 | 25 | Сильні app-level auth/CSRF/storage/download controls, але застосовна High DoS і невалідний dependency audit |
| Data integrity/backup | 12 | 20 | Міграції пройшли; backup/restore не доведено в production-like Linux |
| Deployment/reproducibility | 2 | 15 | Clean target sync падає; Docker/Nginx runtime заблоковані |
| Functional correctness | 11 | 15 | 460 fallback tests PASS і 56 critical security tests PASS; target environment не відтворено |
| Test/CI evidence | 1 | 10 | Критичні CI gates мають кілька детермінованих blockers |
| Operations | 4 | 10 | Health/CLI/runbooks наявні; rehearsal і restore не виконані |
| Documentation/accessibility | 3 | 5 | Документація сильна; browser/axe matrix не виконана |
| **Total** | **47** | **100** | P1 cap 69 не перевищено |

Score не замінює вердикт: сім P1 автоматично вимагають **NO-GO**.
