# Software Hub — Threat Model

**Статус:** reviewed for `1.0.0-rc.1`  
**Дата:** 2026-07-26  
**Метод:** asset/threat-oriented аналіз із категоріями STRIDE  
**Потребує перегляду:** перед production release і після будь-якої зміни trust boundaries

## 1. Мета

Цей документ визначає активи, trust boundaries, потенційних нападників, основні загрози, security controls і residual risks для Software Hub.

Threat model не стверджує, що система «абсолютно безпечна». Він визначає, які ризики MVP зобов’язаний знижувати, тестувати й документувати.

## 2. Архітектура та trust boundaries

```text
Internet user
   │ untrusted HTTP input
   ▼
Nginx public boundary
   ├── TLS / rate limit / headers
   ├── static files
   └── proxy to FastAPI
          │ trusted internal network only
          ▼
FastAPI application
   ├── public routes
   ├── authenticated admin routes
   ├── application services
   ├── repositories
   └── storage services
          │
          ├── SQLite database
          ├── temporary/quarantine storage
          ├── permanent software storage
          └── backups/logs

Admin browser
   │ authenticated but still untrusted input
   └───────────────────────────────► Nginx/FastAPI
```

### Trust boundaries

1. Internet → Nginx.
2. Nginx → FastAPI.
3. Anonymous user → authenticated admin session.
4. HTTP metadata → domain model.
5. Uploaded bytes → temporary/quarantine storage.
6. Quarantine → permanent public-download storage.
7. Application → SQLite.
8. Application/Nginx → host filesystem.
9. Production host → offsite backup location.

## 3. Активи

| Актив | Чому важливий |
|---|---|
| Admin credentials | повний контроль каталогу й файлів |
| Active session tokens | дозволяють admin actions без пароля |
| CSRF secrets/tokens | захист state-changing actions |
| Application secrets | підпис/генерація security material |
| SQLite database | users, sessions, metadata, audit, statistics |
| Uploaded binaries | можуть бути цінними, шкідливими або підміненими |
| Permanent storage | джерело публічних downloads |
| Quarantine/temp | містить неперевірений content |
| Backups | повна копія критичних даних |
| Audit logs | forensic trail адміністративних дій |
| Domain/TLS config | довіра користувачів і захист traffic |
| Server/VM | контроль усієї системи |
| Software reputation | користувачі довіряють опублікованим файлам |

## 4. Потенційні нападники

### Anonymous remote attacker

Має доступ до public routes і може:

- автоматизувати requests;
- підбирати UUID/slugs;
- надсилати malformed input;
- тестувати injection, traversal і Host header attacks;
- створювати load на login/download/search.

### Attacker із викраденим admin password

Може спробувати login, upload malware, publish file, видалити metadata або backups.

### Attacker із викраденою session cookie

Має тимчасовий authenticated access до меж session lifetime, якщо cookie не revoked.

### Malicious або compromised administrator workstation

Може надсилати легітимно authenticated небезпечні files/actions.

### Local attacker на host/VM

За наявності filesystem access може читати database, secrets і backups. Application-level controls не захищають від повного root compromise.

### Supply-chain attacker

Може використовувати vulnerable або compromised dependency/container base image.

## 5. Security assumptions

- Ubuntu host регулярно оновлюється.
- SSH доступ лише за keys, root/password login вимкнений.
- Docker daemon і host root не скомпрометовані.
- Nginx є єдиним public ingress до FastAPI.
- FastAPI port не опублікований напряму в Internet.
- Production secrets мають достатню entropy і не комітяться в Git.
- Admin використовує унікальний сильний пароль.
- DNS registrar/account захищені MFA поза межами application.
- Offsite backup credentials не зберігаються в public repository.

Якщо ці припущення порушені, residual risk суттєво зростає.

## 6. Матриця загроз

### T01. Brute-force login

- **Категорія:** Spoofing
- **Вектор:** багато спроб пароля або username enumeration.
- **Вплив:** takeover admin account.
- **Controls:** Argon2id; generic error; Nginx rate limit; failed counter; 5 attempts/15-minute lockout; audit; optional VPN/IP restriction.
- **Tests:** unknown/wrong password equivalence; rate limit; lockout; expiry.
- **Residual risk:** password spraying із distributed IP; DoS lockout відомого username.

### T02. Session fixation

- **Категорія:** Spoofing/Elevation of Privilege
- **Вектор:** reuse session identifier before and after login.
- **Вплив:** attacker отримує authenticated session.
- **Controls:** create new cryptographically random token after login; invalidate previous session; secure cookie.
- **Tests:** pre-login cookie cannot authorize post-login session.
- **Residual risk:** викрадення cookie після login поза application.

### T03. Session theft/replay

- **Категорія:** Spoofing
- **Вектор:** XSS, malware, insecure transport, logs.
- **Вплив:** admin impersonation.
- **Controls:** HTTPS; HttpOnly/Secure/SameSite; no token logs; hash token in DB; idle/absolute timeout; revocation; CSP.
- **Residual risk:** compromised admin endpoint/device.

### T04. CSRF admin action

- **Категорія:** Tampering/Elevation of Privilege
- **Вектор:** authenticated admin visits malicious page.
- **Вплив:** publish/delete/backup/change without intent.
- **Controls:** session-bound CSRF token; SameSite; POST-only writes; confirmation for destructive actions.
- **Tests:** missing/invalid/cross-session token.
- **Residual risk:** browser extension або compromised same-origin content.

### T05. Stored/reflected XSS

- **Категорія:** Tampering/Elevation of Privilege
- **Вектор:** software name, descriptions, filename, URL або query містить HTML/JS.
- **Вплив:** session abuse, malicious admin actions, UI spoofing.
- **Controls:** Jinja autoescape; plain text content; no arbitrary HTML; no untrusted `|safe`; CSP; no untrusted `innerHTML`; URL validation.
- **Tests:** common payloads in every displayed field.
- **Residual risk:** future Markdown/HTML feature could reopen risk.

### T06. SQL injection

- **Категорія:** Tampering/Information Disclosure
- **Вектор:** search/filter/form input у dynamic query.
- **Вплив:** data disclosure, corruption, auth bypass.
- **Controls:** SQLAlchemy ORM/parameterization; enum filters; bounded pagination; no SQL concatenation.
- **Tests:** payloads in search, sort, IDs and filters.
- **Residual risk:** future raw SQL migration/reporting code.

### T07. Path traversal

- **Категорія:** Information Disclosure/Tampering
- **Вектор:** filename, URL-encoded `..`, separators, absolute path, null byte.
- **Вплив:** read/write/delete outside storage root.
- **Controls:** public UUID lookup; server-generated storage names; resolved-path containment; no user path; normalize/reject suspicious names.
- **Tests:** POSIX/Windows/encoded/double-encoded traversal and null byte.
- **Residual risk:** implementation bugs around symlinks or cross-platform path handling.

### T08. Malicious upload

- **Категорія:** Tampering/Elevation of Privilege
- **Вектор:** EXE/MSI/archive із malware, spoofed extension або polyglot content.
- **Вплив:** distribution of malware; reputation damage; storage abuse.
- **Controls:** admin-only upload; CSRF; size limit; extension + magic bytes; hash; quarantine; optional scanner; manual publish; no execution/extraction.
- **Tests:** MIME spoof, double extension, invalid signatures, scanner infected/unavailable.
- **Residual risk:** clean scanner result не гарантує safety; trusted admin can intentionally publish malware.

### T09. Upload resource exhaustion

- **Категорія:** Denial of Service
- **Вектор:** huge/chunked/interrupted uploads, many temp files.
- **Вплив:** disk/RAM exhaustion, service outage.
- **Controls:** Nginx and app limits; streaming; actual byte count; free-space preflight; temp cleanup; admin-only; rate limiting/timeouts.
- **Tests:** missing/false Content-Length, interrupted upload, disk threshold.
- **Residual risk:** authorized admin accidentally fills disk.

### T10. Direct access to protected storage

- **Категорія:** Information Disclosure
- **Вектор:** request internal URI, directory listing, guessed storage path.
- **Вплив:** bypass statuses/visibility/statistics.
- **Controls:** Nginx `internal`; storage outside public root; no directory listing; Nginx read-only mount only for permanent files.
- **Tests:** direct `/protected-downloads/`, dotfiles, DB/backups paths.
- **Residual risk:** Nginx misconfiguration.

### T11. IDOR / authorization bypass

- **Категорія:** Elevation of Privilege/Information Disclosure
- **Вектор:** change object ID, call admin action directly, access private file.
- **Вплив:** unauthorized modification/download.
- **Controls:** server-side authorization for every route; status chain checks; public UUID not sufficient authorization; generic 404 policy.
- **Tests:** cross-object IDs, anonymous admin POST, private/unlisted/disabled combinations.
- **Residual risk:** future role system complexity.

### T12. State transition abuse

- **Категорія:** Tampering
- **Вектор:** publish rejected/quarantine file, current draft release, repeated destructive action.
- **Вплив:** invalid public state або data loss.
- **Controls:** centralized service transitions; transactions; idempotency where appropriate; audit; confirmations.
- **Tests:** every invalid transition and repeated operation.
- **Residual risk:** DB/filesystem partial failure.

### T13. DB/filesystem inconsistency

- **Категорія:** Tampering/Denial of Service
- **Вектор:** crash між move та commit, permission error, manual file change.
- **Вплив:** metadata without file, orphan file, wrong checksum.
- **Controls:** temp/quarantine; atomic move; short transactions; compensation; reconciliation dry-run; health/logging.
- **Tests:** injected DB/move failures and process interruption simulations.
- **Residual risk:** power/filesystem failure around durability boundaries.

### T14. Sensitive file exposure

- **Категорія:** Information Disclosure
- **Вектор:** request `.env`, SQLite, backups, `.git`, logs, config.
- **Вплив:** secrets/account takeover/full data disclosure.
- **Controls:** outside web-root; explicit Nginx deny; no directory listing; separated mounts; container permissions.
- **Tests:** HTTP requests for known sensitive paths.
- **Residual risk:** deployment operator copies files into static root.

### T15. Host header / proxy spoofing

- **Категорія:** Spoofing
- **Вектор:** malicious Host/X-Forwarded-* headers.
- **Вплив:** poisoned links, wrong scheme, audit evasion, redirect abuse.
- **Controls:** trusted hosts; Nginx overwrites proxy headers; app trusts known proxy only; canonical public base URL.
- **Tests:** invalid Host and direct app access.
- **Residual risk:** wrong network exposure of app port.

### T16. SSRF through metadata URLs

- **Категорія:** Information Disclosure/Denial of Service
- **Вектор:** source/official URL points to internal service.
- **Вплив:** only if server fetches URL.
- **Controls:** MVP stores/renders validated URLs but never fetches them server-side.
- **Tests:** ensure no fetch code/path exists.
- **Residual risk:** future import/sync feature.

### T17. Audit log leakage or tampering

- **Категорія:** Repudiation/Information Disclosure
- **Вектор:** secrets in metadata, deleting/editing logs, log injection.
- **Вплив:** compromised forensics або secret leak.
- **Controls:** metadata allowlist; structured logs; no secrets; append-only application API; escaped rendering; retention and backup.
- **Tests:** redaction, newline/log injection, pagination/filter authorization.
- **Residual risk:** host root can modify logs.

### T18. Backup compromise

- **Категорія:** Information Disclosure/Tampering
- **Вектор:** public backup path, weak permissions, corrupted archive.
- **Вплив:** full data disclosure або failed recovery.
- **Controls:** outside web-root; restrictive permissions; manifest/checksum; offsite copy; restore rehearsal.
- **Tests:** corrupted checksum, unauthorized HTTP access, restore on clean environment.
- **Residual risk:** offsite credential compromise; unencrypted backup media unless deployment adds encryption.

### T19. Dependency/container supply chain

- **Категорія:** Tampering/Elevation of Privilege
- **Вектор:** vulnerable або malicious package/base image.
- **Вплив:** code execution/data compromise.
- **Controls:** uv.lock; trusted package indexes; pip-audit; Bandit; Trivy; minimal image; reviewed updates; no production secrets in CI.
- **Tests:** CI security jobs.
- **Residual risk:** zero-days and compromised upstream releases.

### T20. Container breakout/excess privileges

- **Категорія:** Elevation of Privilege
- **Вектор:** app vulnerability плюс privileged container/capabilities/socket.
- **Вплив:** host takeover.
- **Controls:** non-root; no privileged; no Docker socket; drop capabilities; read-only root FS; narrow mounts; current runtime patches.
- **Tests:** inspect runtime user/mounts/capabilities.
- **Residual risk:** container runtime/kernel vulnerabilities.

### T21. Denial of service through search/download/login

- **Категорія:** Denial of Service
- **Вектор:** expensive queries, request flood, range abuse.
- **Вплив:** CPU/DB/network saturation.
- **Controls:** Nginx rate limits; bounded query length; pagination; indexes; Nginx file delivery; timeouts; one worker matched to SQLite.
- **Tests:** pagination bounds, query length, basic load smoke.
- **Residual risk:** volumetric attacks require upstream protection not included in MVP.

### T22. Unsafe destructive operation

- **Категорія:** Tampering/Repudiation
- **Вектор:** accidental click, crafted POST, confusing UI.
- **Вплив:** permanent file/data loss.
- **Controls:** separate archive/disable/delete/permanent-delete actions; CSRF; explicit confirmation; audit; backup; no GET writes.
- **Tests:** GET cannot mutate; missing confirmation; repeated action.
- **Residual risk:** authorized admin intentionally confirms wrong action.

## 7. Security acceptance priorities

### Must fix before production

- authentication/session/CSRF failure;
- path traversal;
- direct protected storage access;
- private/disabled/quarantine download;
- upload size/signature bypass;
- `.env`/DB/backup exposure;
- secrets in logs;
- root/privileged container;
- backup that cannot be restored;
- critical known dependency/container vulnerability without documented mitigation.

### May be accepted temporarily with documentation

- download counter measures start, not completion;
- optional scanner unavailable;
- no upstream volumetric DDoS protection;
- no encrypted backup format inside application, if offsite/storage encryption is provided operationally;
- one application worker and no horizontal scaling.

## 8. Review triggers

Threat model must be reviewed when adding:

- public registration or roles;
- Markdown/HTML content;
- server-side URL fetching;
- automatic file imports;
- background jobs;
- PostgreSQL/multiple instances;
- object storage/CDN;
- public API;
- external authentication;
- email/Telegram integrations;
- mandatory malware scanning.


## 9. Phase 19 release-candidate review

The trust boundaries and threat inventory were reviewed against the implemented
Docker/Nginx topology, browser E2E flow, backup/restore service and release
candidate runbooks. No new application trust boundary was introduced in Phase 19.

Residual environment-specific risks remain outside code-level evidence:

- production DNS, firewall, VPN/IP allowlist and TLS renewal are not accepted
  until Phase 20;
- offsite backup credentials and alert delivery belong to the deployment
  environment;
- a compromised host administrator can still alter containers, database, storage
  or backups;
- download-completion accounting remains approximate because the MVP records an
  authorized GET start;
- optional malware scanning does not prove a binary is trustworthy.

The go/no-go controls for these risks are documented in
`docs/production-acceptance.md` and `docs/release-checklist.md`.
