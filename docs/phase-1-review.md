# Software Hub — звіт про Фазу 1

**Фаза:** Bootstrap репозиторію та якість коду  
**Версія застосунку:** `0.1.0`  
**Target runtime:** Python `>=3.14,<3.15`

## Реалізовано

- створено Python package `app`;
- реалізовано application factory `create_app`;
- реалізовано typed bootstrap settings;
- додано `GET /health`;
- створено unit tests для health, settings і application factory;
- налаштовано pytest, branch coverage і threshold 90%;
- налаштовано Ruff;
- налаштовано strict mypy;
- налаштовано Bandit і pip-audit;
- створено pre-commit конфігурацію;
- створено початковий GitHub Actions CI;
- створено `.env.example`, `.gitignore`, `.dockerignore` і root README.

## Навмисно не реалізовано

Відповідно до меж Фази 1 не створювалися:

- SQLAlchemy models і Alembic;
- production secret validation;
- auth, sessions і CSRF;
- HTML templates;
- storage/upload/download;
- Dockerfile, Compose і Nginx.

## Локальна перевірка в робочому середовищі

Доступний runner має Python 3.13.5 і встановлені runtime/test packages, але не має
мережевого доступу для завантаження Python 3.14 та окремих dev-інструментів.
Локально виконані:

- pytest;
- branch coverage;
- `compileall`;
- import smoke test;
- реальний Uvicorn smoke test;
- TOML/YAML parsing;
- Git whitespace check;
- структурна перевірка `uv.lock`.

`uv.lock` додано до репозиторію. Повний `uv sync --all-groups --locked` і запуск
Ruff, mypy, Bandit та pip-audit мають бути повторені на network-enabled Python
3.14 runner. GitHub Actions уже налаштований саме на такий frozen workflow.

## Відоме обмеження середовища

Неможливо локально завантажити CPython 3.14 і package artifacts. Це обмеження
поточного sandbox, а не application code. Першою перевіркою після розміщення у
GitHub має бути green CI на Python 3.14.


## Результати перевірок

```text
pytest: 7 passed
coverage: 100% statements and branches
compileall: passed
FastAPI import smoke: passed
Uvicorn /health smoke: passed
pyproject.toml parse: passed
GitHub Actions YAML parse: passed
pre-commit YAML parse: passed
uv.lock TOML/reference graph: passed
Git whitespace check: passed
```

Lock-файл містить 41 package record після видалення записів, які не входять до
runtime/dev dependency graph Software Hub.
