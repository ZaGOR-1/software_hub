# Software Hub — звіт про Фазу 2

**Фаза:** Конфігурація, application core, logging і error handling  
**Версія застосунку:** `0.1.0`  
**Target runtime:** Python `>=3.14,<3.15`

## Мета фази

Створити єдиний контрольований application core до появи SQLAlchemy, auth,
admin CRUD та файлової бізнес-логіки. Усі подальші модулі повинні використовувати
централізовану конфігурацію, request context, logging і typed exceptions.

## Реалізовано

### Typed settings і fail-fast validation

`app/core/config.py` тепер перевіряє:

- execution environment;
- production debug prohibition;
- наявність двох окремих production secrets;
- мінімальну довжину й базову непередбачуваність secrets;
- HTTPS для production public URL;
- trusted-host allowlist;
- заборону wildcard host у production;
- наявність public host у trusted hosts;
- абсолютність storage, temporary, quarantine, icons і backup paths;
- bounded upload size;
- normalization і allowlist syntax для extensions;
- CIDR syntax для trusted proxy networks;
- request-ID header syntax;
- захист від CRLF injection у CSP.

Comma-separated environment values нормалізуються й дедуплікуються.

### Request correlation

- кожен HTTP request отримує request ID;
- валідний вхідний `X-Request-ID` зберігається;
- невалідний або надто довгий ID замінюється UUID4 hex;
- request ID зберігається у `scope.state` та `ContextVar`;
- response завжди містить request-ID header, включно з 4xx і 500.

### Structured logging

- JSON lines за замовчуванням;
- UTC timestamp;
- level, logger, event і request ID;
- bounded request metadata;
- recursive redaction ключів, пов’язаних із password, cookie, session,
  authorization, token, secret і CSRF;
- request middleware не читає і не логує body;
- Uvicorn access logger знижений до `WARNING`, щоб уникати дублювання.

### Trusted host і proxy policy

- Starlette TrustedHostMiddleware працює з явним allowlist;
- forwarding headers видаляються для peer, який не належить trusted CIDR;
- довіра до proxy фіксується в request state;
- документація прямо вимагає узгодити application allowlist із параметрами
  Uvicorn `--forwarded-allow-ips`.

### Security headers

Application middleware додає:

- `X-Content-Type-Options: nosniff`;
- `Referrer-Policy`;
- `Permissions-Policy`;
- `X-Frame-Options: DENY` як compatibility fallback;
- Content Security Policy із `frame-ancestors 'none'`.

CSP навмисно не додається на development OpenAPI/Swagger endpoints, оскільки
їхній frontend використовує ресурси, несумісні з production CSP. У production
docs можуть бути повністю вимкнені. HSTS буде налаштований у Nginx після
перевіреного HTTPS у Фазі 17.

### Typed exceptions і safe error handling

Створено базовий `ApplicationError` і спеціалізовані exceptions:

- `EntityNotFound`;
- `PermissionDenied`;
- `InvalidStateTransition`;
- `FileValidationError`;
- `StorageError`;
- `DuplicateFileError`;
- `AuthenticationError`;
- `CSRFError`;
- `RateLimitError`.

Централізовані handlers підтримують JSON та HTML для:

- 400;
- 401;
- 403;
- 404;
- 409;
- 413;
- 422;
- 429;
- 500;
- 503.

Validation handler не повертає submitted input. Unexpected exception handler
повертає лише generic 500 response і request ID. Stack trace залишається лише у
server log та не потрапляє у HTTP response.

### UTC helpers

- `utc_now()` повертає timezone-aware UTC datetime;
- `ensure_utc()` конвертує aware datetime;
- naive datetime відхиляється.

## Створені або суттєво змінені файли

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
app/main.py
app/templates/errors/base.html
app/templates/errors/{400,401,403,404,409,413,422,429,500,503}.html
tests/unit/core/*
tests/integration/test_error_handling.py
.env.example
README.md
pyproject.toml
docs/README.md
docs/phase-2-review.md
```

## Перевірки

Локально виконано:

```text
python -m compileall -q app tests
python -m pytest -q
Git whitespace validation
pyproject.toml parsing
application import smoke
real Uvicorn /health smoke
production settings smoke
```

Результат pytest:

```text
62 passed
97.95% total branch-aware coverage
90% threshold passed
```

Security-критичні тести перевіряють:

- missing/weak/equal production secrets;
- production debug;
- HTTP production URL;
- wildcard і invalid hosts;
- relative paths;
- invalid extensions і proxy networks;
- request-ID propagation та replacement;
- JSON/HTML error mappings;
- validation input non-disclosure;
- production 500 non-disclosure;
- security headers;
- invalid Host rejection;
- forwarded-header stripping;
- trusted-proxy pass-through;
- structured redaction;
- absence of Authorization/Cookie values у request logs.

## Обмеження робочого середовища

Поточний runner має Python 3.13.5. Спроба отримати Ruff через `uvx` завершилася
HTTP 503 від внутрішнього package registry. `uv run --offline` також не може
запустити target Python 3.14, оскільки interpreter не встановлений.

Через це локально не підтверджені виконання:

- Ruff format check;
- Ruff lint;
- strict mypy;
- Bandit;
- pip-audit;
- frozen sync під Python 3.14.

Конфігурації цих інструментів збережені, а GitHub Actions виконує повний quality
gate на Python 3.14. Жоден із цих результатів не позначено як пройдений локально.

## Навмисно не реалізовано

Відповідно до меж Фази 2 не додано:

- SQLAlchemy engine, sessions або models;
- Alembic;
- database health probe;
- auth/session tables і login flow;
- CSRF business implementation;
- admin/public UI;
- storage startup directory creation;
- upload/download logic;
- Nginx і Docker runtime.

## Відомі ризики та наступні дії

1. **Proxy trust має два рівні.** App stripping не замінює правильний Uvicorn
   allowlist. Це буде зафіксовано у production command/Compose.
2. **CSP дублюватиметься з Nginx.** У Фазі 17 Nginx стане джерелом production
   security headers; application defaults залишаться defense in depth.
3. **Logging policy залежить від дисципліни.** Services повинні передавати лише
   safe structured metadata й ніколи не вставляти secrets у message string.
4. **Error templates поки мінімальні.** Повний дизайн з’явиться у UI-фазі без
   зміни error contract.

## Definition of Done

```text
[x] typed settings реалізовані
[x] production config fail-fast
[x] weak secrets відхиляються
[x] absolute paths перевіряються
[x] trusted hosts перевіряються
[x] typed application exceptions створені
[x] JSON і HTML error handlers створені
[x] request ID реалізований
[x] structured logging реалізований
[x] sensitive structured fields редагуються
[x] request logging не читає body/headers
[x] trusted host middleware підключений
[x] untrusted forwarding headers видаляються
[x] UTC helpers створені
[x] baseline security headers підключені
[x] production responses не містять traceback
[x] tests і coverage проходять
[x] документація й .env.example оновлені
[ ] Ruff/mypy/Bandit/pip-audit локально — blocked package registry
[ ] Python 3.14 frozen sync локально — interpreter unavailable
```

Функціональний scope Фази 2 завершено. Наступна фаза — database foundation та
Alembic — може використовувати цей core без дублювання конфігурації, logging або
error mapping.
