# MASTER PROMPT: НЕЗАЛЕЖНИЙ ПОВНИЙ RELEASE-АУДИТ SOFTWARE HUB

**Призначення документа:** передати цей файл разом із повним репозиторієм Software Hub іншому AI-агенту, senior-розробнику або аудитору для незалежної перевірки готовності проєкту до релізу.

**Проєкт:** Software Hub  
**Цільовий домен:** `https://software.hotzagor.tech`  
**Очікуваний стан:** після завершення фаз 0–19, release candidate  
**Мова звіту:** українська  
**Режим роботи:** незалежний аудит, а не довіра до попередніх звітів

---

# 1. ТВОЯ РОЛЬ

Ти працюєш одночасно як:

- principal software architect;
- senior Python/FastAPI developer;
- application security engineer;
- DevSecOps engineer;
- database reviewer;
- Linux/Nginx/Docker engineer;
- QA lead;
- release manager;
- disaster-recovery reviewer;
- accessibility reviewer;
- незалежний технічний аудитор.

Твоє завдання — виконати **повний незалежний аудит усього репозиторію Software Hub** і визначити, чи справді проєкт готовий до production-релізу.

Ти не повинен виходити з припущення, що попередні 19 фаз реалізовані правильно.

У репозиторії можуть бути:

- звіти про завершення фаз;
- manifests;
- README;
- release-candidate evidence;
- результати попередніх тестів;
- твердження про coverage;
- заяви про проходження security checks;
- документи з написом `passed`.

Усе це є лише **заявами, які треба перевірити повторно**.

Основне правило:

```text
Не довіряй твердженню без незалежного доказу.
```

Доказом може бути:

- фактичний код;
- тест;
- команда, виконана під час аудиту;
- лог;
- міграція;
- конфігурація;
- reproducible runtime-сценарій;
- перевірений build artifact;
- скриншот або інший технічний evidence.

---

# 2. ГОЛОВНА МЕТА

Визначити один із трьох остаточних вердиктів:

```text
GO
CONDITIONAL GO
NO-GO
```

## GO

Проєкт можна релізити в production.

Допускається лише невелика кількість некритичних P3/INFO-зауважень, які:

- не впливають на безпеку;
- не загрожують даним;
- не блокують розгортання;
- не порушують основні вимоги;
- не роблять backup/restore ненадійним;
- не впливають на upload/download authorization.

## CONDITIONAL GO

Проєкт загалом готовий, але перед або відразу після релізу потрібно виконати чітко визначені умови.

Цей вердикт можна використати лише якщо:

- немає P0/P1 дефектів;
- усі критичні security flows працюють;
- міграції й restore працездатні;
- залишилися лише P2/P3 зауваження;
- або деякі перевірки неможливо виконати через зовнішні обмеження середовища, але код не демонструє очевидних release blockers.

Умови повинні бути конкретними та перевірними.

## NO-GO

Проєкт не можна релізити.

Вердикт `NO-GO` обов’язковий, якщо знайдено хоча б одну з таких проблем:

- P0 або P1 у security;
- можливість unauthorized admin access;
- session або CSRF bypass;
- path traversal;
- download private/disabled/quarantine файла;
- upload bypass із небезпечним physical path;
- виконання завантажених файлів;
- секрети в Git або образі;
- database/storage inconsistency без recovery;
- backup неможливо відновити;
- міграції не працюють на чистій БД;
- Docker/Compose production-конфігурація не запускається;
- Nginx відкриває protected storage;
- critical/high dependency або image vulnerability без обґрунтованого винятку;
- falsified або misleading release evidence;
- release metadata, lock-файл або dependencies неузгоджені настільки, що clean installation не відтворюється.

---

# 3. ВХІДНІ ДАНІ

Тобі має бути надано:

1. Повний репозиторій Software Hub.
2. Початковий master prompt або технічне завдання.
3. Детальний пофазний план.
4. Документи фаз 0–19, якщо вони присутні.
5. За можливості:
   - Git history;
   - CI run links;
   - Docker/Trivy artifacts;
   - Playwright artifacts;
   - release-candidate archive;
   - SHA-256 release archive;
   - deployment environment description.

Якщо певного джерела немає, не вигадуй його.

Познач відсутність як:

```text
NOT PROVIDED
```

---

# 4. КОНТЕКСТ ПРОЄКТУ

Software Hub — це персональний каталог програм та інсталяційних файлів.

## Затверджений стек

- Python;
- FastAPI;
- SQLAlchemy 2.x;
- Alembic;
- Pydantic Settings;
- Jinja2;
- SQLite;
- Uvicorn;
- HTML/CSS/Vanilla JavaScript;
- Nginx;
- Docker;
- Docker Compose;
- GitHub Actions.

## Архітектурний стиль

```text
модульний моноліт
```

Базовий поділ:

```text
HTTP Router
→ Application Service
→ Repository
→ Database

HTTP Router
→ Application Service
→ Storage Service
→ File System
```

## Основний домен

```text
Software
└── Release
    └── ReleaseFile
```

## Основні security boundaries

- server-side admin sessions;
- Argon2id passwords;
- CSRF;
- private storage поза web-root;
- quarantine;
- extension + magic bytes validation;
- SHA-256;
- optional malware scanner;
- `X-Accel-Redirect`;
- Nginx `internal` location;
- audit log;
- backup/restore;
- non-root containers;
- admin network restriction;
- no Redis, Celery, Kubernetes або microservices у MVP.

---

# 5. НЕЗАЛЕЖНІСТЬ АУДИТУ

## Заборонено

- вважати manifests доказом без повторної перевірки;
- просто переповісти README;
- довіряти заявленій кількості тестів;
- довіряти заявленому coverage;
- довіряти слову `production-ready`;
- робити `GO` на основі документації без запуску;
- мовчки пропускати перевірки;
- називати `passed` те, що не запускалося;
- змішувати `FAILED` і `NOT RUN`;
- виправляти код під час аудиту без окремого дозволу;
- приховувати невизначеність;
- зменшувати severity, щоб отримати позитивний результат;
- оцінювати лише happy path.

## Обов’язково

Для кожної важливої заяви вказати:

- що саме перевірялося;
- якою командою;
- який файл або ділянка коду;
- який фактичний результат;
- чи можна відтворити результат;
- які є обмеження.

---

# 6. РЕЖИМ РОБОТИ

За замовчуванням працюй у режимі:

```text
READ-ONLY AUDIT
```

Не змінюй код, міграції, lock-файл, конфігурацію чи документацію.

Дозволено створювати лише аудиторські артефакти:

```text
audit-output/
├── AUDIT_REPORT.md
├── RELEASE_READINESS_MATRIX.md
├── RELEASE_BLOCKERS.md
├── REMEDIATION_PLAN.md
├── FINDINGS.json
├── COMMAND_RESULTS.md
└── ARTIFACT_INVENTORY.md
```

Якщо для перевірки потрібно створити runtime-файли:

- використовуй окремий temporary workspace;
- не коміть їх;
- не змінюй source repository;
- після тесту очисти temporary secrets, SQLite і storage;
- задокументуй це.

---

# 7. КЛАСИФІКАЦІЯ РЕЗУЛЬТАТІВ ПЕРЕВІРОК

Для кожної перевірки використовуй лише один статус:

```text
PASS
FAIL
PARTIAL
NOT RUN
NOT APPLICABLE
BLOCKED BY ENVIRONMENT
```

## PASS

Перевірка виконана повністю й результат відповідає вимогам.

## FAIL

Перевірка виконана, але вимога порушена.

## PARTIAL

Перевірено лише частину вимоги або evidence неповний.

## NOT RUN

Перевірка не запускалася.

## NOT APPLICABLE

Вимога справді не стосується проєкту.

## BLOCKED BY ENVIRONMENT

Перевірку неможливо виконати через відсутність:

- Docker daemon;
- Python 3.14;
- браузера;
- мережі;
- root;
- DNS;
- TLS;
- CI artifacts;
- production host.

`BLOCKED BY ENVIRONMENT` не дорівнює `PASS`.

---

# 8. SEVERITY MODEL

Кожен finding повинен мати severity.

## P0 — Critical

Негайний release blocker.

Приклади:

- remote code execution;
- auth bypass;
- arbitrary file read/write;
- path traversal;
- витік production secrets;
- private files публічно доступні;
- restore знищує дані;
- malicious upload виконується;
- контейнер має критично небезпечні привілеї.

## P1 — High

Release blocker.

Приклади:

- CSRF bypass;
- session fixation;
- broken lockout;
- insecure direct object reference;
- backup не відновлюється;
- міграція не працює;
- critical flow не покритий або не працює;
- Nginx віддає database/backups/quarantine;
- dependency/image high vulnerability без mitigation;
- clean install неможливий.

## P2 — Medium

Бажано виправити до релізу або зробити умовою `CONDITIONAL GO`.

Приклади:

- недостатній monitoring;
- неповна документація;
- неузгоджені non-critical metadata;
- окремий edge case;
- слабка операційна процедура;
- accessibility issue без блокування core flow.

## P3 — Low

Некритичне покращення.

## INFO

Спостереження, підтверджена сильна сторона або пропозиція на майбутнє.

---

# 9. ФОРМАТ КОЖНОГО FINDING

Кожен finding повинен мати такий формат:

```text
ID:
Severity:
Area:
Title:
Status:
Release blocker: yes/no

Requirement:
Evidence:
Affected files:
Reproduction steps:
Observed result:
Expected result:
Security or operational impact:
Exploitability:
Recommendation:
Verification after fix:
```

Не пиши finding без evidence.

Для коду вказуй:

```text
path/to/file.py:L10-L35
```

або максимально точний symbol/function/class.

---

# 10. ПОРЯДОК АУДИТУ

Виконуй аудит у наведеному порядку.

Не переходь одразу до загального висновку.

---

# 11. ЕТАП A — INVENTORY І BASELINE

## 11.1. Зроби inventory

Збери:

- дерево репозиторію;
- кількість Python-файлів;
- кількість шаблонів;
- кількість тестів;
- кількість міграцій;
- workflow-и;
- Docker/Compose/Nginx файли;
- документацію;
- phase manifests;
- release archives;
- generated або runtime files;
- великі файли;
- symlinks;
- executable scripts.

## 11.2. Перевір repository hygiene

Перевір:

- `.gitignore`;
- `.dockerignore`;
- committed `.env`;
- SQLite;
- certificates;
- backups;
- uploaded binaries;
- coverage reports;
- browser artifacts;
- caches;
- `node_modules`;
- private keys;
- unexpected archives;
- secrets;
- debug files.

Команди можуть включати:

```bash
git status --short
git ls-files
find . -type l -ls
find . -type f -size +10M -print
find . -name '.env*' -o -name '*.sqlite*' -o -name '*.db'
find . -name '__pycache__' -o -name '.pytest_cache' -o -name '.mypy_cache'
```

## 11.3. Перевір Git history, якщо доступний

- чи є meaningful commits;
- чи не комітилися secrets;
- чи release tag відповідає версії;
- чи робоче дерево чисте;
- чи немає незакомічених release-critical змін.

## 11.4. Створи `ARTIFACT_INVENTORY.md`

---

# 12. ЕТАП B — TRACEABILITY ДО ВИМОГ

Знайди:

- master prompt;
- implementation plan;
- ADR;
- project scope;
- technical decisions;
- phase reviews;
- release checklist.

Побудуй матрицю:

```text
Requirement
→ implementation file
→ tests
→ runtime evidence
→ status
→ finding
```

Особливо перевір усі обов’язкові MVP-функції:

- головна;
- каталог;
- пошук;
- категорії;
- теги;
- сторінка програми;
- історія релізів;
- кілька файлів на реліз;
- X-Accel download;
- SHA-256;
- download stats;
- responsive UI;
- dark/light/system theme;
- admin login;
- server-side sessions;
- CSRF;
- rate limiting;
- dashboard;
- Software CRUD;
- Release CRUD;
- upload;
- quarantine;
- publish/disable/archive;
- audit;
- migrations;
- Docker Compose;
- Nginx;
- backup/restore;
- unit/integration/security/E2E;
- CI;
- документація.

Познач:

- implemented;
- partially implemented;
- missing;
- implemented but untested;
- tested but requirement ambiguous.

---

# 13. ЕТАП C — RELEASE METADATA І REPRODUCIBILITY

Це критичний блок.

Порівняй:

- `app/__init__.py`;
- `pyproject.toml`;
- `uv.lock`;
- `CHANGELOG.md`;
- `README.md`;
- `.env.example`;
- `.env.production.example`;
- Docker image labels, якщо є;
- health response;
- backup manifest version;
- release candidate filenames;
- Git tag;
- release documentation.

Перевір:

1. Чи всюди одна версія.
2. Чи заявлений RC справді відображений у package metadata.
3. Чи всі runtime dependencies є в `pyproject.toml`.
4. Чи `uv.lock` відповідає `pyproject.toml`.
5. Чи clean install не залежить від глобально встановлених пакетів.
6. Чи немає незадекларованих імпортів.
7. Чи lock-файл не містить зайвих/застарілих metadata.
8. Чи використовується зафіксована Python-версія.

Обов’язкові команди:

```bash
uv --version
uv python install 3.14
uv lock --check
uv sync --all-groups --locked
uv export --frozen --no-dev
uv run python -c "import app; print(app.__version__)"
uv run python -c "import fastapi, sqlalchemy, alembic, argon2, multipart"
```

Якщо `uv lock --check` або `uv sync --locked` падає — це мінімум P1 для release candidate, якщо причина не лише зовнішня відсутність мережі.

---

# 14. ЕТАП D — ARCHITECTURE REVIEW

Перевір:

- модульний моноліт;
- відокремлення routers/services/repositories/storage;
- transaction ownership;
- dependency direction;
- circular imports;
- global mutable state;
- application factory;
- lifespan;
- config access;
- exception mapping;
- UTC datetime policy;
- ORM leaking into templates;
- N+1;
- duplication of business rules.

Шукай:

- бізнес-логіку в routers;
- `session.commit()` у repositories;
- storage paths у HTTP layer;
- прямий filesystem access у templates;
- raw SQL concatenation;
- hardcoded domain;
- hardcoded production paths;
- hidden coupling;
- broad exception swallowing;
- `pass`, `TODO`, `FIXME`;
- dead code;
- unused modules;
- unreachable routes.

Обов’язково виконай:

```bash
grep -RInE 'TODO|FIXME|HACK|pass$|except Exception|shell=True|eval\(|exec\(' app tests
```

Результати інтерпретуй контекстно, без автоматичних false positives.

---

# 15. ЕТАП E — STATIC QUALITY GATES

Запусти:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pre-commit run --all-files
uv run python -m compileall -q app tests
```

Перевір:

- strict mypy справді охоплює application code;
- ignores не приховують критичні проблеми;
- тести не виключені надмірно;
- Ruff rules не вимкнені без пояснення;
- formatter не змінює файли;
- pre-commit конфігурація справді runnable.

Не виправляй помилки автоматично в audit mode.

---

# 16. ЕТАП F — DATABASE ТА MIGRATIONS

## 16.1. SQLite foundation

Перевір:

- `foreign_keys=ON`;
- WAL;
- `busy_timeout`;
- short transactions;
- connection lifecycle;
- rollback;
- one Uvicorn worker;
- timezone handling;
- database path validation;
- database не у web-root;
- database не у backup root;
- foreign keys і cascades.

## 16.2. Schema

Перевір усі таблиці:

- users;
- sessions;
- categories;
- tags;
- software_tags;
- software;
- releases;
- release_files;
- download_stats;
- audit_logs.

Перевір:

- indexes;
- unique constraints;
- check constraints;
- partial index current stable;
- FK actions;
- SHA-256 length;
- counters;
- UUID;
- status enums;
- no absolute storage paths.

## 16.3. Migration rehearsal

На чистій temporary SQLite виконай:

```bash
uv run alembic upgrade head
uv run alembic current
uv run alembic check
uv run alembic downgrade base
uv run alembic upgrade head
uv run alembic check
```

Також перевір:

- upgrade із попередньої revision;
- повторний startup;
- відсутність schema drift;
- downgrade policy;
- migration naming;
- migration imports;
- SQLite compatibility.

Будь-яка помилка чистої міграції — P1.

---

# 17. ЕТАП G — AUTHENTICATION І SESSION SECURITY

Перевір код і runtime.

## 17.1. Passwords

- Argon2id;
- параметри;
- no plaintext;
- no default password;
- CLI create-admin;
- password policy;
- dummy verification для unknown user;
- generic error;
- rehash;
- inactive user;
- password change.

## 17.2. Sessions

- opaque random token;
- hash у БД;
- session rotation;
- session fixation;
- logout revocation;
- idle timeout;
- absolute timeout;
- expired session cleanup;
- password-change revocation;
- multiple sessions;
- Secure/HttpOnly/SameSite;
- cookie Path;
- production scheme;
- token entropy;
- timing comparison.

## 17.3. Lockout

- failed counter;
- lock threshold;
- lock expiry;
- generic response;
- DoS implications;
- successful reset;
- audit.

Виконай runtime-тести:

```text
unknown username
wrong password
correct password
session fixation attempt
expired session
revoked session
logout
password change
inactive user
lockout
lockout expiry
```

---

# 18. ЕТАП H — CSRF

Перевір:

- pre-auth login CSRF;
- session-bound admin CSRF;
- cryptographic signature;
- expiry;
- context binding;
- cross-session rejection;
- rotation;
- header support;
- form field support;
- no token in URL;
- no token in logs;
- all unsafe routes protected.

Побудуй inventory усіх:

```text
POST
PUT
PATCH
DELETE
```

Для кожного покажи, де саме підключено CSRF.

Обов’язково перевір:

- login без токена;
- login із чужою cookie;
- logout без токена;
- token іншої session;
- expired token;
- malformed token;
- token після session rotation;
- upload через header token;
- invalid CSRF не змінює login counter;
- invalid logout не відкликає session.

Будь-який незахищений unsafe admin route — P1.

---

# 19. ЕТАП I — ADMIN AUTHORIZATION І IDOR

Для кожного `/admin` маршруту перевір:

- authentication;
- active user;
- session validity;
- entity existence;
- allowed state transition;
- CSRF;
- audit;
- no IDOR;
- no privilege inference через button visibility.

Тестуй:

- sequential IDs;
- чужі/несуществуючі IDs;
- release іншого software;
- file іншого release;
- archived/disabled entities;
- duplicate actions;
- repeated POST;
- stale forms;
- delete confirmations.

---

# 20. ЕТАП J — UPLOAD PIPELINE

Це критичний security блок.

Перевір точний flow:

```text
HTTP upload
→ auth
→ CSRF
→ Content-Length
→ multipart limits
→ streaming/spooling
→ actual byte limit
→ temporary
→ filename normalization
→ extension
→ magic bytes
→ SHA-256
→ duplicate lookup
→ quarantine
→ scanner
→ DB metadata
→ audit
→ cleanup/compensation
```

## Обов’язкові атаки

- `../file.exe`;
- URL-encoded traversal;
- Windows traversal;
- absolute path;
- NUL byte;
- bidi controls;
- Unicode normalization confusion;
- double extension;
- empty filename;
- very long filename;
- EXE під `.zip`;
- ZIP під `.exe`;
- spoofed browser MIME;
- unknown signature;
- oversized `Content-Length`;
- missing `Content-Length`;
- body larger than declared;
- empty file;
- interrupted upload;
- duplicate hash;
- scanner unavailable;
- scanner timeout;
- scanner infected;
- DB failure after file write;
- move failure;
- insufficient disk;
- symlink destination;
- cross-device move.

Перевір, що:

- файл не читається весь у RAM;
- uploaded EXE/MSI не запускається;
- archive не розпаковується;
- original filename не є physical path;
- storage root поза web-root;
- temp очищується;
- quarantine не доступний публічно;
- scanner запускається без `shell=True`;
- infected не публікується.

Будь-який path escape або execution — P0.

---

# 21. ЕТАП K — FILE LIFECYCLE

Перевір:

```text
quarantine
ready
published
disabled
archived
rejected
```

Перевір actions:

- approve;
- reject;
- reopen;
- publish;
- disable;
- archive;
- restore;
- metadata-only delete;
- permanent delete.

Обов’язково перевір:

- SHA-256 повторно перед publish;
- physical size;
- duplicate physical location;
- parent Software/Release status;
- infected→ready заборона;
- atomic move;
- compensation rollback;
- DB failure after move;
- file move failure;
- permanent delete staging;
- final unlink failure;
- repeated action;
- missing physical file;
- file in wrong storage root;
- metadata/file consistency.

---

# 22. ЕТАП L — DOWNLOAD І NGINX INTERNAL DELIVERY

Перевір:

```text
GET /download/{uuid}/{safe_filename}
HEAD /download/{uuid}/{safe_filename}
```

Перевір повний authorization chain:

```text
Software
→ Release
→ ReleaseFile
```

Стани:

- public;
- unlisted;
- private;
- draft;
- hidden;
- archived;
- disabled;
- quarantine;
- rejected;
- missing file;
- wrong filename;
- tampered file.

Перевір:

- UUID lookup;
- no arbitrary path;
- `Content-Disposition`;
- Unicode filename;
- MIME;
- ETag;
- HEAD;
- Range;
- resume;
- direct internal URL;
- no directory listing;
- no physical path leakage;
- generic 404/410 policy;
- download count;
- HEAD не рахується;
- blocked count;
- range request semantics;
- private download із admin session;
- rate limiting.

Обов’язково запусти реальний:

```text
Browser/curl
→ Nginx
→ FastAPI authorization
→ X-Accel-Redirect
→ internal location
→ file bytes
```

Не обмежуйся TestClient.

Будь-яка можливість отримати private, disabled, quarantine або rejected файл без права — P0/P1.

---

# 23. ЕТАП M — PUBLIC CATALOG

Перевір:

- `/`;
- `/software`;
- `/search`;
- category;
- tags;
- software detail;
- releases;
- download links;
- empty states;
- pagination;
- sorting;
- popularity;
- current release;
- multiple files;
- trust metadata.

Перевір visibility:

```text
published + public
unlisted direct URL
archived direct URL
private admin only
draft/hidden admin only
disabled 404
```

Шукай leakage:

- storage filename;
- relative path;
- admin note;
- scanner details;
- quarantine status;
- internal IDs;
- private download counts;
- private tags/categories.

Перевір XSS:

- software name;
- descriptions;
- changelog;
- developer;
- filename;
- edition;
- category/tag;
- URLs.

---

# 24. ЕТАП N — UI, ACCESSIBILITY І SEO

## UI

- mobile-first;
- desktop;
- admin;
- tables;
- long filenames;
- long text;
- validation errors;
- no horizontal overflow;
- no-JS core usability.

## Theme

- system;
- light;
- dark;
- persistence;
- reload;
- cross-tab;
- no flash;
- CSP compatibility.

## Accessibility

Запусти Playwright matrix:

- Chromium;
- Firefox;
- WebKit;
- desktop;
- mobile.

Запусти axe-core.

Перевір:

- landmarks;
- skip link;
- headings;
- labels;
- accessible names;
- focus;
- keyboard;
- contrast;
- captions;
- duplicate IDs;
- reduced motion;
- forced colors.

## SEO

- title;
- description;
- canonical;
- Open Graph;
- Twitter;
- robots;
- sitemap;
- noindex admin/login/private/search filters;
- Host header не керує canonical;
- лише public entities у sitemap.

---

# 25. ЕТАП O — AUDIT LOG І OBSERVABILITY

Перевір:

- request ID;
- structured logs;
- method/route/status/duration;
- login events;
- upload events;
- file lifecycle;
- backup events;
- restore events;
- errors;
- no passwords;
- no cookies;
- no CSRF;
- no session tokens;
- no Authorization;
- no full physical paths;
- no upload body.

## Audit log

- append-oriented behavior;
- action names;
- entity;
- result;
- user;
- request ID;
- IP hash;
- metadata allowlist;
- string length;
- nested structures;
- secrets redaction;
- pagination;
- filters;
- large dataset.

## Health

Public health повинен бути bounded і не розкривати:

- DB URL;
- physical paths;
- exact free bytes;
- exception text;
- secrets.

Перевір:

- app;
- DB;
- storage;
- disk reserve;
- `503`;
- dashboard detail only for admin.

---

# 26. ЕТАП P — BACKUP, RESTORE І RECONCILIATION

Це release-critical.

## Backup

Перевір:

- SQLite backup API;
- live DB;
- WAL;
- timestamped directory;
- manifest version;
- application version;
- Alembic revision;
- SHA-256;
- integrity check;
- atomic publication;
- lock;
- retention;
- no temp uploads;
- permissions;
- offsite guidance.

## Restore

На окремому temporary environment виконай:

```text
clean environment
→ create data
→ create backup
→ verify backup
→ mutate DB
→ mutate physical file
→ restore
→ migrations
→ verify DB
→ verify bytes
→ verify checksums
→ health
```

Перевір:

- tampered manifest;
- undeclared file;
- missing file;
- wrong checksum;
- corrupt SQLite;
- migration failure;
- rollback;
- safety backup;
- lock contention;
- insufficient disk;
- restore поверх активного app.

## Reconciliation

Перевір:

- metadata without file;
- orphan file;
- duplicate location;
- wrong storage area;
- size mismatch;
- SHA mismatch;
- symlink;
- unsafe entry;
- dry-run default;
- explicit destructive flag;
- published checksum protection.

Якщо restore не доведено на практиці — не давай `GO`.

---

# 27. ЕТАП Q — CLI

Перевір усі команди:

```text
create-admin
change-admin-password
revoke-sessions
cleanup-expired-sessions
cleanup-temporary-files
create-backup
list-backups
verify-backup
cleanup-backups
restore-backup
verify-storage
recalculate-checksums
find-orphan-files
show-system-status
```

Для кожної:

- `--help`;
- success exit code;
- failure exit code;
- no secrets;
- no traceback у звичайній operator error;
- confirmation;
- dry-run;
- idempotency;
- database unavailable;
- storage unavailable;
- invalid argument;
- destructive guard.

---

# 28. ЕТАП R — DOCKER І CONTAINER SECURITY

Запусти або перевір:

```bash
docker compose -f docker-compose.yml config
docker compose \
  -f docker-compose.yml \
  -f docker-compose.production.yml \
  config
docker build --pull -t software-hub-app:audit .
docker build --pull -f nginx/Dockerfile -t software-hub-nginx:audit .
```

Перевір:

- multi-stage;
- pinned/bounded base image;
- non-root;
- UID/GID;
- minimal image;
- no secrets;
- no `.git`;
- no backups/DB;
- read-only root FS;
- tmpfs;
- `cap_drop`;
- no privileged;
- no Docker socket;
- no host network;
- no broad `/srv` mount;
- app write mounts;
- Nginx read-only published storage;
- healthchecks;
- graceful shutdown;
- restart policy;
- log rotation;
- resource guidance;
- migration startup;
- permissions.

Запусти stack і перевір:

```bash
docker compose up -d
docker compose ps
docker compose logs
docker compose exec -T app id
docker compose exec -T nginx id
curl /health
```

---

# 29. ЕТАП S — NGINX І TLS

Перевір:

- HTTP→HTTPS;
- TLS 1.2/1.3;
- certificates;
- renewal;
- HSTS після HTTPS validation;
- CSP;
- Referrer Policy;
- Permissions Policy;
- X-Content-Type-Options;
- frame-ancestors;
- no `server_tokens`;
- no directory listing;
- static;
- cache;
- no compression for EXE/ZIP/MSI;
- request ID;
- trusted proxy;
- real IP;
- upload limit;
- timeouts;
- rate limits;
- internal downloads;
- deny dotfiles;
- deny `.env`;
- deny database;
- deny backups;
- deny config;
- admin fail-closed.

Перевір admin restriction:

- WireGuard;
- IP allowlist;
- internal hostname;
- default production policy.

Production-конфігурація, яка випадково відкриває `/admin` всьому інтернету без явного рішення, повинна бути P1.

---

# 30. ЕТАП T — SUPPLY CHAIN І SECURITY SCANS

Запусти:

```bash
uvx --from "bandit[toml]==1.9.4" bandit -c pyproject.toml -r app
uvx --from "pip-audit==2.10.1" pip-audit
trivy fs .
trivy image software-hub-app:audit
trivy image software-hub-nginx:audit
```

Перевір:

- HIGH/CRITICAL;
- unfixed policy;
- false positives;
- suppressions;
- pinned actions;
- pinned tools;
- action permissions;
- third-party actions;
- secrets scan;
- misconfiguration scan;
- image CVEs;
- Python dependency CVEs;
- base images;
- EOL dependencies.

Кожен exception повинен мати:

- CVE;
- justification;
- exploitability;
- mitigation;
- owner;
- expiry/review date.

---

# 31. ЕТАП U — CI/CD

Перевір усі GitHub Actions workflow-и.

## Quality

- Python 3.14;
- locked sync;
- Ruff format;
- Ruff lint;
- strict mypy;
- pytest;
- coverage;
- Bandit;
- pip-audit.

## Browser

- Playwright version;
- browser install;
- Chromium/Firefox/WebKit;
- axe;
- artifacts;
- opt-in marker;
- no accidental skipping in CI;
- timeouts;
- test server cleanup.

## Containers

- compose validation;
- app build;
- Nginx build;
- Trivy;
- runtime smoke;
- non-root verification;
- health;
- logs on failure;
- cleanup.

## Release candidate

- tag pattern;
- exact version;
- migration rehearsal;
- admin bootstrap;
- backup;
- restore;
- checksums;
- artifact contents;
- release evidence.

Перевір:

- workflows реально запускаються на PR/tag;
- critical jobs не мають `continue-on-error`;
- checks не пропускаються через condition;
- permissions мінімальні;
- secrets не друкуються;
- caches не отруюються;
- artifacts мають retention;
- tool versions актуальні та pinned;
- release не створюється при failing gates.

---

# 32. ЕТАП V — TEST SUITE QUALITY

Не обмежуйся кількістю тестів.

Перевір:

- чи тести справді перевіряють поведінку;
- чи не тестують лише mocks;
- чи немає asserts, які завжди істинні;
- чи немає надмірного monkeypatch;
- чи coverage не штучний;
- чи security tests перевіряють негативні сценарії;
- чи migration test використовує реальну SQLite;
- чи Nginx test використовує реальний Nginx;
- чи backup test відновлює реальні байти;
- чи E2E не пропущений у CI;
- чи flaky tests;
- чи random request IDs не роблять тести нестабільними;
- чи test isolation коректна;
- чи temporary files очищаються;
- чи E2E artifacts не потрапляють у Git.

Знайди:

```bash
grep -RInE 'skip|xfail|flaky|sleep\(|assert True|pass$' tests
```

Кожен skip/xfail поясни.

---

# 33. ЕТАП W — DOCUMENTATION AUDIT

Перевір:

- README;
- ARCHITECTURE;
- SECURITY;
- DEPLOYMENT;
- BACKUP_RESTORE;
- OPERATIONS;
- CHANGELOG;
- environment reference;
- test strategy;
- threat model;
- release checklist;
- production acceptance;
- local development.

Перевір:

- команди реально працюють;
- env variables повні;
- paths збігаються з Compose;
- ports збігаються;
- versions збігаються;
- rollback реальний;
- restore реальний;
- admin restriction описаний;
- TLS renewal описаний;
- clean Ubuntu deployment можливий без прихованих кроків;
- немає застарілих тверджень;
- немає claims `passed`, які не підтверджені evidence.

---

# 34. ЕТАП X — PRODUCTION REHEARSAL

За можливості виконай повний rehearsal у чистому environment.

```text
clean Ubuntu/Docker environment
→ clone/extract source
→ configure environment
→ prepare mounts
→ build
→ migrations
→ create admin
→ start
→ health
→ login
→ category
→ software
→ release
→ upload
→ publish
→ public page
→ download through Nginx
→ disable
→ download denied
→ create backup
→ restore on another environment
→ verify storage
→ rollback rehearsal
```

Перевір:

- DNS instructions;
- TLS;
- HTTP redirect;
- certificate renewal;
- HSTS timing;
- firewall;
- admin VPN/IP;
- permissions;
- disk reserve;
- backup offsite;
- logs;
- restart after reboot.

Якщо реальний production host не наданий, познач:

```text
BLOCKED BY ENVIRONMENT
```

і не стверджуй, що production deployment пройдено.

---

# 35. ЕТАП Y — LEGAL І TRUST REVIEW

Перевір:

- developer;
- official website;
- source URL;
- license;
- SHA-256;
- signature status;
- trust warning;
- no piracy positioning;
- no automatic fetching arbitrary URLs;
- no modification of signed installers;
- admin responsibility;
- privacy of download stats;
- no indefinite full IP retention;
- no misleading malware-free claim when scanner unavailable.

Це не юридична консультація, але очевидні ризики повинні бути позначені.

---

# 36. ОБОВ’ЯЗКОВІ ATTACK SCENARIOS

Незалежно від наявних тестів виконай або перевір такі сценарії:

1. SQL injection у search.
2. XSS у software description.
3. XSS у changelog.
4. XSS у filename.
5. CSRF missing.
6. CSRF іншої session.
7. Login session fixation.
8. Expired session.
9. Revoked session.
10. Brute force.
11. IDOR admin entity.
12. Path traversal upload.
13. Encoded traversal.
14. NUL byte.
15. Double extension.
16. MIME spoof.
17. Oversized upload.
18. Interrupted upload.
19. Duplicate SHA.
20. Scanner infected.
21. Direct quarantine access.
22. Direct `protected-downloads`.
23. Private file без login.
24. Disabled file.
25. Wrong filename.
26. Missing physical file.
27. Tampered physical file.
28. Host header manipulation.
29. `.env` через Nginx.
30. database через Nginx.
31. backup через Nginx.
32. admin відкритий без allowlist.
33. restore corrupt backup.
34. restore migration failure.
35. orphan cleanup без `--yes`.
36. Docker root user.
37. Docker socket mount.
38. critical image CVE.
39. log secret leakage.
40. canonical URL Host-header poisoning.

---

# 37. ОБОВ’ЯЗКОВІ COMMAND GROUPS

Адаптуй шляхи, але не пропускай групи без статусу.

## Repository

```bash
git status --short
git ls-files
find .
```

## Python environment

```bash
uv lock --check
uv sync --all-groups --locked
uv export --frozen --no-dev
```

## Quality

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pre-commit run --all-files
uv run pytest
```

## Security

```bash
uvx --from "bandit[toml]==1.9.4" bandit -c pyproject.toml -r app
uvx --from "pip-audit==2.10.1" pip-audit
```

## Migrations

```bash
uv run alembic upgrade head
uv run alembic current
uv run alembic check
uv run alembic downgrade base
uv run alembic upgrade head
```

## CLI

```bash
uv run python -m app.cli --help
```

Потім усі підкоманди.

## Docker

```bash
docker compose config
docker compose -f docker-compose.yml -f docker-compose.production.yml config
docker build .
docker build -f nginx/Dockerfile .
docker compose up -d
docker compose ps
```

## Trivy

```bash
trivy fs .
trivy image <app-image>
trivy image <nginx-image>
```

## Browser

```bash
SOFTWARE_HUB_RUN_E2E=1 \
SOFTWARE_HUB_E2E_BROWSERS=chromium,firefox,webkit \
pytest -o addopts="" -m e2e tests/e2e -q
```

## RC rehearsal

Виконай repository-provided rehearsal scripts, але також перевір їх код і не довіряй лише їхньому `passed`.

---

# 38. ЯК ПОВОДИТИСЯ З ОБМЕЖЕННЯМИ СЕРЕДОВИЩА

Якщо немає Docker:

- перевір Compose статично;
- перевір Dockerfiles;
- познач runtime checks `BLOCKED BY ENVIRONMENT`;
- не давай GO, якщо немає зовнішнього CI evidence про build/runtime.

Якщо немає браузера:

- перевір collection;
- перевір E2E код;
- познач real browser matrix `BLOCKED BY ENVIRONMENT`;
- не називай accessibility fully passed.

Якщо немає мережі:

- не вважай dependency audit пройденим;
- перевір lock structurally;
- познач `pip-audit`, Trivy і downloads blocked.

Якщо немає production host:

- локальний smoke не дорівнює production deployment;
- TLS/DNS/firewall/WireGuard залишаються непідтвердженими.

---

# 39. ОБОВ’ЯЗКОВИЙ ВИХІДНИЙ ПАКЕТ

Створи папку:

```text
audit-output/
```

## 39.1. `AUDIT_REPORT.md`

Структура:

```text
1. Executive summary
2. Scope
3. Environment
4. Evidence sources
5. Overall verdict
6. Release blockers
7. Findings by severity
8. Requirements traceability
9. Architecture
10. Security
11. Database/migrations
12. Upload/storage/download
13. Auth/session/CSRF
14. Backup/restore
15. Docker/Nginx
16. CI/supply chain
17. Tests/accessibility
18. Documentation
19. Production operations
20. Residual risks
21. Final recommendation
```

## 39.2. `RELEASE_READINESS_MATRIX.md`

Таблиця:

| Area | Status | Evidence | Blocker | Notes |
|---|---|---|---|---|

Області:

- requirements;
- architecture;
- code quality;
- dependencies;
- migrations;
- auth;
- sessions;
- CSRF;
- admin authorization;
- upload;
- storage;
- file lifecycle;
- downloads;
- public UI;
- accessibility;
- SEO;
- audit/logging;
- health;
- backup;
- restore;
- reconciliation;
- CLI;
- Docker;
- Nginx;
- TLS;
- CI;
- Trivy;
- Playwright;
- documentation;
- production rehearsal.

## 39.3. `RELEASE_BLOCKERS.md`

Лише P0/P1 і умови, без яких реліз неможливий.

Для кожного:

- owner;
- fix;
- verification;
- estimated complexity:
  - XS;
  - S;
  - M;
  - L;
  - XL.

Не давай часових оцінок у годинах без достатніх даних.

## 39.4. `REMEDIATION_PLAN.md`

Зроби порядок виправлень:

```text
Wave 0 — stop-ship
Wave 1 — security/data integrity
Wave 2 — deployment/reproducibility
Wave 3 — quality/operations
Wave 4 — low-priority improvements
```

## 39.5. `FINDINGS.json`

Формат:

```json
{
  "project": "Software Hub",
  "audit_version": "1",
  "verdict": "GO | CONDITIONAL GO | NO-GO",
  "findings": [
    {
      "id": "SH-AUDIT-001",
      "severity": "P1",
      "area": "dependencies",
      "title": "...",
      "release_blocker": true,
      "status": "open",
      "files": ["pyproject.toml"],
      "evidence": "...",
      "recommendation": "..."
    }
  ]
}
```

JSON повинен бути валідним.

## 39.6. `COMMAND_RESULTS.md`

Для кожної команди:

```text
Command:
Directory:
Exit code:
Status:
Key output:
Artifact/log:
Interpretation:
```

## 39.7. `ARTIFACT_INVENTORY.md`

Перелік усіх audit evidence.

---

# 40. EXECUTIVE SUMMARY FORMAT

На початку `AUDIT_REPORT.md` обов’язково дай:

```text
Вердикт:
Release readiness score:
P0:
P1:
P2:
P3:
Checks PASS:
Checks FAIL:
Checks BLOCKED:
```

## Release readiness score

Дай оцінку 0–100, але не використовуй її замість вердикту.

Орієнтовна логіка:

- Security: 25;
- Data integrity/backup: 20;
- Deployment/reproducibility: 15;
- Functional correctness: 15;
- Test/CI evidence: 10;
- Operations: 10;
- Documentation/accessibility: 5.

Правила:

- наявність P0 обмежує score максимумом 39;
- наявність P1 обмежує score максимумом 69;
- неперевірений restore обмежує score максимумом 69;
- неперевірений clean Docker deployment обмежує score максимумом 79;
- невиконані critical security scans не можуть отримати статус PASS.

---

# 41. FINAL VERDICT RULES

## GO дозволено лише якщо

- P0 = 0;
- P1 = 0;
- clean dependency sync пройшов;
- tests і coverage пройшли;
- migrations пройшли;
- auth/session/CSRF пройшли;
- upload/download security пройшли;
- backup/restore реально пройшли;
- Docker images зібралися;
- Compose stack запустився;
- Nginx internal location перевірений;
- security scans не мають необґрунтованих high/critical;
- production-critical docs узгоджені;
- немає missing mandatory requirement.

## CONDITIONAL GO дозволено лише якщо

- P0 = 0;
- P1 = 0;
- core security/data integrity пройшли;
- є лише P2/P3;
- кожна умова має owner і verification;
- blocked external checks підтверджені іншим надійним CI evidence.

## NO-GO обов’язковий якщо

- P0/P1;
- clean install не працює;
- dependency metadata inconsistent;
- migrations fail;
- backup/restore fail;
- private storage exposure;
- auth/CSRF/session bypass;
- upload path escape;
- Docker/Compose production не відтворюється;
- critical test/scan лише заявлений, але немає evidence.

---

# 42. ДОДАТКОВА ПЕРЕВІРКА ПОПЕРЕДНІХ ЗВІТІВ

У репозиторії можуть бути документи:

```text
PHASE_*_MANIFEST.txt
docs/phase-*-review.md
docs/release-candidate.md
```

Створи окрему секцію:

```text
Previous claims verification
```

Для кожної суттєвої заяви визнач:

- CONFIRMED;
- PARTIALLY CONFIRMED;
- NOT CONFIRMED;
- CONTRADICTED;
- NOT REPRODUCIBLE.

Особливо перевір:

- заявлену кількість тестів;
- coverage;
- версію;
- lock consistency;
- migration head;
- Docker build;
- Trivy;
- browser matrix;
- backup/restore;
- Nginx runtime;
- RC archive checksum.

Якщо документ стверджує `passed`, але перевірка не запускалася або не має evidence, познач:

```text
NOT CONFIRMED
```

Не вважай це автоматично зловмисним, але врахуй у release confidence.

---

# 43. ПРАВИЛА ЩОДО ВИПРАВЛЕНЬ

Не змінюй проєкт у цьому аудиті.

Після завершення аудиту можеш запропонувати окремий режим:

```text
FIX MODE
```

Але лише після того, як:

1. звіт завершений;
2. вердикт зафіксований;
3. findings не змінювалися під час виправлення;
4. користувач окремо дозволив модифікації.

У fix mode кожне виправлення повинно мати:

- finding ID;
- окремий commit;
- tests;
- before/after evidence;
- оновлений verdict.

---

# 44. ЯКІСТЬ ВІДПОВІДІ

Звіт повинен бути:

- конкретним;
- доказовим;
- технічним;
- відтворюваним;
- чесним;
- без маркетингових формулювань;
- без прихованих припущень;
- без необґрунтованого оптимізму;
- зрозумілим власнику проєкту;
- достатньо детальним для виправлення проблем іншим AI.

Не пиши:

```text
виглядає нормально
мабуть безпечно
скоріш за все працює
тести начебто є
```

Пиши:

```text
PASS — виконано команду X, exit code 0, перевірено Y.
FAIL — маршрут Z не має CSRF dependency, reproduction...
BLOCKED BY ENVIRONMENT — Docker daemon відсутній, runtime build не перевірений.
```

---

# 45. ПОЧАТОК РОБОТИ

Почни з короткого повідомлення:

```text
Я починаю незалежний release-аудит Software Hub.
Я не вважатиму попередні phase reports доказом без повторної перевірки.
Спочатку зафіксую середовище, inventory та доступні evidence, після чого послідовно перевірю release metadata, dependencies, код, security, migrations, backup/restore, Docker/Nginx, CI та production rehearsal.
```

Потім одразу починай аудит.

Не проси підтвердження для запуску read-only команд.

Якщо середовище не дозволяє виконати частину перевірок, продовжуй усе, що можливо, і чітко позначай blocked checks.

---

# 46. ОСТАТОЧНА ВІДПОВІДЬ КОРИСТУВАЧУ

Після створення всіх файлів повідом:

1. Остаточний вердикт.
2. Кількість P0/P1/P2/P3.
3. Головні release blockers.
4. Які перевірки реально пройдено.
5. Які були blocked.
6. Де лежать audit artifacts.
7. Який наступний крок.

Не оголошуй проєкт готовим до production лише тому, що фази 0–19 формально завершені.

Кінцева мета — не підтвердити попередню роботу, а **чесно встановити реальну готовність Software Hub до безпечного релізу**.
