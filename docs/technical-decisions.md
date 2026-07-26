# Software Hub — зафіксовані технічні рішення

**Статус:** затверджено для початку реалізації  
**Дата:** 2026-07-23

## 1. Runtime і залежності

| Рішення | Зафіксоване значення | Причина |
|---|---|---|
| Python | `3.14.x`, constraint `>=3.14,<3.15` | актуальна стабільна bugfix-гілка; не використовувати Python 3.15 pre-release |
| Package manager | `uv` | один інструмент для environment, dependency resolution і запуску команд |
| Lock file | `uv.lock` у Git | відтворювані exact dependency versions |
| Backend | FastAPI | затверджено master prompt |
| ORM | SQLAlchemy 2.x | затверджено master prompt |
| Validation/settings | Pydantic 2 + Pydantic Settings | typed config і schemas |
| Templates | Jinja2 | SSR без SPA |
| ASGI server | Uvicorn | один worker для SQLite MVP |

У `pyproject.toml` залежності задаються сумісними діапазонами, а exact resolution фіксується у `uv.lock`. Непрямі залежності на кшталт Starlette не pin-яться вручну поза lock-файлом без окремої причини.

## 2. Ідентифікатори

- Internal primary keys: integer IDs.
- Public identifier ReleaseFile: UUIDv4.
- Session token: криптографічно випадковий token не менше 256 bits.
- У БД зберігається hash session token, не сам token.
- Public URL ніколи не використовує internal database ID або storage path як єдиний control доступу.

## 3. Сесії та login

| Параметр | Значення |
|---|---|
| Cookie name | `software_hub_session` |
| Cookie flags production | `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/admin` |
| Idle timeout | 30 хвилин |
| Absolute lifetime | 12 годин |
| Session rotation | обов’язково після успішного login |
| Failed attempts threshold | 5 |
| Lockout duration | 15 хвилин |
| Logout | revoke server-side session + delete cookie |
| Password change | revoke всі інші session; поточну можна залишити лише після повторної authentication policy |
| Password minimum | 14 символів |
| Password hash | Argon2id |

Login error для unknown username, wrong password, inactive user і lockout має однаковий публічний текст. Детальна причина доступна лише в safe audit metadata.

## 4. CSRF

- Session-bound synchronizer token pattern.
- Token передається лише в hidden form field або окремому header для майбутніх same-origin JS requests.
- Token не передається в URL.
- Перевірка виконується constant-time.
- Усі POST state-changing routes вимагають CSRF, включно з logout, upload, publish, disable, archive, backup і delete.

## 5. Upload policy

| Параметр | Значення |
|---|---|
| Default max upload | 2 GiB, configurable |
| Initial allowlist | `.exe`, `.msi`, `.zip`, `.7z` |
| Upload method | streaming chunks, без full-file read у RAM |
| Temporary storage | окрема `temporary` directory |
| Initial final status | `quarantine` |
| Duplicate check | SHA-256 indexed lookup |
| Browser MIME trust | не довіряти |
| Archive extraction | заборонено у MVP |
| Execution | завантажені файли ніколи не виконуються |
| Scanner | optional adapter; unavailable не ламає app |
| Unknown signature | лишити в quarantine для ручного рішення |

Nginx `client_max_body_size` і application `MAX_UPLOAD_SIZE` мають бути узгоджені. Application все одно перевіряє фактично отриману кількість bytes.

## 6. Storage layout

Production root:

```text
/srv/software-hub/
├── storage/
│   ├── software/
│   ├── icons/
│   ├── temporary/
│   ├── quarantine/
│   └── import/
├── database/
├── backups/
├── logs/
└── config/
```

- App отримує write лише до необхідних mounts.
- Nginx отримує read-only доступ до permanent software storage.
- Temporary і permanent storage повинні бути на одній filesystem, якщо atomic rename є обов’язковим.
- Якщо вони на різних filesystems, move implementation повинен явно виконати copy + fsync + atomic rename у цільовій directory і cleanup source.
- Storage files мають server-generated names.
- Original filename зберігається лише як metadata.

## 7. Download policy

- Endpoint: `/download/{public_uuid}/{safe_filename}`.
- FastAPI виконує authorization і повертає `X-Accel-Redirect`.
- Nginx location `/protected-downloads/` має `internal`.
- `HEAD` перевіряє доступність, але не збільшує статистику.
- `GET` збільшує counter після успішної перевірки доступу та наявності файла, перед internal redirect.
- Цей counter означає «авторизований початок завантаження».
- Disabled/private/invalid state для публічного клієнта повертає `404`.
- Missing physical file повертає `404` користувачу та створює operational error log.
- Range/resume обробляє Nginx.

## 8. SQLite policy

- Один application process/worker у production.
- `PRAGMA foreign_keys=ON` для кожного connection.
- WAL mode.
- `busy_timeout` початково 5000 ms, configurable.
- Короткі транзакції.
- Файловий streaming і hashing виконуються поза DB transaction.
- Safe backup — SQLite backup API або `.backup`, не простий copy активного файла.
- Partial unique index для одного current stable release дозволений як defense-in-depth, але business service все одно виконує атомарний transition.

## 9. Data retention

| Дані | Початкова політика |
|---|---|
| Expired sessions | cleanup щодня; зберігати не довше 7 днів після expiry для діагностики лише якщо безпечно |
| Temporary files | видаляти старші 24 годин, якщо не пов’язані з active operation |
| Audit logs | 180 днів, configurable |
| Application logs | rotation; 14–30 днів залежно від обсягу |
| Daily DB backups | 14 копій |
| Weekly full metadata/storage backups | 8 копій |
| Monthly offsite backups | 6 копій |
| Raw/full IP | не зберігати безстроково |

Retention не замінює offsite backup. Копія на тому самому диску не вважається disaster-recovery backup.

## 10. UI/content policy

- Початкова мова: українська.
- Рядки групуються так, щоб майбутня i18n не вимагала переписування templates.
- Full description і changelog у MVP — plain text.
- Jinja autoescape завжди ввімкнений.
- `|safe` для адміністративного контенту заборонений.
- Основні функції працюють без JavaScript.
- Inline scripts не використовуються, щоб спростити CSP.

## 11. Production admin access

Бажаний порядок:

1. WireGuard/VPN restriction на Nginx level;
2. IP allowlist, якщо IP стабільний;
3. публічний login лише як fallback із TLS, rate limit, lockout, CSRF, audit і сильним паролем.

Приховування посилання `/admin` не є security control.

## 12. Backup semantics

Backup set містить:

- consistent SQLite backup;
- software storage або посилання на окремий verified storage snapshot;
- icons;
- manifest;
- SHA-256 checksums;
- application version/git commit;
- schema revision;
- sanitized config template.

Restore за замовчуванням не запускається поверх активного production instance. Потрібні preflight, confirmation і maintenance/offline mode.

## 13. Versioning та releases

- Semantic Versioning для application releases.
- Початковий production release: `v1.0.0`.
- `CHANGELOG.md` у форматі Keep a Changelog-подібної структури.
- Release створюється лише з green CI, migration rehearsal, backup/restore verification і completed checklist.

## 14. Рішення, які відкладаються

Не фіксуються до появи реальної потреби:

- PostgreSQL migration date;
- CDN provider;
- S3-compatible storage;
- public API format;
- multi-user roles;
- malware scanner implementation за замовчуванням;
- Markdown support;
- background job system.
