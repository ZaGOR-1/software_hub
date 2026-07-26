# Фаза 0 — Review та критерії завершення

**Дата виконання:** 2026-07-23  
**Статус:** complete, pending user acceptance

## Створені артефакти

- `docs/project-scope.md` — MVP та out-of-scope;
- `docs/technical-decisions.md` — конкретні policy values;
- `docs/ADR/0001-modular-monolith.md`;
- `docs/ADR/0002-sqlite-for-mvp.md`;
- `docs/ADR/0003-server-side-sessions.md`;
- `docs/ADR/0004-x-accel-redirect.md`;
- `docs/ADR/0005-upload-quarantine.md`;
- `docs/threat-model.md`;
- `docs/release-checklist.md`;
- `docs/reference/master-prompt.md`;
- `docs/reference/implementation-plan.md`.

## Зафіксовані ключові рішення

- Python `>=3.14,<3.15`;
- `uv` та committed `uv.lock`;
- modular monolith;
- SQLite/WAL/foreign keys/busy timeout;
- один Uvicorn worker;
- integer internal IDs і UUIDv4 для public file IDs;
- server-side session token із hash у БД;
- idle timeout 30 хв, absolute 12 год;
- 5 failed logins → lockout 15 хв;
- CSRF для всіх state-changing forms;
- upload limit 2 GiB configurable;
- `.exe`, `.msi`, `.zip`, `.7z` allowlist;
- streaming upload → quarantine → manual publish;
- optional malware scanner;
- `X-Accel-Redirect` для downloads;
- disabled/private invalid public access → 404;
- GET counter означає authorized download start; HEAD не рахується;
- plain-text content у MVP;
- no raw long-term IP storage;
- production admin бажано через WireGuard/IP allowlist;
- safe SQLite backup + tested restore;
- separate archive/disable/delete/permanent-delete semantics.

## Перевірка критеріїв Фази 0

- [x] MVP scope зафіксовано.
- [x] Out-of-scope зафіксовано.
- [x] Архітектурні ADR створено.
- [x] Package manager і Python version визначено.
- [x] Session, upload, retention і download policies визначено.
- [x] Threat model створено.
- [x] Release checklist створено.
- [x] Master prompt і implementation plan збережено як repository references.
- [x] Код application/business logic не створювався.
- [x] Фаза не переходить до Phase 1 автоматично.

## Відомі residual risks

- optional scanner не гарантує malware detection;
- один admin із valid credentials може навмисно publish небезпечний файл;
- download counter не підтверджує завершення transfer;
- root compromise host виходить за межі application controls;
- volumetric DDoS потребуватиме upstream protection;
- backup encryption залежатиме від production storage/offsite implementation.

## Наступна фаза

Фаза 1 може починатися окремою командою. Вона повинна створити лише repository/application bootstrap, quality tooling, basic `/health` і CI, не переходячи до database models, auth або upload.
