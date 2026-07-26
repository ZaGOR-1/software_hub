# Software Hub — Release Checklist

Цей checklist використовується для кожного release candidate. Пункти, які не застосовуються, мають містити письмове обґрунтування; їх не можна мовчки пропускати.

## 1. Scope і зміни

- [ ] Release scope відповідає затвердженій фазі.
- [ ] Out-of-scope функції не додані без ADR.
- [ ] Усі нові environment variables описані.
- [ ] Усі schema changes мають Alembic migration.
- [ ] CHANGELOG оновлений.
- [ ] Відомі обмеження задокументовані.
- [ ] Немає критичних `TODO`, `pass` або fake stubs у scope release.

## 2. Code quality

- [ ] `ruff format --check` проходить.
- [ ] `ruff check` проходить.
- [ ] `mypy` проходить.
- [ ] Unit tests проходять.
- [ ] Integration tests проходять.
- [ ] Security tests проходять.
- [ ] E2E smoke проходить.
- [ ] Coverage threshold виконано.
- [ ] Broad exception handlers перевірені й обґрунтовані.
- [ ] Немає `eval`, `exec`, unsafe deserialization або untrusted `shell=True`.

## 3. Database

- [ ] Міграції застосовуються на чистій SQLite database.
- [ ] Upgrade із попереднього release протестований.
- [ ] Downgrade перевірений, якщо він підтримується.
- [ ] `foreign_keys=ON` перевірено.
- [ ] WAL і busy timeout перевірено.
- [ ] Indexes для нових queries додані.
- [ ] Немає довгих transactions у upload/file operations.
- [ ] Перед destructive migration створено tested backup.

## 4. Authentication і sessions

- [ ] Default admin/password відсутні.
- [ ] Argon2id використовується.
- [ ] Login повертає generic errors.
- [ ] Login rate limit працює.
- [ ] Failed-attempt lockout працює.
- [ ] Session ID rotate після login.
- [ ] Idle timeout працює.
- [ ] Absolute lifetime працює.
- [ ] Revoked/expired session не приймається.
- [ ] Logout revoke server-side session.
- [ ] Cookie має `HttpOnly`, `Secure`, `SameSite` у production.
- [ ] Session token не логуються й не зберігаються raw у DB.

## 5. CSRF, XSS та authorization

- [ ] Усі state-changing routes використовують CSRF.
- [ ] Logout, upload, publish, disable, archive, backup і delete покриті.
- [ ] Missing/invalid/cross-session CSRF tests проходять.
- [ ] Jinja autoescape увімкнений.
- [ ] User/admin-entered content не використовує unsafe `|safe`.
- [ ] XSS payload tests проходять.
- [ ] Admin authorization перевіряється server-side.
- [ ] IDOR tests проходять.
- [ ] Private/unlisted/public rules перевірені.

## 6. Upload і storage

- [ ] Upload streaming, а не full-file read у RAM.
- [ ] Nginx і app upload limits узгоджені.
- [ ] Actual bytes контролюються незалежно від Content-Length.
- [ ] Extension allowlist працює.
- [ ] Magic bytes перевіряються.
- [ ] MIME spoof test проходить.
- [ ] Path traversal і null-byte tests проходять.
- [ ] SHA-256 обчислюється.
- [ ] Duplicate hash detection працює.
- [ ] Temp cleanup працює після помилки.
- [ ] Quarantine file не доступний публічно.
- [ ] Infected file не можна publish.
- [ ] Publish повторно перевіряє physical size і SHA-256.
- [ ] Publish виконує atomic `quarantine → software` move.
- [ ] DB failure після publish move повертає файл у quarantine.
- [ ] Disable й archive не видаляють physical bytes.
- [ ] Published file не можна видалити без попереднього disable/archive.
- [ ] Metadata-only deletion явно підтверджує створення orphan-файла.
- [ ] Permanent deletion використовує private staging і відновлення при DB failure.
- [ ] Final staged unlink failure створює operator-visible critical error.
- [ ] Storage permissions перевірені.
- [ ] Uploaded file не має executable permission від application.
- [ ] Reconciliation dry-run виконаний без невідомих inconsistencies.

## 7. Download

- [ ] FastAPI не стрімить великий file body.
- [ ] `X-Accel-Redirect` працює.
- [ ] Nginx internal location недоступний напряму.
- [ ] Physical path не розкривається.
- [ ] Public UUID lookup працює.
- [ ] Full Software → Release → ReleaseFile status chain перевіряється.
- [ ] Private, disabled, rejected і quarantine files недоступні.
- [ ] `HEAD` не збільшує count.
- [ ] Range/resume smoke test проходить.
- [ ] Safe `Content-Disposition` перевірений.

## 8. Nginx і HTTP security

- [ ] HTTP перенаправляється на HTTPS.
- [ ] TLS certificate valid.
- [ ] Renewal перевірено.
- [ ] HSTS увімкнений лише після перевірки HTTPS.
- [ ] CSP налаштована й сумісна з UI.
- [ ] `X-Content-Type-Options` присутній.
- [ ] Referrer-Policy присутній.
- [ ] Permissions-Policy присутній.
- [ ] Framing заборонений через CSP.
- [ ] `server_tokens off`.
- [ ] Directory listing вимкнений.
- [ ] `.env`, `.git`, DB, backups, logs і config недоступні HTTP.
- [ ] Host validation працює.
- [ ] Proxy headers приймаються лише від trusted Nginx.
- [ ] Admin restriction через VPN/IP перевірена або fallback risk прийнятий письмово.

## 9. Containers

- [ ] App container працює не від root.
- [ ] Multi-stage build використовується.
- [ ] `privileged: true` відсутній.
- [ ] Docker socket не mounted.
- [ ] Host network не використовується без ADR.
- [ ] Capabilities dropped.
- [ ] Root filesystem read-only, де можливо.
- [ ] Writable mounts мінімальні.
- [ ] Nginx storage mount read-only.
- [ ] Healthchecks green.
- [ ] Graceful shutdown перевірений.
- [ ] Trivy scan пройдено.
- [ ] Critical findings виправлені або документовано accepted risk.

## 10. Secrets і logs

- [ ] `.env` не в Git.
- [ ] Production secrets не baked into image.
- [ ] Weak/missing secrets блокують startup.
- [ ] Secret не генерується заново на кожному startup.
- [ ] Logs не містять password, cookie, CSRF token, Authorization header або upload body.
- [ ] Request ID присутній.
- [ ] Log rotation/retention налаштовані.
- [ ] Audit metadata пройшла allowlist/redaction review.

## 11. Backup і restore

- [ ] Pre-release backup створено.
- [ ] SQLite backup зроблено safe mechanism.
- [ ] Manifest містить application version і schema revision.
- [ ] Checksums verified.
- [ ] Retention cleanup не видалила потрібні copies.
- [ ] Offsite copy існує або ризик явно прийнятий.
- [ ] Restore виконаний у чистому test environment.
- [ ] Restored application проходить health і smoke tests.
- [ ] Restore procedure відповідає документації.

## 12. Operations

- [ ] `/health` перевіряє app, DB і storage без витоку secrets.
- [ ] Disk free-space threshold працює.
- [ ] Cleanup expired sessions виконаний.
- [ ] Cleanup temporary files виконаний.
- [ ] Audit log pagination/filter працює.
- [ ] Last backup відображається коректно.
- [ ] Common failure runbook актуальний.
- [ ] Rollback image/tag доступний.
- [ ] Rollback або restore rehearsal виконаний для risky release.

## 13. Final acceptance

- [ ] Production Compose config validated.
- [ ] DNS вказує на правильний server.
- [ ] `software.hotzagor.tech` працює через HTTPS.
- [ ] Public catalog smoke test пройдено.
- [ ] Admin login smoke test пройдено.
- [ ] Full upload → quarantine → publish → download → disable E2E пройдено.
- [ ] Security acceptance checklist пройдено.
- [ ] Release tag створено.
- [ ] Release notes опубліковані.
- [ ] Після deployment health і logs перевірені.


## 14. Release-candidate evidence

- [ ] Version matches `app.__version__`, `pyproject.toml`, `uv.lock` and CHANGELOG.
- [ ] `scripts/rehearse-release-candidate.sh` passes in the locked environment.
- [ ] CI, browser E2E, container build/Trivy and RC evidence workflows are green.
- [ ] RC tag resolves to the exact audited commit.
- [ ] Source archive and evidence-manifest SHA-256 checks pass independently.
- [ ] Persisted Sigstore bundle and GitHub build-provenance attestation verify for the expected repository.
- [ ] Immutable workflow artifact ID, run URL and container image digests are recorded.
- [ ] Fresh-host deployment rehearsal is recorded.
- [ ] Isolated/offsite restore rehearsal is recorded.
- [ ] Production acceptance owner and rollback owner are named.
- [ ] Remaining environment-specific items are explicitly deferred to Phase 20.
