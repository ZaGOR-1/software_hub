# Software Hub — межі MVP

**Статус:** затверджено
**Дата:** 2026-07-23
**Основний домен:** `https://software.hotzagor.tech`

## 1. Мета продукту

Software Hub — персональний вебкаталог програм та інсталяційних файлів із публічним SSR-інтерфейсом, захищеною адміністративною панеллю, локальним файловим сховищем та прямою видачею великих файлів через Nginx.

Проєкт реалізується як production-ready MVP, який одна людина може розгортати, підтримувати, резервувати та відновлювати без мікросервісної інфраструктури.

## 2. Основні користувачі

### Публічний відвідувач

Може:

- переглядати головну сторінку й каталог;
- шукати програми;
- фільтрувати за категоріями та тегами;
- відкривати сторінку програми;
- переглядати поточну версію та історію релізів;
- вибирати файл за платформою, архітектурою й типом пакета;
- переглядати SHA-256, ліцензію, розробника та джерело;
- завантажувати дозволені опубліковані файли.

### Адміністратор

Може:

- входити до `/admin` без відкритої реєстрації;
- керувати категоріями й тегами;
- створювати, редагувати, публікувати, приховувати й архівувати програми;
- створювати релізи та призначати поточний stable-реліз;
- потоково завантажувати файли;
- переглядати результати перевірки файла;
- публікувати, вимикати, архівувати та остаточно видаляти файли через окремі дії;
- переглядати статистику, audit log, стан БД, сховища й резервних копій;
- запускати backup і maintenance-команди.

## 3. Обов’язковий scope MVP

### Публічна частина

- головна сторінка;
- каталог;
- пошук;
- категорії й теги;
- сортування й pagination;
- сторінка програми;
- історія релізів;
- кілька файлів на один реліз;
- пряме завантаження через Nginx `X-Accel-Redirect`;
- SHA-256 та trust metadata;
- статистика завантажень;
- responsive UI;
- світла, темна та системна тема;
- базове SEO й accessibility.

### Адміністративна частина

- один або кілька вручну створених адміністраторів;
- Argon2id;
- server-side sessions;
- CSRF для всіх state-changing форм;
- login rate limiting і тимчасове блокування;
- dashboard;
- CRUD Category, Tag, Software, Release;
- streaming upload ReleaseFile;
- allowlist розширень;
- magic-byte validation;
- SHA-256;
- quarantine;
- optional malware scanner interface;
- publish, disable, archive, metadata delete та permanent file delete як різні операції;
- audit log.

### Інфраструктура й операції

- FastAPI + Jinja2 modular monolith;
- SQLAlchemy 2.x + Alembic;
- SQLite із foreign keys, WAL і busy timeout;
- Docker Compose;
- Nginx;
- HTTPS deployment documentation;
- filesystem storage поза application container і web-root;
- backup, restore і checksum manifest;
- reconciliation/verify-storage commands;
- Ruff, mypy, pytest, pytest-cov, pre-commit;
- GitHub Actions;
- dependency та container security scans;
- повний набір deployment, security та operations документації.

## 4. Out of scope для MVP

Без окремого ADR та зміни roadmap не реалізовуються:

- відкрита реєстрація;
- social login;
- відновлення пароля через email;
- публічний REST API;
- desktop/package-manager client;
- автоматичні оновлення програм;
- GitHub Releases sync;
- скачування файлів із довільних URL сервером;
- автоматичний запуск EXE/MSI;
- розпакування архівів;
- коментарі, рейтинги, форуми;
- платежі й підписки;
- Telegram bot та email notifications;
- Redis, Celery, RabbitMQ, Kafka;
- Elasticsearch;
- PostgreSQL у першому релізі;
- S3/object storage/CDN;
- Kubernetes;
- multi-region і multi-tenant;
- складна RBAC;
- більше одного application instance;
- автоматичний production deploy.

## 5. Зафіксовані product rules

- `draft` не відображається публічно;
- `public` відображається в каталозі;
- `unlisted` доступне за прямим URL, але не з’являється в каталозі;
- `private` доступне лише адміністратору;
- `disabled` повертає зовнішньому користувачу `404`, щоб не розкривати стан ресурсу;
- `archived` може залишатися в історії, але не рекомендується як поточна версія;
- release не може бути current, поки не published;
- для однієї програми одночасно існує не більше одного current stable release;
- quarantine/rejected/disabled file ніколи не віддається публічно;
- фізичний шлях не входить до public URL і не приймається від клієнта;
- `HEAD` не збільшує download counter;
- у MVP download рахується як авторизований початок `GET`, а не гарантоване завершення передачі;
- опис програм зберігається як plain text; довільний HTML і Markdown не підтримуються у v1;
- повні IP-адреси не зберігаються безстроково.

## 6. Definition of MVP success

MVP готовий, коли адміністратор може на чистому сервері:

1. запустити систему через Docker Compose;
2. застосувати міграції;
3. створити admin без default password;
4. увійти до admin panel;
5. створити категорію, програму та реліз;
6. завантажити файл, який потрапить у quarantine;
7. перевірити metadata й опублікувати файл;
8. відкрити публічну сторінку;
9. завантажити файл через Nginx internal location;
10. вимкнути файл і переконатися, що він недоступний;
11. створити backup;
12. відновити backup у чистому тестовому середовищі;
13. пройти security, unit, integration та E2E перевірки.

## 7. Правило зміни scope

Будь-яка нова велика функція спочатку оформлюється як:

1. опис проблеми;
2. вплив на security, data model, deployment та operations;
3. ADR;
4. окрема фаза roadmap;
5. оновлення acceptance criteria.

Додавання функції «по ходу» без цих кроків не допускається.
