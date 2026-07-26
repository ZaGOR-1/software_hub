# Artifact inventory — Software Hub release audit

Дата: 2026-07-26
Audited source root: `D:\work\software_hub`
Audit output root: `D:\work\software_hub\audit-output`

## 1. Audited snapshot baseline

| Type | Count | Notes |
|---|---:|---|
| Files before `audit-output` | 354 | Source snapshot і supplied evidence |
| Directories | 70 | Без temporary audit environments |
| Python files | 190 | `app`, `tests`, Alembic, healthcheck |
| Jinja templates | 36 | Public/admin/auth/error/component templates |
| Test Python modules | 84 | 366 `def test_*`; 513 collected cases |
| Alembic migrations | 2 | `0001`, `0002_phase4_domain_schema` |
| PHASE manifests | 19 | Phases 1–19; Phase 0 represented by review doc |
| GitHub workflows | 4 | CI, E2E, container-build, release-candidate |
| Release archives/checksums | 0 | Not provided |
| Git repository metadata | 0 | `.git` absent |

Repository hygiene evidence:

- `.env.example` і `.env.production.example` present; real `.env` absent.
- SQLite/runtime DB, backups, logs, private storage files absent.
- Private keys/certificates absent.
- Python caches, `node_modules`, coverage artifacts and browser artifacts absent.
- Symlinks absent.
- Files larger than 10 MB absent.
- `.gitignore` і `.dockerignore` cover secrets/runtime debris; Docker context intentionally omits tests/docs/manifests.

## 2. Primary source/config evidence

| Evidence | Purpose | Audit use |
|---|---|---|
| `SOFTWARE_HUB_FULL_RELEASE_AUDIT_PROMPT.md` | Audit specification | Required stages, severity/verdict/artifact format |
| `pyproject.toml` | Project metadata/tools/dependencies | Version, Python range, groups, Ruff/mypy/pytest/coverage |
| `.python-version` | Target interpreter | Python 3.14 |
| `uv.lock` | Frozen dependency graph | Reproducibility, exact versions, vulnerability audit |
| `app/__init__.py` | Runtime version | Version consistency |
| `README.md`, `CHANGELOG.md` | User/release claims | Previous-claim verification |
| `ARCHITECTURE.md`, `SECURITY.md` | Architecture/security claims | Independent code trace |
| `docs/` | Requirements/runbooks/reviews | Phase traceability, deployment, operations, acceptance |
| `PHASE-*.manifest` | Phase evidence | Phase 1–19 inventory |

## 3. Application evidence

| Area | Main evidence |
|---|---|
| Config/security defaults | `app/core/config.py`, `constants.py`, `.env*.example` |
| Password/auth | `app/core/security.py`, `app/services/auth_service.py` |
| Sessions/CSRF | `app/services/session_service.py`, `app/core/csrf.py`, `app/routers/auth/dependencies.py` |
| DB/transactions | `app/database/session.py`, `pragmas.py`, models/repositories |
| Migrations/schema | `alembic/env.py`, `alembic/versions/*` |
| Upload | `app/storage/upload.py`, `signatures.py`, `scanner.py`, `app/services/upload_service.py` |
| Storage containment | `app/storage/paths.py`, `manager.py`, `move.py`, `lifecycle.py` |
| File lifecycle | `app/services/file_service.py`, `policies.py` |
| Downloads | `app/services/download_service.py`, `app/routers/public/downloads.py` |
| Public UI/SEO | public routers/services/templates, `app/core/seo.py`, static assets |
| Audit/logging/health | `app/services/audit_service.py`, `app/core/logging.py`, middleware, status service |
| Backup/restore/reconciliation | `backup_service.py`, `reconciliation_service.py`, CLI |

## 4. Deployment/CI evidence

| Evidence | Purpose | Result class |
|---|---|---|
| `Dockerfile` | App image build/runtime/security | Static reviewed; runtime blocked |
| `nginx/Dockerfile` | Edge image | Static reviewed; runtime blocked |
| `docker-compose.yml` | Base topology/security | Static reviewed; Docker blocked |
| `docker-compose.production.yml` | Production overlay/TLS | Static reviewed; Docker blocked |
| `nginx/templates/*.template` | Routing/TLS/internal download | Static reviewed; Nginx blocked |
| `nginx/snippets/*` | Headers/admin access/proxy policy | Static reviewed |
| `docker/*.sh`, `scripts/*.sh` | Entrypoint/health/deploy/backup/RC | `bash -n` PASS; RC runtime blocked |
| `.github/workflows/ci.yml` | Python quality/security | P1 remediated; action refs SHA-pinned |
| `.github/workflows/e2e.yml` | Browser/axe | Static present; runtime blocked |
| `.github/workflows/container-build.yml` | Build/Trivy/runtime | Healthcheck fixed; Trivy/action refs SHA-pinned; runtime blocked |
| `.github/workflows/release-candidate.yml` | RC packaging | Exact tag/commit + deterministic archive/checksums + manifest + signed attestation enforced |

## 5. Test evidence

| Evidence set | Result |
|---|---|
| Full declared graph before Playwright | Collection FAIL |
| Full fallback graph after temporary Playwright | 460 PASS / 43 FAIL / 10 SKIP |
| Coverage fallback | 86.29%; threshold not met on host |
| Critical auth/session/CSRF/download/public selection | 56 PASS |
| Upload/storage security selection | 57 PASS / 1 OS-specific FAIL |
| Infrastructure selection | 21 PASS / 3 FAIL |
| Fresh Alembic rehearsal | upgrade/current/check/downgrade/upgrade/check PASS |
| CLI help inventory | 14/14 required commands PASS |
| Shell syntax | PASS |
| Local fallback health | HTTP 200, all checks `ok` |
| Browser/axe | BLOCKED BY ENVIRONMENT |
| Docker/Nginx/TLS/Trivy | BLOCKED BY ENVIRONMENT |
| Production-like restore | BLOCKED BY ENVIRONMENT |

## 6. Security/supply-chain evidence

| Tool/evidence | Version | Result |
|---|---|---|
| Bandit | 1.9.4 | 0 High, 0 Medium, 6 Low reviewed |
| pip-audit, CI-exact no args | 2.10.1 | False green; audits tool env |
| pip-audit, frozen runtime export | 2.10.1 | 7 advisory records/4 packages; applicable High Starlette |
| Ruff locked | 0.11.7 | Config parse FAIL on py314 |
| Ruff supported comparison | 0.15.22 | 687 lint errors, 46 unformatted files |
| Current-tree secret pattern scan | ripgrep | No production key/token evidence |
| Git-history secret scan | N/A | BLOCKED: `.git` absent |
| Trivy | N/A | BLOCKED: tool/images absent |
| Official advisory | GHSA-82w8-qh3p-5jfq | Starlette form parsing DoS, fixed 1.3.1 |

## 7. Temporary audit evidence

Temporary work was confined to user temp space:

- `%TEMP%\software-hub-release-audit-019f9ecc`
  - isolated source copy;
  - Python 3.13 fallback venv;
  - temporary SQLite/storage/backup/rehearsal files;
  - generated requirements export.
- `%TEMP%\software-hub-audit-tools`
  - isolated uv 0.10.0 tool.

Temporary secrets were audit-only fixed values in a temporary process/copy. No production credentials were used.

Cleanup result:

- `%TEMP%\software-hub-audit-tools` видалено повністю.
- Із temporary work copy видалено 61 children, включно з `.venv`, `.venv313`, runtime SQLite/storage/backup directories, requirements exports і audit-only secrets.
- Windows ACL заборонив поточному процесу читати або видалити один залишковий `%TEMP%\software-hub-release-audit-019f9ecc\.pytest_cache`; через це порожній parent не можна прибрати повністю. Це environment cleanup limitation, не release artifact і не зміна source tree.

### Focused P1 remediation evidence — 2026-07-26

| Artifact / source | Evidence |
|---|---|
| `uv.lock` | Clean CPython 3.14 graph; FastAPI 0.140.0, Starlette 1.3.1, Pydantic 2.13.4, Ruff 0.15.22, Playwright 1.61.0 |
| `test-results/quality/pytest-p1-remediation.xml` | Full standard suite: 497 passed, 17 intentional skips |
| `coverage.xml` | Combined coverage 92.16% from terminal report |
| `test-results/quality/requirements-p1-remediation.txt` | Frozen no-dev runtime export |
| `test-results/quality/pip-audit-p1-remediation.json` | 27 dependencies, 0 vulnerabilities |
| `test-results/quality/bandit-p1-remediation.json` | 0 findings |
| `.github/workflows/ci.yml` | Frozen runtime audit semantics |
| `.github/workflows/container-build.yml` | Installed app healthcheck path |
| `.github/workflows/e2e.yml` | Locked Playwright graph without ad-hoc `--with` |

### Focused P2/P3 remediation evidence — 2026-07-26

| Artifact / source | Evidence |
|---|---|
| `.github/workflows/*.yml` | Static scan: 15 third-party `uses:`, all 40-hex commit SHA with version comments |
| `.github/dependabot.yml` | Weekly reviewed GitHub Actions update PR configuration |
| `.github/workflows/release-candidate.yml` | Exact tag/commit validation, deterministic archive, SHA-256 manifest/rehearsal attestation, persisted Sigstore bundle + ID/URL, immutable commit/attempt artifact |
| `tests/infrastructure/test_quality_gates_phase18.py` | Mutable Action and update-automation regression |
| `tests/infrastructure/test_release_candidate_phase19.py` | Provenance/evidence invariant regression |
| `test-results/quality/pytest-p2p3-remediation.xml` | Full Windows suite: 500 passed, 17 intentional skips |
| `coverage.xml` | Combined coverage 92.16% |

## 8. Missing or externally blocked evidence

1. `.git` history, branch, clean worktree, commit SHA and tags.
2. Historical secret scan.
3. CI run URLs and uploaded JUnit/coverage/SARIF/browser artifacts.
4. Executed protected-tag RC artifact/checksums/attestation and image digests
   (generation/verification workflow is implemented; external run pending).
5. Docker daemon and production-like Linux containers.
6. Nginx/TLS runtime and certificates.
7. Trivy filesystem/image reports.
8. Installed Chromium/Firefox/WebKit and axe runtime output.
9. Production-like backup/restore/rollback evidence.
10. Resource pressure, log rotation and real operator acceptance record.

## 9. Generated audit package

Рівно сім постійних audit artifacts:

1. `AUDIT_REPORT.md` — головний незалежний звіт.
2. `RELEASE_READINESS_MATRIX.md` — 30-area status/evidence matrix і score.
3. `RELEASE_BLOCKERS.md` — P1 stop-ship items та mandatory conditions.
4. `REMEDIATION_PLAN.md` — Wave 0–4 порядок виправлень.
5. `FINDINGS.json` — machine-readable 10 findings.
6. `COMMAND_RESULTS.md` — command-by-command results та interpretation.
7. `ARTIFACT_INVENTORY.md` — цей evidence inventory.

Жодних інших файлів у `audit-output/` не передбачено.
