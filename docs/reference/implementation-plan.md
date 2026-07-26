# SOFTWARE HUB — ДЕТАЛЬНИЙ ПОФАЗНИЙ ПЛАН РЕАЛІЗАЦІЇ

**Версія документа:** 1.0
**Дата:** 23 липня 2026 року
**Цільовий домен:** `https://software.hotzagor.tech`
**Формат реалізації:** модульний моноліт, production-ready MVP
**Стек:** FastAPI, SQLAlchemy 2.x, Alembic, Pydantic, Jinja2, SQLite, Nginx, Docker Compose

---

# 1. РЕЗЮМЕ РОЗУМІННЯ ПРОЄКТУ

Software Hub — це персональний каталог програм та інсталяційних файлів, який має дві основні частини:

1. **Публічний сайт**
   - каталог програм;
   - пошук, категорії й теги;
   - сторінка програми;
   - історія релізів;
   - вибір файла за платформою, архітектурою та типом пакета;
   - пряме завантаження файла через Nginx;
   - відображення SHA-256, джерела, ліцензії та іншої trust-інформації.

2. **Захищена адміністративна панель**
   - авторизація через server-side session;
   - CRUD програм, релізів, файлів, категорій і тегів;
   - безпечний streaming upload;
   - quarantine та ручна публікація;
   - аудит адміністративних дій;
   - статистика завантажень;
   - резервне копіювання;
   - діагностика сховища та системи.

Головні архітектурні принципи:

```text
простота
→ безпека
→ надійність
→ підтримуваність
→ розширюваність
```

Проєкт не повинен перетворюватися на мікросервісну систему. Для MVP достатньо одного FastAPI-застосунку, SQLite, Nginx і файлового сховища поза контейнером.

---

# 2. ОСТАТОЧНА АРХІТЕКТУРНА СХЕМА

## 2.1. Логічна схема

```text
Browser
  │
  ▼
Nginx
  ├── TLS termination
  ├── HTTP → HTTPS
  ├── static files
  ├── rate limiting
  ├── security headers
  ├── internal protected downloads
  └── reverse proxy
        │
        ▼
FastAPI application
  ├── Public routers
  ├── Authentication routers
  ├── Admin routers
  ├── Health routers
  ├── Middleware
  ├── Application services
  ├── Repositories
  ├── Storage services
  ├── Session/CSRF/Auth services
  ├── Audit and logging
  ├── Backup and reconciliation
  └── CLI commands
        │
        ├───────────────┐
        ▼               ▼
SQLite database     File system
                    ├── software
                    ├── icons
                    ├── temporary
                    ├── quarantine
                    ├── backups
                    └── logs
```

## 2.2. Основний потік HTTP-запиту

```text
Request
→ Nginx
→ trusted proxy headers
→ request ID middleware
→ host validation
→ session middleware
→ CSRF/auth checks
→ router
→ application service
→ repository/storage service
→ template or redirect response
```

## 2.3. Потік upload

```text
Admin form
→ authentication
→ CSRF
→ size pre-check
→ streaming у temporary
→ actual size check
→ filename normalization
→ extension validation
→ magic bytes detection
→ SHA-256
→ duplicate lookup
→ scanner interface
→ move to quarantine
→ short DB transaction
→ admin review
→ publish action
→ atomic move to permanent storage
→ metadata update
→ audit log
```

## 2.4. Потік download

```text
GET /download/{uuid}/{filename}
→ lookup by public UUID
→ validate Software status
→ validate Release status
→ validate ReleaseFile status
→ validate visibility
→ verify physical file
→ register authorized download start
→ X-Accel-Redirect
→ Nginx serves file
```

## 2.5. Потік авторизації

```text
GET login form
→ CSRF token
→ POST credentials
→ generic error on failure
→ failed counter / lockout
→ Argon2id verification
→ revoke/rotate old session where needed
→ create server-side session
→ set secure session cookie
→ redirect to admin dashboard
```

---

# 3. ОСТАТОЧНА СТРУКТУРА ПРОЄКТУ

```text
software-hub/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── cli.py
│   ├── core/
│   │   ├── config.py
│   │   ├── constants.py
│   │   ├── enums.py
│   │   ├── security.py
│   │   ├── csrf.py
│   │   ├── exceptions.py
│   │   ├── error_handlers.py
│   │   ├── logging.py
│   │   ├── middleware.py
│   │   ├── request_context.py
│   │   └── time.py
│   ├── database/
│   │   ├── base.py
│   │   ├── session.py
│   │   ├── pragmas.py
│   │   ├── types.py
│   │   └── migrations_helpers.py
│   ├── models/
│   │   ├── user.py
│   │   ├── session.py
│   │   ├── category.py
│   │   ├── tag.py
│   │   ├── software.py
│   │   ├── release.py
│   │   ├── release_file.py
│   │   ├── download_stat.py
│   │   ├── audit_log.py
│   │   └── associations.py
│   ├── schemas/
│   │   ├── auth.py
│   │   ├── category.py
│   │   ├── tag.py
│   │   ├── software.py
│   │   ├── release.py
│   │   ├── release_file.py
│   │   ├── pagination.py
│   │   └── common.py
│   ├── repositories/
│   │   ├── base.py
│   │   ├── user_repository.py
│   │   ├── session_repository.py
│   │   ├── category_repository.py
│   │   ├── tag_repository.py
│   │   ├── software_repository.py
│   │   ├── release_repository.py
│   │   ├── release_file_repository.py
│   │   ├── download_stat_repository.py
│   │   └── audit_repository.py
│   ├── services/
│   │   ├── auth_service.py
│   │   ├── session_service.py
│   │   ├── category_service.py
│   │   ├── tag_service.py
│   │   ├── software_service.py
│   │   ├── release_service.py
│   │   ├── file_service.py
│   │   ├── download_service.py
│   │   ├── audit_service.py
│   │   ├── dashboard_service.py
│   │   ├── backup_service.py
│   │   ├── reconciliation_service.py
│   │   └── system_status_service.py
│   ├── storage/
│   │   ├── paths.py
│   │   ├── filename.py
│   │   ├── validation.py
│   │   ├── signatures.py
│   │   ├── hashing.py
│   │   ├── upload.py
│   │   ├── scanner.py
│   │   ├── move.py
│   │   ├── cleanup.py
│   │   └── disk.py
│   ├── routers/
│   │   ├── public/
│   │   │   ├── home.py
│   │   │   ├── catalog.py
│   │   │   ├── software.py
│   │   │   ├── search.py
│   │   │   └── downloads.py
│   │   ├── auth/
│   │   │   └── login.py
│   │   ├── admin/
│   │   │   ├── dashboard.py
│   │   │   ├── software.py
│   │   │   ├── releases.py
│   │   │   ├── files.py
│   │   │   ├── categories.py
│   │   │   ├── tags.py
│   │   │   ├── audit.py
│   │   │   └── backups.py
│   │   └── health/
│   │       └── health.py
│   ├── templates/
│   │   ├── base.html
│   │   ├── public/
│   │   ├── admin/
│   │   ├── auth/
│   │   ├── errors/
│   │   └── components/
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   ├── images/
│   │   └── icons/
│   └── i18n/
│       └── uk.py
├── alembic/
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
├── scripts/
│   ├── entrypoint.sh
│   ├── wait_for_app.sh
│   ├── deploy.sh
│   ├── rollback.sh
│   └── backup.sh
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── security/
│   ├── e2e/
│   ├── fixtures/
│   └── conftest.py
├── nginx/
│   ├── nginx.conf
│   ├── conf.d/
│   │   ├── default.conf
│   │   ├── security_headers.conf
│   │   ├── rate_limits.conf
│   │   └── admin_restriction.conf.example
│   └── snippets/
├── docker/
│   ├── app-entrypoint.sh
│   └── healthcheck.py
├── docs/
│   ├── ADR/
│   ├── threat-model.md
│   ├── test-strategy.md
│   └── release-checklist.md
├── .github/workflows/
│   ├── ci.yml
│   └── container-scan.yml
├── Dockerfile
├── docker-compose.yml
├── docker-compose.production.yml
├── pyproject.toml
├── uv.lock або poetry.lock
├── alembic.ini
├── .env.example
├── .gitignore
├── .dockerignore
├── .pre-commit-config.yaml
├── README.md
├── ARCHITECTURE.md
├── SECURITY.md
├── DEPLOYMENT.md
├── BACKUP_RESTORE.md
├── OPERATIONS.md
└── CHANGELOG.md
```

---

# 4. ОСТАТОЧНА МОДЕЛЬ ДАНИХ

## 4.1. User

Ключові поля:

- `id`;
- `username`;
- `password_hash`;
- `is_active`;
- `is_superuser`;
- `failed_login_attempts`;
- `locked_until`;
- `password_changed_at`;
- `last_login_at`;
- `created_at`;
- `updated_at`.

Обмеження:

- unique index на normalized username;
- відсутність default production user;
- password hash лише Argon2id;
- деактивований користувач не може створити нову сесію.

## 4.2. Session

Поля:

- `id`;
- `session_token_hash`;
- `user_id`;
- `created_at`;
- `last_activity_at`;
- `expires_at`;
- `absolute_expires_at`;
- `revoked_at`;
- `user_agent_hash`;
- `ip_hash`;
- `csrf_secret_hash` або session-bound CSRF metadata.

Обмеження:

- у cookie зберігається сирий непередбачуваний token;
- у базі — hash token;
- index на `session_token_hash`;
- index на `user_id`, `expires_at`, `revoked_at`.

## 4.3. Category

Поля:

- `id`;
- `name`;
- `slug`;
- `description`;
- `sort_order`;
- `is_visible`;
- timestamps.

## 4.4. Tag

Поля:

- `id`;
- `name`;
- `slug`;
- timestamps.

Зв’язок `software_tags`:

- composite primary key або unique constraint;
- foreign keys із cascade для association records.

## 4.5. Software

Поля:

- `id`;
- `name`;
- `slug`;
- `short_description`;
- `full_description`;
- `developer_name`;
- `official_website_url`;
- `source_url`;
- `license_name`;
- `category_id`;
- `icon_path`;
- `supported_os`;
- `system_requirements`;
- `status`;
- `visibility`;
- `is_featured`;
- `created_at`;
- `updated_at`;
- `published_at`;
- `archived_at`.

Індекси:

- unique `slug`;
- `status`;
- `visibility`;
- `category_id`;
- `updated_at`;
- `is_featured`.

## 4.6. Release

Поля:

- `id`;
- `software_id`;
- `version`;
- `release_channel`;
- `release_date`;
- `changelog`;
- `is_current`;
- `status`;
- timestamps.

Обмеження:

- unique `(software_id, version, release_channel)`;
- index `(software_id, status)`;
- бізнес-обмеження одного current stable release реалізується сервісом у транзакції;
- додатковий partial unique index для SQLite можна розглянути після перевірки сумісності міграцій.

## 4.7. ReleaseFile

Поля:

- `id`;
- `public_uuid`;
- `release_id`;
- `original_filename`;
- `display_filename`;
- `storage_filename`;
- `relative_storage_path`;
- `file_extension`;
- `detected_mime_type`;
- `file_size_bytes`;
- `sha256`;
- `architecture`;
- `package_type`;
- `platform`;
- `edition`;
- `download_count`;
- `status`;
- `visibility`;
- `uploaded_at`;
- `published_at`;
- `disabled_at`;
- `source_url`;
- `signature_status`;
- `scanner_status`;
- `scanner_details`;
- `admin_note`.

Індекси:

- unique `public_uuid`;
- index `sha256`;
- index `release_id`;
- index `(status, visibility)`;
- index `uploaded_at`.

## 4.8. DownloadStat

Поля:

- `id`;
- `release_file_id`;
- `date`;
- `download_count`;
- `successful_download_count`;
- `blocked_download_count`.

Обмеження:

- unique `(release_file_id, date)`;
- atomic upsert у короткій транзакції.

## 4.9. AuditLog

Поля:

- `id`;
- `user_id`;
- `action`;
- `entity_type`;
- `entity_id`;
- `result`;
- `timestamp`;
- `safe_metadata_json`;
- `request_id`;
- `ip_hash`.

Обмеження:

- append-only на рівні application service;
- жодних паролів, cookies, CSRF tokens, secrets;
- індекси на `timestamp`, `action`, `user_id`, `(entity_type, entity_id)`.

---

# 5. ПОФАЗНИЙ ПЛАН

---

# ФАЗА 0. ФІКСАЦІЯ РІШЕНЬ І МЕЖ MVP

## Мета

Перетворити master prompt на набір однозначних технічних рішень, щоб під час реалізації не виникало суперечливих трактувань.

## Завдання

1. Зафіксувати MVP scope і out-of-scope.
2. Створити ADR-документи:
   - вибір модульного моноліту;
   - SQLite для MVP;
   - server-side sessions;
   - X-Accel-Redirect;
   - файлове сховище поза web-root;
   - ручна публікація після quarantine;
   - plain text для описів у першій версії;
   - один Uvicorn worker у production.
3. Визначити:
   - package manager;
   - Python version;
   - формат primary keys;
   - session cookie name;
   - max upload size;
   - retention сесій, логів і backup;
   - політику для disabled downloads: `404` або `410`;
   - політику підрахунку download count;
   - початковий allowlist.
4. Скласти threat model.
5. Створити release checklist.

## Файли

```text
docs/ADR/0001-modular-monolith.md
docs/ADR/0002-sqlite-for-mvp.md
docs/ADR/0003-server-side-sessions.md
docs/ADR/0004-x-accel-redirect.md
docs/ADR/0005-upload-quarantine.md
docs/threat-model.md
docs/release-checklist.md
```

## Залежності

Немає.

## Критерії завершення

- усі спірні рішення задокументовані;
- немає невизначеності щодо статусів та переходів;
- визначено policy defaults;
- зафіксовано MVP acceptance checklist;
- фаза не містить коду бізнес-логіки.

## Тести й перевірки

- review документації;
- перевірка відсутності суперечностей між ADR;
- звірка з master prompt.

## Ризики

- занадто рання фіксація дрібних деталей;
- непомітне розширення scope;
- конфлікт між зручністю й security.

## Результат

Стабільна технічна база для подальших фаз.

---

# ФАЗА 1. BOOTSTRAP РЕПОЗИТОРІЮ ТА ЯКІСТЬ КОДУ

## Мета

Створити мінімальний, але повністю робочий каркас репозиторію з автоматизованими перевірками.

## Завдання

1. Ініціалізувати Python-проєкт.
2. Створити `pyproject.toml`.
3. Зафіксувати runtime і dev dependencies.
4. Налаштувати:
   - Ruff format;
   - Ruff lint;
   - mypy;
   - pytest;
   - pytest-cov;
   - pre-commit;
   - Bandit;
   - pip-audit.
5. Створити мінімальний FastAPI app.
6. Додати `/health` із базовим статусом application process.
7. Додати централізований application factory.
8. Додати `.env.example`, `.gitignore`, `.dockerignore`.
9. Створити базовий README.
10. Додати початковий CI без Docker scan.

## Файли

```text
app/__init__.py
app/main.py
app/core/config.py
app/routers/health/health.py
tests/unit/test_health.py
pyproject.toml
.pre-commit-config.yaml
.env.example
.gitignore
.dockerignore
.github/workflows/ci.yml
README.md
```

## Залежності

Фаза 0.

## Критерії завершення

- application запускається локально;
- `GET /health` повертає `200`;
- lint, format, mypy та pytest проходять;
- pre-commit працює;
- CI запускається на push і pull request;
- у Git немає secrets.

## Тести

- health endpoint;
- config defaults у test environment;
- application startup;
- import smoke test.

## Ризики

- надмірно суворий mypy до появи моделей;
- нестабільні dependency versions;
- змішування dev і production dependencies.

## Результат

Чистий репозиторій, який можна безпечно розвивати.

---

# ФАЗА 2. КОНФІГУРАЦІЯ, CORE, LOGGING І ERROR HANDLING

## Мета

Створити фундамент усіх cross-cutting concerns до появи бізнес-функцій.

## Завдання

1. Реалізувати typed settings.
2. Валідувати:
   - environment;
   - secret length;
   - production debug prohibition;
   - absolute storage paths;
   - allowed extensions;
   - upload limits;
   - trusted hosts.
3. Створити application exceptions.
4. Створити HTTP error handlers.
5. Реалізувати request ID.
6. Реалізувати structured logging.
7. Реалізувати request logging middleware.
8. Додати trusted host middleware.
9. Додати secure proxy policy.
10. Створити UTC time helpers.
11. Створити базові security headers на рівні app для dev; production headers надалі контролюватиме Nginx.
12. Заборонити виведення stack traces у production.

## Файли

```text
app/core/config.py
app/core/constants.py
app/core/enums.py
app/core/exceptions.py
app/core/error_handlers.py
app/core/logging.py
app/core/middleware.py
app/core/request_context.py
app/core/time.py
app/templates/errors/*.html
tests/unit/core/
tests/integration/test_error_handling.py
```

## Залежності

Фаза 1.

## Критерії завершення

- invalid production config зупиняє startup;
- weak secrets відхиляються;
- кожен request має request ID;
- production responses не містять traceback;
- error pages відображаються для основних HTTP codes;
- logs не містять cookies або form passwords.

## Тести

- missing secret;
- weak secret;
- invalid trusted host;
- request ID propagation;
- error handler mappings;
- redaction logging tests;
- production debug disabled.

## Ризики

- дублювання headers між app і Nginx;
- помилкове логування sensitive data;
- неправильна довіра до forwarded headers.

## Результат

Єдиний контрольований application core.

---

# ФАЗА 3. DATABASE FOUNDATION ТА ALEMBIC

## Мета

Підготувати надійний SQLite-шар із короткими транзакціями та міграціями.

## Завдання

1. Створити SQLAlchemy declarative base.
2. Налаштувати engine.
3. Увімкнути:
   - `PRAGMA foreign_keys=ON`;
   - `journal_mode=WAL`;
   - `busy_timeout`;
   - контроль synchronous mode.
4. Реалізувати session factory.
5. Реалізувати dependency `get_db_session`.
6. Налаштувати Alembic.
7. Додати naming conventions для constraints.
8. Налаштувати test database.
9. Створити smoke migration.
10. Реалізувати health check для database.
11. Визначити transaction boundary policy.

## Файли

```text
app/database/base.py
app/database/session.py
app/database/pragmas.py
app/database/types.py
app/database/migrations_helpers.py
alembic.ini
alembic/env.py
alembic/versions/
tests/integration/database/
```

## Залежності

Фази 1–2.

## Критерії завершення

- міграції застосовуються на чистій БД;
- downgrade останньої тестової міграції працює;
- foreign keys реально enforce-яться;
- WAL і busy timeout встановлюються для кожного connection;
- session rollback виконується при exception;
- health endpoint перевіряє database.

## Тести

- PRAGMA verification;
- FK violation;
- transaction rollback;
- migration upgrade/downgrade;
- simultaneous short writes;
- database unavailable behavior.

## Ризики

- SQLite locking;
- неправильне використання sync/async SQLAlchemy;
- довгі транзакції у майбутньому upload flow.

## Результат

Стабільний persistence foundation.

---

# ФАЗА 4. МОДЕЛІ ДАНИХ І ПЕРША ПОВНА МІГРАЦІЯ

## Мета

Реалізувати повну доменну модель без UI та складної бізнес-логіки.

## Завдання

1. Створити всі ORM models.
2. Створити enums для statuses, visibility, architecture, package type.
3. Визначити relationships та cascade rules.
4. Додати indexes і constraints.
5. Створити association table Software–Tag.
6. Створити першу production migration.
7. Додати repository base.
8. Додати factory fixtures для тестів.
9. Перевірити portability SQLAlchemy models для майбутнього PostgreSQL.
10. Не використовувати SQLite-only SQL у business layer.

## Файли

```text
app/models/*.py
app/repositories/base.py
alembic/versions/0001_initial_schema.py
tests/integration/models/
tests/fixtures/factories.py
```

## Залежності

Фаза 3.

## Критерії завершення

- всі таблиці створюються міграцією;
- всі unique constraints працюють;
- cascade поведінка задокументована;
- timestamps timezone-aware на application level;
- schema downgrade протестований;
- metadata не містить storage absolute paths.

## Тести

- unique username/slug/public UUID;
- association uniqueness;
- invalid FK;
- enum persistence;
- cascade behavior;
- index existence;
- migration from empty database.

## Ризики

- надмірна cascade deletion;
- недостатні indexes;
- прив’язка enums до конкретної СУБД.

## Результат

Повна стабільна schema v1.

---

# ФАЗА 5. REPOSITORIES ТА ДОМЕННІ STATE TRANSITIONS

## Мета

Винести доступ до БД і бізнес-переходи зі HTTP layer.

## Завдання

1. Реалізувати repositories для всіх моделей.
2. Реалізувати pagination abstraction.
3. Реалізувати пошук і фільтрацію без raw SQL concatenation.
4. Створити domain policies:
   - Software status transitions;
   - Release status transitions;
   - ReleaseFile status transitions;
   - visibility rules.
5. Реалізувати встановлення current stable release.
6. Реалізувати duplicate SHA lookup.
7. Реалізувати transactional service boundaries.
8. Створити application services без HTML dependencies.

## Файли

```text
app/repositories/*.py
app/services/category_service.py
app/services/tag_service.py
app/services/software_service.py
app/services/release_service.py
app/services/file_service.py
app/schemas/pagination.py
tests/unit/services/
tests/integration/repositories/
```

## Залежності

Фаза 4.

## Критерії завершення

- routers у майбутньому не потребуватимуть прямого ORM manipulation;
- invalid transitions повертають typed exceptions;
- current stable змінюється атомарно;
- пошук має bounded pagination;
- duplicate SHA знаходиться через index.

## Тести

- всі дозволені й заборонені transitions;
- current release replacement;
- pagination bounds;
- search normalization;
- repository rollback;
- N+1 checks для основних read queries.

## Ризики

- “fat repository” або “fat service”;
- дублювання правил у різних services;
- race condition при current release.

## Результат

Чистий application layer.

---

# ФАЗА 6. AUTHENTICATION, PASSWORDS І SERVER-SIDE SESSIONS

## Мета

Реалізувати production-oriented login без JWT та localStorage.

## Завдання

1. Argon2id password hashing.
2. CLI create-admin.
3. CLI change-admin-password.
4. Server-side session generation.
5. Session token hashing у БД.
6. Secure cookie configuration.
7. Idle timeout.
8. Absolute timeout.
9. Session revocation.
10. Session rotation після login.
11. Logout.
12. Failed login counter.
13. Temporary lockout.
14. Generic login errors.
15. Audit hooks.
16. Cleanup expired sessions.
17. Захист admin routes.
18. Password change revokes sessions згідно з ADR.

## Файли

```text
app/core/security.py
app/services/auth_service.py
app/services/session_service.py
app/repositories/user_repository.py
app/repositories/session_repository.py
app/routers/auth/login.py
app/templates/auth/login.html
app/cli.py
tests/unit/security/
tests/integration/auth/
tests/security/test_session_security.py
```

## Залежності

Фази 2, 4, 5.

## Критерії завершення

- admin створюється лише CLI;
- default password відсутній;
- login/logout працюють;
- session fixation неможлива;
- expired і revoked sessions не приймаються;
- locked user отримує generic error;
- cookie має правильні production flags;
- session token не зберігається у БД відкрито.

## Тести

- correct/incorrect password;
- unknown username;
- lockout;
- lockout expiry;
- inactive user;
- session fixation;
- idle expiry;
- absolute expiry;
- revoked session;
- logout;
- password change;
- cookie attributes;
- token entropy assumptions.

## Ризики

- DoS через lockout конкретного username;
- некоректна робота за reverse proxy;
- помилкова ротація cookie.

## Результат

Повноцінний security boundary для admin.

---

# ФАЗА 7. CSRF ТА ЗАХИСТ HTML-ФОРМ

## Мета

Захистити всі state-changing admin actions до появи CRUD UI.

## Завдання

1. Визначити session-bound CSRF design.
2. Генерувати token для forms.
3. Перевіряти token для POST actions.
4. Використовувати constant-time comparison.
5. Додати hidden field helper.
6. Додати CSRF dependency/decorator.
7. Додати dedicated CSRF exception.
8. Заборонити token у URL.
9. Додати token rotation policy.
10. Підготувати базові form helpers.

## Файли

```text
app/core/csrf.py
app/core/security.py
app/templates/components/csrf.html
tests/unit/test_csrf.py
tests/security/test_csrf_flows.py
```

## Залежності

Фаза 6.

## Критерії завершення

- POST без CSRF відхиляється;
- invalid token відхиляється;
- token іншої session відхиляється;
- logout також захищений;
- token не логуються;
- усі admin write routes зобов’язані використовувати CSRF dependency.

## Тести

- missing token;
- malformed token;
- wrong session;
- expired session;
- replay policy;
- token in query ignored;
- safe methods не вимагають token.

## Ризики

- випадкове вимкнення CSRF на окремому route;
- конфлікт із multipart upload;
- token leakage через logs.

## Результат

Готова безпечна форма-комунікація.

---

# ФАЗА 8. ADMIN CRUD: КАТЕГОРІЇ, ТЕГИ, ПРОГРАМИ ТА РЕЛІЗИ

## Мета

Реалізувати основне керування каталогом без upload-файлів.

## Завдання

1. Admin layout і navigation.
2. Dashboard skeleton.
3. Category CRUD.
4. Tag CRUD.
5. Software CRUD.
6. Release CRUD.
7. Slug generation і conflict handling.
8. URL validation.
9. Plain-text descriptions.
10. Publish/hide/archive/disable actions.
11. Preview software.
12. Current release management.
13. Audit for all actions.
14. Confirmation forms for dangerous actions.
15. Safe validation error rendering.

## Файли

```text
app/routers/admin/dashboard.py
app/routers/admin/categories.py
app/routers/admin/tags.py
app/routers/admin/software.py
app/routers/admin/releases.py
app/templates/admin/base.html
app/templates/admin/dashboard.html
app/templates/admin/categories/*
app/templates/admin/tags/*
app/templates/admin/software/*
app/templates/admin/releases/*
app/static/css/admin.css
app/static/js/admin.js
tests/integration/admin/
```

## Залежності

Фази 5–7.

## Критерії завершення

- admin може створити category;
- admin може створити software;
- admin може створити release;
- invalid state transitions заблоковані;
- всі write forms мають CSRF;
- усі дії аудитуються;
- public ще не бачить draft records;
- немає прямого ORM manipulation у routers.

## Тести

- CRUD happy paths;
- duplicate slug;
- invalid URL;
- oversized text;
- unauthorized access;
- IDOR attempts;
- CSRF;
- state transition errors;
- current stable transaction;
- XSS payload rendering.

## Ризики

- занадто складні HTML forms;
- бізнес-логіка просочується в router;
- випадкове physical delete у майбутньому.

## Результат

Повноцінне керування metadata каталогу.

---

# ФАЗА 9. STORAGE FOUNDATION ТА БЕЗПЕЧНІ ШЛЯХИ

## Мета

Створити ізольований файловий шар до реалізації upload.

## Завдання

1. Typed storage roots.
2. Startup validation directories.
3. Створення required directories.
4. Перевірка прав доступу.
5. Safe path join.
6. Resolved path containment.
7. Server-generated storage names.
8. Filename normalization.
9. Unicode handling.
10. Null byte rejection.
11. Double-extension policy.
12. Disk free-space check.
13. Atomic move abstraction.
14. Cleanup temporary files.
15. Заборона executable permissions.

## Файли

```text
app/storage/paths.py
app/storage/filename.py
app/storage/move.py
app/storage/cleanup.py
app/storage/disk.py
tests/unit/storage/
tests/security/test_path_traversal.py
```

## Залежності

Фаза 2.

## Критерії завершення

- жоден user-controlled string не стає physical path;
- `../`, encoded traversal і absolute paths блокуються;
- storage directories перевіряються при startup;
- atomic move працює на цільовій filesystem;
- temp cleanup безпечний;
- app не виставляє executable bit.

## Тести

- traversal variants;
- null byte;
- Windows path separators;
- Unicode normalization;
- very long filename;
- reserved filenames;
- insufficient disk space;
- move failure;
- cross-device move behavior.

## Ризики

- різні filesystem semantics;
- storage і temp на різних mount points;
- permission drift у production.

## Результат

Безпечний storage abstraction.

---

# ФАЗА 10. STREAMING UPLOAD, VALIDATION І QUARANTINE

## Мета

Реалізувати головний security-critical upload pipeline.

## Завдання

1. Streaming multipart upload.
2. Content-Length pre-check, якщо header присутній.
3. Actual byte count.
4. Hard max upload size.
5. Temporary file lifecycle.
6. SHA-256 during streaming.
7. Extension allowlist.
8. Magic bytes validation:
   - PE/EXE;
   - MSI/Compound File;
   - ZIP;
   - 7z.
9. Browser MIME не вважати trusted.
10. Duplicate SHA detection.
11. Scanner interface.
12. No-op/unavailable scanner implementation.
13. Optional ClamAV adapter.
14. Move to quarantine.
15. Metadata creation.
16. Compensation cleanup.
17. Upload progress UX лише як enhancement.
18. Audit success/failure.
19. Rejection and manual review statuses.

## Файли

```text
app/storage/upload.py
app/storage/validation.py
app/storage/signatures.py
app/storage/hashing.py
app/storage/scanner.py
app/services/file_service.py
app/routers/admin/files.py
app/templates/admin/files/new.html
app/templates/admin/files/detail.html
app/static/js/upload.js
tests/unit/storage/test_signatures.py
tests/integration/upload/
tests/security/test_upload_attacks.py
```

## Залежності

Фази 5, 7, 8, 9.

## Критерії завершення

- великі файли не читаються повністю в RAM;
- oversized upload видаляється з temp;
- spoofed MIME не обходить validation;
- невідомий тип лишається у quarantine;
- infected файл не може бути published;
- duplicate hash позначається;
- metadata і file lifecycle не розходяться;
- upload transaction коротка.

## Тести

- valid EXE/MSI/ZIP/7z signatures;
- wrong extension;
- spoofed MIME;
- double extension;
- null byte;
- oversized body;
- interrupted upload;
- duplicate hash;
- scanner unavailable;
- scanner infected;
- DB failure after temp write;
- move failure;
- orphan prevention.

## Ризики

- складність reliable compensation;
- false positives magic detection;
- ClamAV memory consumption;
- web server body limit не збігається з app limit.

## Результат

Безпечне завантаження файлів у quarantine.

---

# ФАЗА 11. FILE LIFECYCLE: REVIEW, PUBLISH, DISABLE, ARCHIVE, DELETE

## Мета

Завершити керування ReleaseFile після upload.

## Завдання

1. Admin metadata view.
2. Publish readiness checks.
3. Atomic move quarantine → permanent.
4. Update relative path.
5. Publish transaction.
6. Disable action.
7. Archive action.
8. Delete metadata policy.
9. Permanent delete policy.
10. Separate confirmations.
11. Copy public URL.
12. Test download button.
13. Verify file existence before actions.
14. Duplicate warning.
15. Audit every transition.
16. Compensation на move/commit failure.

## Файли

```text
app/services/file_service.py
app/routers/admin/files.py
app/templates/admin/files/*
tests/unit/services/test_file_transitions.py
tests/integration/files/
```

## Залежності

Фаза 10.

## Критерії завершення

- quarantine file не може бути public;
- publish перевіряє scanner/validation status;
- published metadata завжди відповідає physical file;
- disable не видаляє файл;
- permanent delete відокремлений від archive;
- усі destructive actions мають CSRF і confirmation;
- помилки не залишають published metadata без file.

## Тести

- publish happy path;
- publish invalid state;
- missing physical file;
- move failure;
- DB commit failure;
- disable;
- archive;
- delete metadata;
- permanent delete;
- repeated action idempotency.

## Ризики

- partial failure між filesystem і DB;
- випадкове permanent deletion;
- storage permissions.

## Результат

Повний контроль життєвого циклу файла.

---

# ФАЗА 12. PUBLIC DOWNLOAD ENDPOINT І X-ACCEL-REDIRECT

## Мета

Реалізувати безпечне і продуктивне завантаження через Nginx.

## Завдання

1. Download lookup by UUID.
2. Safe filename handling.
3. Check Software status/visibility.
4. Check Release status.
5. Check ReleaseFile status/visibility.
6. Admin-only access для private.
7. HEAD behavior.
8. Content-Disposition.
9. MIME type.
10. X-Accel-Redirect header.
11. Internal URI mapping.
12. Physical file verification.
13. DownloadStat update.
14. `download_count` update.
15. Blocked count policy.
16. Rate limiting configuration.
17. Range/resume через Nginx.
18. Direct internal location denial.
19. 404/410 policy.
20. Request ID in logs.

## Файли

```text
app/services/download_service.py
app/routers/public/downloads.py
app/repositories/download_stat_repository.py
nginx/conf.d/default.conf
nginx/conf.d/rate_limits.conf
tests/integration/downloads/
tests/security/test_download_authorization.py
```

## Залежності

Фази 5, 6, 11.

## Критерії завершення

- FastAPI не передає file body;
- Nginx віддає physical file;
- internal location недоступний напряму;
- private, disabled, draft і quarantine недоступні;
- HEAD не збільшує counter;
- physical path не витікає;
- resume працює на інтеграційному стенді.

## Тести

- public/unlisted/private;
- disabled;
- archived;
- missing file;
- wrong filename;
- UUID enumeration resistance;
- HEAD;
- range;
- direct internal URI;
- blocked count;
- Host header;
- path leakage.

## Ризики

- неправильне mapping internal URI;
- подвійний count через retries;
- X-Accel headers випадково віддаються proxy.

## Результат

Production-grade file delivery.

---

# ФАЗА 13. ПУБЛІЧНИЙ КАТАЛОГ, SEARCH І SOFTWARE PAGES

## Мета

Створити повний публічний користувацький сценарій.

## Завдання

1. Public base layout.
2. Home page.
3. Catalog.
4. Search.
5. Category filter.
6. Tag filter.
7. Sorting.
8. Pagination.
9. Software card.
10. Software detail page.
11. Release history.
12. Available files table.
13. Recommended file selection.
14. SHA-256 display.
15. Trust metadata.
16. Empty states.
17. Public visibility rules.
18. Unlisted behavior.
19. Private behavior.
20. Robots and favicon routes.

## Файли

```text
app/routers/public/home.py
app/routers/public/catalog.py
app/routers/public/software.py
app/routers/public/search.py
app/templates/public/*
app/templates/components/software_card.html
app/templates/components/pagination.html
app/static/css/public.css
tests/integration/public/
```

## Залежності

Фази 5, 8, 12.

## Критерії завершення

- користувач знаходить software;
- бачить current version;
- обирає файл;
- отримує download;
- draft/hidden/private не витікають;
- pagination bounded;
- search input normalized;
- HTML autoescape не обходиться.

## Тести

- home sections;
- search;
- filters;
- sorting;
- pagination edge cases;
- unlisted direct URL;
- private URL;
- empty catalog;
- XSS payload display;
- invalid slug.

## Ризики

- складні query combinations;
- N+1 queries;
- неправильне трактування hidden/unlisted.

## Результат

Повний публічний MVP flow.

---

# ФАЗА 14. UI/UX, RESPONSIVE DESIGN, THEME, ACCESSIBILITY І SEO

## Мета

Довести інтерфейс до production-ready стану без SPA.

## Завдання

1. Mobile-first CSS.
2. Responsive catalog grid.
3. Responsive admin forms.
4. Dark/light/system theme.
5. Theme storage.
6. No-JS fallback.
7. Visible focus states.
8. Keyboard navigation.
9. Semantic headings.
10. Form labels.
11. Error summaries.
12. Color contrast.
13. Reduced motion.
14. Icon alt behavior.
15. Metadata:
    - title;
    - description;
    - canonical;
    - Open Graph.
16. `noindex` для admin/login.
17. `robots.txt`.
18. Optional sitemap.
19. No inline scripts для CSP compatibility.
20. Basic browser compatibility checks.

## Файли

```text
app/templates/base.html
app/templates/components/*
app/static/css/base.css
app/static/css/components.css
app/static/css/theme.css
app/static/js/theme.js
app/static/js/admin.js
app/routers/public/seo.py або відповідні handlers
tests/e2e/accessibility/
```

## Залежності

Фази 8, 13.

## Критерії завершення

- desktop і mobile сценарії працюють;
- основна навігація працює без JS;
- theme перемикається;
- focus видимий;
- HTML має логічну структуру;
- admin не індексується;
- inline JS відсутній або обґрунтований nonce policy.

## Тести

- viewport sizes;
- keyboard-only flow;
- forms;
- theme persistence;
- no-JS smoke;
- axe accessibility checks;
- metadata assertions;
- robots rules.

## Ризики

- CSS scope conflicts;
- CSP несумісність;
- надлишкова анімація.

## Результат

Якісний адаптивний SSR-інтерфейс.

---

# ФАЗА 15. AUDIT, DASHBOARD, HEALTH І OBSERVABILITY

## Мета

Додати адміністратору контроль стану системи та безпечний аудит.

## Завдання

1. Audit service.
2. Centralized action names.
3. Safe metadata filtering.
4. Login success/failure audit.
5. CRUD audit.
6. Upload/download management audit.
7. Backup audit.
8. Audit filters.
9. Dashboard metrics.
10. Quarantine count.
11. Disabled count.
12. Disk free space.
13. Database status.
14. Storage status.
15. Last backup.
16. Recent admin actions.
17. Structured app events.
18. Improved health:
    - app;
    - DB;
    - storage;
    - disk threshold.
19. Не повертати secrets або physical paths.

## Файли

```text
app/services/audit_service.py
app/services/dashboard_service.py
app/services/system_status_service.py
app/repositories/audit_repository.py
app/routers/admin/audit.py
app/routers/admin/dashboard.py
app/templates/admin/audit/*
app/templates/admin/dashboard.html
tests/integration/audit/
tests/integration/health/
```

## Залежності

Фази 6, 8, 10–13.

## Критерії завершення

- всі security-sensitive admin actions аудитуються;
- audit metadata проходить allowlist;
- dashboard не виконує дорогі unbounded queries;
- health має коректні статуси;
- sensitive information не витікає.

## Тести

- audit event coverage;
- redaction;
- filters;
- unavailable storage;
- database error;
- low disk;
- dashboard empty state;
- large audit dataset pagination.

## Ризики

- audit log growth;
- логування персональних даних;
- health endpoint як інформаційний витік.

## Результат

Операційна прозорість системи.

---

# ФАЗА 16. BACKUP, RESTORE, RECONCILIATION І MAINTENANCE CLI

## Мета

Забезпечити відновлюваність і контроль consistency.

## Завдання

1. Safe SQLite backup API.
2. Timestamped backup directories.
3. Manifest.
4. Checksums.
5. Storage metadata snapshot.
6. Icons backup.
7. Config template backup.
8. Retention cleanup.
9. Backup status record або manifest discovery.
10. Restore command із confirmation.
11. Restore preflight.
12. Verify backup checksum.
13. Reconciliation:
    - metadata without file;
    - orphan files;
    - SHA mismatch;
    - invalid paths;
    - duplicate hashes.
14. Dry-run by default.
15. Explicit destructive flag.
16. CLI commands:
    - create-admin;
    - change-admin-password;
    - revoke-sessions;
    - cleanup-expired-sessions;
    - cleanup-temporary-files;
    - create-backup;
    - restore-backup;
    - verify-storage;
    - recalculate-checksums;
    - find-orphan-files;
    - show-system-status.
17. Correct exit codes.
18. Audit backup operations.

## Файли

```text
app/services/backup_service.py
app/services/reconciliation_service.py
app/cli.py
scripts/backup.sh
BACKUP_RESTORE.md
OPERATIONS.md
tests/integration/backup/
tests/integration/reconciliation/
```

## Залежності

Фази 3, 9–11, 15.

## Критерії завершення

- live SQLite backup не пошкоджується;
- restore проходить на чистій test environment;
- manifest і checksums валідні;
- retention працює;
- reconciliation нічого не видаляє без explicit flag;
- CLI не друкує secrets.

## Тести

- backup during normal reads/writes;
- corrupted archive;
- wrong checksum;
- missing storage;
- restore to empty environment;
- orphan detection;
- metadata without file;
- SHA mismatch;
- dry-run;
- cleanup retention;
- interrupted backup.

## Ризики

- великий storage backup;
- брак дискового простору;
- restore поверх активної system;
- backup на тому самому фізичному диску.

## Результат

Перевірений disaster-recovery flow.

---

# ФАЗА 17. DOCKER, NGINX І PRODUCTION HARDENING

## Мета

Перетворити application на безпечний deployment unit.

## Завдання

1. Multi-stage Dockerfile.
2. Non-root app user.
3. Minimal runtime image.
4. Entrypoint.
5. Graceful shutdown.
6. App healthcheck.
7. Docker Compose:
   - app;
   - nginx;
   - optional certbot;
   - optional clamav profile.
8. Persistent mounts.
9. Read-only root filesystem.
10. Writable tmpfs.
11. Drop capabilities.
12. No privileged mode.
13. No Docker socket.
14. Nginx:
   - TLS;
   - redirects;
   - static;
   - protected downloads;
   - upload limit;
   - login rate limit;
   - download rate limit;
   - security headers;
   - `server_tokens off`;
   - deny dotfiles;
   - deny database/backups/config.
15. Trusted proxy configuration.
16. Admin network restriction example.
17. Log rotation strategy.
18. Certbot renewal documentation.
19. Production compose override.
20. Container resource recommendations.

## Файли

```text
Dockerfile
docker-compose.yml
docker-compose.production.yml
docker/app-entrypoint.sh
nginx/nginx.conf
nginx/conf.d/*.conf
nginx/snippets/*
DEPLOYMENT.md
SECURITY.md
```

## Залежності

Фази 1–16.

## Критерії завершення

- clean Docker build;
- app container non-root;
- compose starts on empty host directories;
- migrations execute safely;
- Nginx serves static and downloads;
- internal path inaccessible;
- `.env`, DB і backups inaccessible;
- security headers present;
- healthchecks green;
- containers restart correctly;
- shutdown не пошкоджує active operations.

## Тести

- container user;
- read-only filesystem;
- mount permissions;
- startup without secrets;
- Nginx config test;
- headers;
- HTTP→HTTPS;
- direct internal access;
- upload too large;
- rate limit;
- dotfile access;
- container restart.

## Ризики

- permissions на bind mounts;
- certbot complexity;
- rootless restrictions;
- app/nginx UID mismatch.

## Результат

Production deployment package.

---

# ФАЗА 18. ПОВНИЙ TESTING HARDENING І CI

## Мета

Об’єднати всі перевірки у reproducible quality gate.

## Завдання

1. Розширити unit coverage.
2. Integration suite.
3. Security suite.
4. E2E Playwright suite.
5. Coverage threshold.
6. CI jobs:
   - Ruff format;
   - Ruff lint;
   - mypy;
   - pytest;
   - coverage;
   - Bandit;
   - pip-audit;
   - Docker build;
   - Trivy;
   - migration test;
   - E2E smoke.
7. Test fixtures for sample files.
8. Redact secrets in CI logs.
9. Cache dependencies safely.
10. Upload test artifacts.
11. Fail pipeline on unjustified critical vulnerabilities.
12. Document accepted scan exceptions.

## Файли

```text
tests/unit/*
tests/integration/*
tests/security/*
tests/e2e/*
docs/test-strategy.md
.github/workflows/ci.yml
.github/workflows/container-scan.yml
```

## Залежності

Усі функціональні фази.

## Критерії завершення

- CI green;
- critical security flows покриті;
- migrations tested from zero;
- E2E повністю проходить;
- coverage threshold реалістичний і enforced;
- security scan exceptions задокументовані;
- flaky tests відсутні.

## Обов’язковий E2E сценарій

```text
login
→ create category
→ create software
→ create release
→ upload file
→ review quarantine
→ publish file
→ open public software page
→ download
→ disable file
→ verify download unavailable
```

## Ризики

- flaky browser tests;
- slow CI;
- vulnerability false positives;
- тестове оточення відрізняється від production.

## Результат

Автоматичний quality gate перед release.

---

# ФАЗА 19. ДОКУМЕНТАЦІЯ, DEPLOYMENT RUNBOOK І RELEASE CANDIDATE

## Мета

Зробити проєкт підтримуваним однією людиною без знань “лише в голові”.

## Завдання

1. Завершити README.
2. ARCHITECTURE.
3. SECURITY.
4. DEPLOYMENT.
5. BACKUP_RESTORE.
6. OPERATIONS.
7. CHANGELOG.
8. Environment variable reference.
9. Local development guide.
10. Production deployment guide.
11. Proxmox VM guide.
12. VPS guide.
13. DNS і TLS.
14. WireGuard/IP allowlist.
15. Update procedure.
16. Rollback.
17. Common failures.
18. Disk monitoring.
19. Backup verification.
20. Certificate renewal.
21. Release checklist.
22. Threat model review.
23. Security acceptance checklist.
24. Final migration rehearsal.
25. Final restore rehearsal.

## Файли

```text
README.md
ARCHITECTURE.md
SECURITY.md
DEPLOYMENT.md
BACKUP_RESTORE.md
OPERATIONS.md
CHANGELOG.md
docs/release-checklist.md
```

## Залежності

Усі попередні фази.

## Критерії завершення

- новий Ubuntu Server можна підготувати лише за документацією;
- admin створюється за інструкцією;
- backup і restore відтворюються;
- rollback описаний;
- немає undocumented required steps;
- acceptance checklist повністю пройдений.

## Тести

- deployment rehearsal;
- restore rehearsal;
- certificate config test;
- fresh admin bootstrap;
- clean database migration;
- smoke test production compose.

## Ризики

- документація відстає від коду;
- ручні кроки без перевірки;
- rollback лише теоретичний.

## Результат

Release candidate, готовий до production acceptance.

---

# ФАЗА 20. PRODUCTION ACCEPTANCE І ЗАПУСК

## Мета

Безпечно розгорнути MVP на `software.hotzagor.tech`.

## Завдання

1. Підготувати Ubuntu Server VM/VPS.
2. Оновити систему.
3. Налаштувати SSH keys.
4. Вимкнути password SSH.
5. Вимкнути root login.
6. Налаштувати firewall.
7. Створити `/srv/software-hub`.
8. Налаштувати власників і permissions.
9. Встановити Docker.
10. Розгорнути compose.
11. Задати production secrets.
12. Застосувати migrations.
13. Створити admin.
14. Налаштувати DNS.
15. Отримати TLS certificate.
16. Увімкнути HTTPS redirect.
17. Увімкнути HSTS після перевірки.
18. Обмежити admin через WireGuard/IP, якщо доступно.
19. Завантажити test software.
20. Пройти full E2E.
21. Створити перший backup.
22. Відновити backup у test directory або окремій VM.
23. Увімкнути operational monitoring.
24. Зафіксувати version tag.
25. Створити release notes.

## Залежності

Фаза 19.

## Критерії завершення

- домен працює через HTTPS;
- HTTP redirect працює;
- admin protected;
- upload/download працюють;
- X-Accel-Redirect працює;
- backup verified;
- health green;
- security acceptance checklist completed;
- release tagged.

## Ризики

- DNS propagation;
- неправильні permissions;
- відсутність offsite backup;
- відкритий admin endpoint;
- нестача storage.

## Результат

Production MVP v1.0.0.

---

# 6. ЗАЛЕЖНОСТІ МІЖ ФАЗАМИ

```text
0  Decisions
└── 1  Bootstrap
    └── 2  Core/config/logging
        ├── 3  Database foundation
        │   └── 4  Models/migrations
        │       └── 5  Repositories/domain rules
        │           ├── 6  Auth/sessions
        │           │   └── 7  CSRF
        │           │       └── 8  Admin CRUD
        │           ├── 13 Public catalog
        │           └── 15 Audit/dashboard
        └── 9  Storage foundation
            └── 10 Upload/quarantine
                └── 11 File lifecycle
                    └── 12 Downloads/X-Accel

8 + 12 + 13
└── 14 UI/UX/accessibility/SEO

3 + 9 + 11 + 15
└── 16 Backup/reconciliation/CLI

Усі функціональні фази
└── 17 Docker/Nginx hardening
    └── 18 Testing/CI
        └── 19 Documentation/RC
            └── 20 Production launch
```

Критичний шлях:

```text
0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8
                          └→ 9 → 10 → 11 → 12
8 + 12 → 13 → 14 → 15 → 16 → 17 → 18 → 19 → 20
```

---

# 7. SECURITY PLAN

## 7.1. Authentication

- Argon2id;
- generic login errors;
- app-level lockout;
- Nginx rate limiting;
- no default user;
- server-side sessions;
- session ID rotation;
- idle and absolute expiration;
- revocation;
- secure cookie flags;
- session token hash in DB.

## 7.2. CSRF

- token bound to active session;
- required for every state-changing form;
- constant-time verification;
- no token in query string;
- token omitted from logs;
- dedicated security tests.

## 7.3. XSS

- Jinja autoescape;
- plain text descriptions in MVP;
- no `|safe` for user content;
- no arbitrary HTML;
- validated external URLs;
- no untrusted `innerHTML`;
- CSP-compatible JS;
- security headers.

## 7.4. SQL injection

- ORM and parameterized queries;
- no string-built SQL;
- bounded pagination;
- normalized search;
- typed filter enums;
- injection tests.

## 7.5. Upload security

- stream to temp;
- actual size limit;
- filename normalization;
- extension allowlist;
- magic bytes;
- SHA-256;
- duplicate detection;
- quarantine;
- optional scanner;
- atomic move;
- no execution;
- no archive extraction;
- cleanup on failure.

## 7.6. Download security

- UUID lookup;
- no path input;
- full chain visibility checks;
- X-Accel-Redirect;
- internal Nginx location;
- no direct storage exposure;
- HEAD policy;
- disabled/private protection;
- safe Content-Disposition.

## 7.7. Infrastructure

- non-root container;
- dropped capabilities;
- read-only root FS;
- no Docker socket;
- no privileged mode;
- bind mounts only where needed;
- Nginx denies sensitive paths;
- TLS;
- security headers;
- admin network restriction.

## 7.8. Secrets

- typed settings;
- fail-fast;
- `.env.example` only;
- production secrets outside Git;
- no random secret regeneration at startup;
- file permissions `600` або Docker secrets.

## 7.9. Audit/privacy

- hashed/truncated IP;
- no full IP retention by default;
- no passwords/tokens/cookies;
- append-only audit flow;
- retention policy;
- request IDs.

---

# 8. TESTING PLAN

## 8.1. Unit

Покрити:

- slug generation;
- normalization;
- password hashing;
- session expiry;
- CSRF;
- state transitions;
- visibility;
- safe path resolution;
- signatures;
- hashing;
- duplicate detection;
- current release logic;
- backup manifest;
- retention logic.

## 8.2. Integration

Покрити:

- repositories;
- database constraints;
- migrations;
- login/logout;
- admin authorization;
- CRUD;
- upload;
- publish;
- download authorization;
- statistics;
- audit;
- backup;
- restore;
- reconciliation.

## 8.3. Security

Покрити:

- SQL injection;
- XSS;
- CSRF;
- traversal;
- encoded traversal;
- null byte;
- double extension;
- oversized upload;
- MIME spoofing;
- duplicate hash;
- brute force;
- lockout;
- session fixation;
- expired/revoked session;
- IDOR;
- direct internal URI;
- private/disabled file;
- Host header;
- sensitive file exposure;
- logs redaction.

## 8.4. E2E

Мінімальний production-like flow:

```text
admin login
→ category
→ software
→ release
→ file upload
→ quarantine review
→ publish
→ public page
→ download
→ disable
→ download denied
```

## 8.5. Quality gates

Рекомендований початковий threshold:

- overall coverage: не менше 80%;
- services/security-critical modules: не менше 90%;
- upload/download/auth critical branches: максимально повне branch coverage;
- жодного failing security test;
- жодного unreviewed critical container vulnerability.

---

# 9. DEPLOYMENT PLAN

## 9.1. Development

```text
local Python environment
→ SQLite test/development DB
→ local storage directory
→ Uvicorn
→ optional local Nginx profile
```

## 9.2. Integration

```text
Docker Compose
→ app
→ nginx
→ mounted test storage
→ temporary TLS or HTTP-only local profile
→ E2E tests
```

## 9.3. Production

```text
Ubuntu Server
→ Docker Engine
→ /srv/software-hub
→ production env/secrets
→ app container
→ nginx container
→ Let's Encrypt
→ DNS software.hotzagor.tech
→ optional WireGuard admin restriction
```

## 9.4. Update

```text
backup
→ pull tagged release
→ build images
→ run migrations
→ start new containers
→ health check
→ smoke test
→ keep previous image/tag for rollback
```

## 9.5. Rollback

```text
stop current containers
→ restore previous image/tag
→ downgrade DB only if explicitly supported
→ otherwise restore pre-deploy backup
→ start previous version
→ health and smoke test
```

Важливе правило: destructive migrations не виконувати без окремого tested migration plan.

---

# 10. ОСНОВНІ РИЗИКИ

## 10.1. SQLite locking

**Причина:** довгі транзакції або кілька workers.
**Зниження:** один worker, WAL, busy timeout, короткі транзакції, Nginx downloads.

## 10.2. DB/filesystem inconsistency

**Причина:** commit або move завершується частково.
**Зниження:** temporary/quarantine, atomic move, compensation cleanup, reconciliation CLI.

## 10.3. Upload bypass

**Причина:** довіра лише до extension/MIME.
**Зниження:** allowlist + magic bytes + hash + quarantine + optional scanner.

## 10.4. Accidental deletion

**Причина:** змішування archive, disable і delete.
**Зниження:** окремі actions, confirmations, CSRF, audit, backup.

## 10.5. Admin exposure

**Причина:** admin доступний з інтернету.
**Зниження:** WireGuard/IP allowlist, rate limiting, strong password, audit.

## 10.6. Disk exhaustion

**Причина:** uploads, temp, backups, logs.
**Зниження:** free-space checks, retention, health thresholds, cleanup commands.

## 10.7. Backup exists but cannot restore

**Причина:** backup ніколи не тестували.
**Зниження:** регулярний restore rehearsal і checksum validation.

## 10.8. Permission mismatch in Docker

**Причина:** UID/GID і bind mounts.
**Зниження:** documented ownership, startup preflight, fixed container UID.

## 10.9. Download counter accuracy

**Причина:** X-Accel лише фіксує authorized start, а не completion.
**Зниження:** чітко задокументувати semantics MVP; за потреби пізніше аналізувати Nginx logs.

## 10.10. Scope creep

**Причина:** додавання sync, public API, S3, notifications.
**Зниження:** out-of-scope list і ADR для кожного нового великого компонента.

---

# 11. РІШЕННЯ, ЯКІ ПОТРІБНО ЗАФІКСУВАТИ ПЕРЕД КОДОМ

Рекомендовані значення для першої реалізації:

| Рішення | Рекомендація |
|---|---|
| Python | актуальна підтримувана stable версія, зафіксована в `pyproject.toml` |
| Package manager | `uv` із `uv.lock` |
| Primary keys | integer internal IDs; UUID для public ReleaseFile |
| Description format | plain text у MVP |
| Session cookie | `software_hub_session` |
| Idle timeout | 30 хвилин |
| Absolute session timeout | 12 годин |
| Login lockout | 5 невдалих спроб / 15 хвилин |
| Max upload | 2 GiB як configurable default, узгоджений з Nginx |
| Initial extensions | `.exe`, `.msi`, `.zip`, `.7z` |
| Disabled download response | `404` для мінімізації витоку стану |
| Download count | authorized GET start; HEAD не рахується |
| Admin access | через WireGuard у production, fallback — internet + hardening |
| Uvicorn workers | 1 |
| Scanner | optional, disabled by default |
| Backup DB | щодня |
| Backup storage | щотижня або після великих змін |
| Audit retention | configurable, початково 180 днів |
| App logs | stdout + Docker rotation |
| Full IP storage | не зберігати безстроково |
| Public file deletion | тільки окремою explicit permanent action |
| Database migration policy | additive/reversible migrations для MVP |

Ці значення не є зміною затвердженої архітектури; це конкретизація параметрів.

---

# 12. DEFINITION OF DONE ДЛЯ КОЖНОЇ ФАЗИ

Фаза вважається завершеною лише коли:

```text
[ ] Код реалізовано без критичних TODO
[ ] Ruff format check проходить
[ ] Ruff lint проходить
[ ] mypy проходить
[ ] Unit tests проходять
[ ] Integration/security tests фази проходять
[ ] Міграції перевірено, якщо schema змінювалася
[ ] Документацію оновлено
[ ] Нові env variables додані в .env.example
[ ] Нові security assumptions задокументовано
[ ] Логи не містять secrets
[ ] Немає необґрунтованих broad exception handlers
[ ] Ручний smoke test виконано
[ ] Відомі обмеження зафіксовано
```

---

# 13. ЗАГАЛЬНІ КРИТЕРІЇ ГОТОВНОСТІ MVP

```text
[ ] Clean Docker Compose startup
[ ] Clean database migrations
[ ] CLI admin creation
[ ] Secure login
[ ] Server-side sessions
[ ] CSRF on all writes
[ ] Category/Tag CRUD
[ ] Software CRUD
[ ] Release CRUD
[ ] Streaming file upload
[ ] Signature validation
[ ] SHA-256
[ ] Quarantine
[ ] Manual publish
[ ] X-Accel-Redirect downloads
[ ] Private/disabled protection
[ ] Download statistics
[ ] Audit log
[ ] Dashboard and health
[ ] Backup
[ ] Tested restore
[ ] Reconciliation
[ ] Responsive UI
[ ] Dark/light/system theme
[ ] Accessibility checks
[ ] Security headers
[ ] Rate limiting
[ ] Non-root containers
[ ] CI and container scan
[ ] Full documentation
[ ] Production release checklist passed
```

---

# 14. РЕКОМЕНДОВАНИЙ ПОРЯДОК РОБОТИ ШТУЧНОГО ІНТЕЛЕКТУ

Для кожної фази AI повинен:

1. Перечитати master prompt і поточну фазу.
2. Перевірити залежності.
3. Показати короткий implementation checklist.
4. Реалізувати лише scope поточної фази.
5. Не створювати фейкові заглушки.
6. Не додавати out-of-scope технології.
7. Запустити:
   - format;
   - lint;
   - mypy;
   - tests;
   - migrations, якщо потрібно.
8. Оновити документацію.
9. Показати:
   - створені файли;
   - змінені файли;
   - команди перевірки;
   - результати тестів;
   - відомі ризики;
   - критерії, які пройдено.
10. Не переходити до наступної фази без окремої команди.

---

# 15. ПЕРША КОМАНДА ДЛЯ ПОЧАТКУ РЕАЛІЗАЦІЇ

Після затвердження цього плану наступна команда для AI може бути такою:

```text
Починай реалізацію Software Hub із Фази 0 та Фази 1.

Спочатку:
1. зафіксуй ADR і технічні рішення;
2. створи структуру репозиторію;
3. налаштуй pyproject.toml, lock-файл, Ruff, mypy, pytest, pytest-cov, pre-commit;
4. створи application factory;
5. реалізуй базовий /health;
6. створи початковий CI;
7. не переходь до database models, auth, admin CRUD або upload pipeline.

Після завершення покажи:
- перелік створених файлів;
- повний diff ключових конфігурацій;
- команди запуску;
- результати lint, mypy і pytest;
- невирішені питання;
- checklist завершення Фази 0 і Фази 1.
```

---

# 16. ПІДСУМОК

План розбиває Software Hub на послідовні вертикальні й інфраструктурні фази. Найбільш критичні частини — authentication, CSRF, upload pipeline, file lifecycle, X-Accel downloads, backup/restore та reconciliation — винесені в окремі фази й мають власні security tests.

Рекомендований принцип виконання:

```text
не будувати весь проєкт одразу
→ завершувати одну фазу
→ запускати перевірки
→ фіксувати документацію
→ переходити далі лише після Definition of Done
```

Це дозволить отримати не просто робочий сайт, а контрольований, відновлюваний і безпечний MVP, який реально підтримувати одній людині.
