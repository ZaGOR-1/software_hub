# MASTER PROMPT: РОЗРОБКА SOFTWARE HUB

Ти — senior full-stack розробник, software architect, DevOps-інженер і спеціаліст із безпеки вебзастосунків.

Твоє завдання — спроєктувати та реалізувати production-ready MVP вебзастосунку **Software Hub**: особистого каталогу програм та інсталяційних файлів із публічним вебінтерфейсом, захищеною адміністративною панеллю та прямим завантаженням файлів із власного сервера.

Проєкт має бути достатньо простим для підтримки однією людиною, але водночас мати чисту архітектуру, безпечну реалізацію, автоматизоване розгортання, тестування, резервне копіювання та можливість подальшого розвитку.

Основний production-домен:

```text
https://software.hotzagor.tech
```

Цільове середовище розгортання:

* VPS на Ubuntu Server;
* або окрема Ubuntu Server VM у Proxmox;
* Docker Compose;
* Nginx;
* HTTPS через Let’s Encrypt.

---

# 1. ГОЛОВНА ІДЕЯ ПРОЄКТУ

Software Hub — це персональний вебкаталог корисних програм, власних утиліт та інсталяційних файлів.

Адміністратор через захищену адміністративну панель повинен мати можливість:

* додавати програми;
* створювати релізи та версії;
* завантажувати файли;
* додавати EXE, MSI, ZIP та інші дозволені типи файлів;
* вказувати архітектуру та тип збірки;
* додавати іконки, опис, категорії й теги;
* публікувати або приховувати програми;
* архівувати старі версії;
* переглядати статистику завантажень;
* керувати каталогом без ручного редагування HTML або бази даних.

Звичайний відвідувач повинен мати можливість:

* відкрити сайт;
* знайти потрібну програму;
* переглянути її опис;
* побачити актуальну версію;
* вибрати потрібний інсталяційний файл;
* натиснути кнопку завантаження;
* отримати файл безпосередньо із сервера.

Приклад користувацького сценарію:

```text
Користувач відкриває software.hotzagor.tech
→ знаходить 7-Zip
→ відкриває сторінку програми
→ обирає Windows x64 Installer
→ натискає «Завантажити»
→ файл одразу завантажується через Nginx
```

---

# 2. РЕЖИМ РОБОТИ ШТУЧНОГО ІНТЕЛЕКТУ

Перед написанням коду:

1. Уважно проаналізуй усі вимоги цього документа.
2. Не змінюй самовільно затверджений технологічний стек.
3. Не додавай зайві технології без реальної необхідності.
4. Не починай реалізацію одразу.
5. Спочатку сформуй детальний пофазний план реалізації.
6. Для кожної фази вкажи:

   * мету;
   * перелік завдань;
   * файли та модулі, які потрібно створити;
   * залежності від попередніх фаз;
   * критерії завершення;
   * тести;
   * ризики;
   * результат фази.
7. Після затвердження плану реалізовуй проєкт послідовно, фаза за фазою.
8. Не створюй заглушки замість реальної логіки без явного позначення.
9. Не залишай критичні місця з `TODO`, якщо вони входять до поточної фази.
10. Після кожної фази:

    * запускай тести;
    * запускай lint і type checking;
    * перевіряй міграції;
    * оновлюй документацію;
    * повідомляй про знайдені обмеження або ризики.

Під час реалізації дотримуйся принципу:

```text
простота → безпека → надійність → підтримуваність → розширюваність
```

Не застосовуй overengineering.

---

# 3. ЗАТВЕРДЖЕНИЙ ТЕХНОЛОГІЧНИЙ СТЕК

## Backend

* Python;
* FastAPI;
* SQLAlchemy 2.x;
* Alembic;
* Pydantic;
* Uvicorn;
* Jinja2.

Використовуй актуальні стабільні версії бібліотек на момент реалізації.

## Frontend

* server-side rendering через Jinja2;
* семантичний HTML5;
* CSS;
* Vanilla JavaScript;
* без React;
* без Vue;
* без Angular;
* без окремого SPA;
* без обов’язкового Node.js build pipeline.

JavaScript використовуй лише там, де він реально потрібний:

* підтвердження небезпечних дій;
* попередній перегляд іконки;
* індикація завантаження файла;
* динамічні форми;
* перемикання теми;
* невеликі інтерактивні елементи.

Основний функціонал має залишатися доступним без складної клієнтської логіки.

## Database

Для MVP:

* SQLite;
* SQLAlchemy ORM;
* Alembic migrations.

Обов’язково налаштувати:

* foreign keys;
* WAL mode;
* `busy_timeout`;
* короткі транзакції;
* коректне управління SQLAlchemy sessions;
* безпечний backup живої бази через SQLite backup API або еквівалентний надійний механізм.

Не зберігати великі файли в SQLite.

Архітектура повинна дозволяти в майбутньому перейти на PostgreSQL без повного переписування бізнес-логіки.

## Web server

* Nginx;
* reverse proxy до FastAPI;
* видача статичних ресурсів;
* безпосередня видача великих файлів;
* підтримка `X-Accel-Redirect`;
* HTTPS;
* security headers;
* rate limiting;
* обмеження розміру HTTP-запитів.

## Deployment

* Docker;
* Docker Compose;
* Linux;
* Ubuntu Server;
* окремі persistent volumes або bind mounts для:

  * бази;
  * програм;
  * іконок;
  * логів;
  * резервних копій;
  * конфігурації.

## Якість коду

* `pyproject.toml`;
* lock-файл залежностей;
* Ruff;
* mypy;
* pytest;
* pytest-cov;
* pre-commit;
* CI через GitHub Actions;
* pip-audit або еквівалентна перевірка залежностей;
* Bandit або еквівалентний статичний security analysis;
* Trivy для перевірки Docker-образів.

---

# 4. АРХІТЕКТУРНИЙ ПІДХІД

Реалізуй проєкт як **модульний моноліт**.

Не використовуй:

* мікросервіси;
* Kubernetes;
* RabbitMQ;
* Kafka;
* Celery;
* Redis;
* Elasticsearch;
* окремий API Gateway;
* складний event-driven підхід;
* надмірне DDD;
* зайві абстракції заради абстракцій.

Для MVP ці технології не потрібні.

Рекомендований поділ відповідальності:

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

HTTP-роутери не повинні містити всю бізнес-логіку.

## Рекомендована структура

```text
software-hub/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   ├── security.py
│   │   ├── csrf.py
│   │   ├── exceptions.py
│   │   ├── logging.py
│   │   └── middleware.py
│   ├── database/
│   │   ├── base.py
│   │   ├── session.py
│   │   └── migrations_helpers.py
│   ├── models/
│   ├── schemas/
│   ├── repositories/
│   ├── services/
│   │   ├── software_service.py
│   │   ├── release_service.py
│   │   ├── file_service.py
│   │   ├── download_service.py
│   │   ├── auth_service.py
│   │   ├── audit_service.py
│   │   └── backup_service.py
│   ├── routers/
│   │   ├── public/
│   │   ├── admin/
│   │   ├── auth/
│   │   └── health/
│   ├── storage/
│   │   ├── paths.py
│   │   ├── validation.py
│   │   ├── hashing.py
│   │   ├── upload.py
│   │   └── cleanup.py
│   ├── templates/
│   │   ├── public/
│   │   ├── admin/
│   │   ├── auth/
│   │   ├── errors/
│   │   └── components/
│   └── static/
│       ├── css/
│       ├── js/
│       ├── images/
│       └── icons/
├── alembic/
├── scripts/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── security/
│   └── e2e/
├── nginx/
├── docker/
├── docs/
├── backups/
├── docker-compose.yml
├── docker-compose.production.yml
├── Dockerfile
├── pyproject.toml
├── .env.example
├── .gitignore
├── README.md
├── SECURITY.md
├── DEPLOYMENT.md
├── BACKUP_RESTORE.md
└── CHANGELOG.md
```

Структуру можна незначно адаптувати, але розподіл відповідальності має залишатися чітким.

---

# 5. ОСНОВНА МОДЕЛЬ ДАНИХ

Основний зв’язок:

```text
Software
└── Release
    └── ReleaseFile
```

Одна програма може мати багато релізів.

Один реліз може мати багато файлів:

* x64 installer;
* x86 installer;
* ARM64 installer;
* portable ZIP;
* MSI;
* окрема редакція.

Не об’єднуй програму, реліз і файл в одну таблицю.

## 5.1. User

Для MVP існує тільки один або кілька вручну створених адміністраторів.

Не реалізовувати відкриту реєстрацію.

Поля:

* UUID або integer ID;
* username;
* password hash;
* is_active;
* is_superuser або роль адміністратора;
* failed_login_attempts;
* locked_until;
* password_changed_at;
* last_login_at;
* created_at;
* updated_at.

Вимоги:

* username має бути унікальним;
* пароль ніколи не зберігається у відкритому вигляді;
* використовувати Argon2id;
* адміністратор створюється через CLI-команду або bootstrap script;
* у проєкті не повинно бути стандартного production-пароля.

## 5.2. Session

Реалізувати серверні сесії.

Поля:

* випадковий session ID або його хеш;
* user_id;
* created_at;
* last_activity_at;
* expires_at;
* absolute_expires_at;
* revoked_at;
* metadata для безпечного аудиту.

Не зберігати секретну інформацію в cookie.

Cookie містить лише непередбачуваний ідентифікатор сесії.

## 5.3. Category

Поля:

* id;
* name;
* slug;
* description;
* sort_order;
* is_visible;
* created_at;
* updated_at.

Slug має бути унікальним.

## 5.4. Tag

Поля:

* id;
* name;
* slug;
* created_at.

Між Software і Tag — many-to-many relationship.

## 5.5. Software

Поля:

* UUID або integer ID;
* name;
* slug;
* short_description;
* full_description;
* developer_name;
* official_website_url;
* source_url;
* license_name;
* category_id;
* icon_path або icon identifier;
* supported_os;
* system_requirements;
* status;
* visibility;
* is_featured;
* created_at;
* updated_at;
* published_at;
* archived_at.

Рекомендовані статуси:

```text
draft
published
hidden
archived
disabled
```

Рекомендована видимість:

```text
public
unlisted
private
```

Значення:

* `public` — відображається у каталозі;
* `unlisted` — не відображається у каталозі, але доступне за прямим URL;
* `private` — доступне лише адміністратору після авторизації.

Slug повинен бути унікальним.

Опис має безпечно відображатися без можливості XSS.

Для MVP бажано використовувати plain text або контрольований Markdown із жорсткою sanitization.

## 5.6. Release

Поля:

* id;
* software_id;
* version;
* release_channel;
* release_date;
* changelog;
* is_current;
* status;
* created_at;
* updated_at;
* published_at.

Release channel:

```text
stable
beta
alpha
nightly
legacy
```

Для одного програмного продукту може бути лише один поточний stable-реліз, якщо бізнес-логіка не дозволяє інше.

## 5.7. ReleaseFile

Поля:

* UUID як публічний ідентифікатор;
* release_id;
* original_filename;
* display_filename;
* storage_filename;
* relative_storage_path;
* file_extension;
* detected_mime_type;
* file_size_bytes;
* sha256;
* architecture;
* package_type;
* platform;
* edition;
* download_count;
* status;
* visibility;
* uploaded_at;
* published_at;
* disabled_at;
* source_url;
* signature_status;
* admin_note.

Architecture:

```text
x64
x86
arm64
universal
other
```

Package type:

```text
installer
portable
archive
msi
other
```

File status:

```text
quarantine
ready
published
disabled
archived
rejected
```

SHA-256 має бути проіндексований для пошуку дублікатів.

Реальний storage path ніколи не повинен надходити від користувача напряму.

## 5.8. DownloadEvent або агрегована статистика

Для MVP можна реалізувати:

* загальний download_count у ReleaseFile;
* добову агреговану статистику;
* окрему таблицю DownloadStat за датою.

Не зберігати безстроково повні IP-адреси відвідувачів.

Для rate limiting або антизловживань можна:

* тимчасово використовувати IP;
* або зберігати його хеш із ротаційною salt;
* застосовувати короткий retention period.

Поля агрегованої статистики:

* release_file_id;
* date;
* download_count;
* successful_download_count;
* blocked_download_count.

## 5.9. AuditLog

Логувати адміністративні дії.

Поля:

* id;
* user_id;
* action;
* entity_type;
* entity_id;
* result;
* timestamp;
* safe_metadata;
* request_id;
* hashed_or_truncated_ip.

Приклади:

```text
admin_login_success
admin_login_failed
software_created
software_updated
release_created
file_uploaded
file_published
file_disabled
file_deleted
settings_changed
backup_created
```

Не записувати в audit log:

* пароль;
* session cookie;
* CSRF token;
* секретні ключі;
* повний Authorization header.

---

# 6. ФАЙЛОВЕ СХОВИЩЕ

Файли програм повинні зберігатися поза application container і поза публічним web-root.

Рекомендована структура:

```text
/srv/software-hub/
├── storage/
│   ├── software/
│   ├── icons/
│   ├── import/
│   ├── temporary/
│   └── quarantine/
├── database/
├── backups/
├── logs/
└── config/
```

Приклад:

```text
/srv/software-hub/storage/software/
└── 7zip/
    └── 26.00/
        ├── 5b7f...a2.exe
        └── d849...f1.exe
```

На диску використовувати безпечне внутрішнє ім’я:

* UUID;
* content hash;
* або інший серверний identifier.

Оригінальне ім’я зберігається лише як metadata.

Заборонено використовувати оригінальне ім’я користувацького файла як абсолютний або відносний шлях без нормалізації.

---

# 7. БЕЗПЕЧНИЙ UPLOAD PIPELINE

Завантаження файла має відбуватися потоково, без зчитування всього файла в RAM.

Послідовність:

```text
HTTP upload
→ перевірка авторизації
→ перевірка CSRF
→ перевірка Content-Length
→ streaming у temporary directory
→ контроль фактичного розміру
→ нормалізація оригінального імені
→ перевірка розширення
→ визначення типу за magic bytes
→ SHA-256
→ перевірка дубліката
→ переміщення в quarantine
→ optional malware scan
→ створення запису в базі
→ ручна або автоматична публікація
→ atomic move у permanent storage
```

## Обов’язкові правила

* allowlist розширень;
* configurable max upload size;
* server-generated storage name;
* заборона path traversal;
* заборона null bytes;
* захист від подвійних розширень;
* перевірка Unicode-імен;
* контроль вільного місця;
* безпечне видалення тимчасового файла при помилці;
* atomic move;
* унікальний storage path;
* заборона виконання файлів на сервері;
* storage directory не повинен бути executable;
* застосунок не повинен запускати завантажені EXE або MSI;
* файли не повинні бути імпортовані як Python-модулі;
* archive-файли не розпаковувати в MVP.

Дозволені формати мають задаватися конфігурацією.

Початковий allowlist:

```text
.exe
.msi
.zip
.7z
```

Перевірка не повинна покладатися лише на MIME type, який надіслав браузер.

Перевіряти:

* extension;
* normalized filename;
* detected type;
* magic bytes;
* розмір.

EXE-файл може визначатися як Windows PE binary.

MSI може визначатися як Compound File Binary.

ZIP і 7z повинні мати відповідні сигнатури.

Якщо тип не вдалося впевнено визначити, файл залишається в quarantine до ручного рішення адміністратора.

## Антивірус

ClamAV або інший локальний scanner зробити опціональним.

Не робити його жорсткою залежністю базового MVP, особливо для VPS із малою кількістю RAM.

Передбачити інтерфейс scanner service:

```text
scan(file_path) → clean / infected / error / unavailable
```

Відсутність антивіруса не повинна ламати застосунок.

Файл із результатом `infected` не можна публікувати.

---

# 8. ЗАВАНТАЖЕННЯ ФАЙЛІВ КОРИСТУВАЧАМИ

Великі файли не повинні передаватися через Python response body.

Правильний процес:

```text
Користувач
→ GET /download/{public_file_id}/{filename}
→ FastAPI перевіряє запис у базі
→ перевіряє статус
→ перевіряє visibility
→ реєструє download event
→ повертає X-Accel-Redirect
→ Nginx віддає файл
```

Внутрішній Nginx location:

```text
/protected-downloads/
```

Він має бути позначений як `internal`.

Користувач не повинен мати прямого доступу до storage directory.

Зовнішній URL може виглядати так:

```text
https://software.hotzagor.tech/download/550e8400-e29b-41d4-a716-446655440000/7zip-x64.exe
```

Реальний шлях може виглядати так:

```text
/srv/software-hub/storage/software/7zip/26.00/5b7f...a2.exe
```

FastAPI ніколи не повинен приймати від користувача довільний файловий шлях.

## Вимоги до download response

* правильний `Content-Disposition`;
* безпечне ім’я файла;
* правильний MIME type;
* підтримка HEAD requests;
* підтримка resume/range через Nginx;
* коректний `Content-Length`;
* можливість відключити конкретний файл;
* відсутність directory listing;
* можливість rate limiting;
* логування успішних і заблокованих спроб.

Download count не повинен збільшуватися для:

* неавторизованого private-файла;
* disabled-файла;
* відсутнього файла;
* HEAD-запиту;
* заблокованого запиту.

Продумай, у який момент вважати download успішним. Для MVP допустимо рахувати авторизований початок завантаження, але це потрібно чітко задокументувати.

---

# 9. АВТОРИЗАЦІЯ ТА СЕСІЇ

Для MVP не використовувати JWT у localStorage.

Використовувати серверні сесії.

## Cookie

Cookie повинна мати:

* `HttpOnly`;
* `Secure`;
* `SameSite=Lax` або суворіше;
* чітко визначений Path;
* обмежений строк життя.

На login:

* створити нову сесію;
* регенерувати session ID;
* не перевикористовувати стару anonymous session.

На logout:

* відкликати server-side session;
* видалити cookie.

На зміну пароля:

* відкликати інші активні сесії;
* бажано відкликати всі сесії, крім поточної, або всі без винятку.

## Тайм-аути

Передбачити:

* inactivity timeout;
* absolute session lifetime;
* ручне відкликання;
* очищення прострочених сесій.

## Password security

* Argon2id;
* сильні параметри хешування;
* мінімальна довжина пароля;
* заборона стандартного пароля;
* constant-time comparison;
* не логувати пароль;
* не повертати різні повідомлення для неіснуючого користувача й неправильного пароля.

Приклад безпечного повідомлення:

```text
Невірний логін або пароль.
```

## Brute-force protection

Реалізувати:

* Nginx rate limit для login endpoint;
* app-level failed login counter;
* тимчасове блокування;
* audit log;
* безпечне повідомлення без витоку існування username.

Redis для цього в MVP не використовувати.

---

# 10. CSRF, XSS, SQL INJECTION ТА ІНШІ ЗАГРОЗИ

## CSRF

Усі state-changing операції повинні використовувати CSRF-захист:

* POST;
* PUT;
* PATCH;
* DELETE.

CSRF token має бути:

* прив’язаний до сесії;
* криптографічно надійний;
* перевірений сервером;
* присутній у формах;
* не передаватися у URL.

## XSS

* Jinja autoescape має бути увімкнений;
* не використовувати `|safe` для користувацького контенту без sanitization;
* заборонити довільний HTML в описах для MVP;
* усі URL валідовувати;
* JavaScript не повинен вставляти неперевірені дані через `innerHTML`;
* реалізувати Content Security Policy.

## SQL injection

* тільки SQLAlchemy ORM або параметризовані queries;
* не будувати SQL через конкатенацію рядків;
* search input валідовувати;
* pagination параметри обмежувати.

## Path traversal

* не приймати absolute path від користувача;
* після побудови шляху перевіряти, що resolved path залишається всередині storage root;
* заборонити `..`;
* заборонити null bytes;
* публічний ID файла брати з бази.

## IDOR

Адміністративні дії мають перевіряти:

* авторизацію;
* статус користувача;
* право доступу;
* існування об’єкта;
* допустимість переходу статусу.

Недостатньо приховати кнопку в HTML.

## SSRF

Поля `official_website_url` і `source_url` не повинні автоматично завантажувати зовнішній контент на сервер у MVP.

Не реалізовувати server-side fetching довільних URL без окремої захищеної логіки.

---

# 11. АДМІНІСТРАТИВНА ПАНЕЛЬ

Admin URL:

```text
/admin
```

Функції:

## Dashboard

Показувати:

* кількість програм;
* кількість релізів;
* кількість файлів;
* загальну кількість завантажень;
* останні завантаження;
* останні адміністративні дії;
* файли в quarantine;
* disabled-файли;
* вільне місце на диску;
* статус бази;
* статус storage;
* останній успішний backup.

## Керування програмами

* створення;
* редагування;
* preview;
* публікація;
* приховування;
* архівування;
* disable;
* безпечне видалення;
* керування категорією;
* керування тегами;
* завантаження іконки.

## Керування релізами

* створення версії;
* release channel;
* changelog;
* release date;
* current version;
* публікація;
* архівування.

## Керування файлами

* upload;
* перегляд metadata;
* SHA-256;
* розмір;
* detected type;
* architecture;
* package type;
* статус scanner;
* source URL;
* publish;
* disable;
* archive;
* delete;
* download test;
* копіювання публічного URL.

## Категорії й теги

* CRUD;
* унікальні slugs;
* сортування;
* visibility.

## Audit log

* фільтрація;
* дата;
* дія;
* користувач;
* entity;
* результат.

## Небезпечні дії

Для видалення або disable:

* явне підтвердження;
* CSRF;
* audit log;
* зрозуміле попередження.

Фізичне видалення файла з диска не повинно бути випадковим.

Бажано розділити:

```text
Archive
Disable
Delete metadata
Permanently delete file
```

Остання дія повинна вимагати окремого підтвердження.

---

# 12. ПУБЛІЧНИЙ ІНТЕРФЕЙС

Початкова мова інтерфейсу — українська.

Текстові рядки організувати так, щоб у майбутньому можна було додати англійську локалізацію.

## Головна сторінка

Містить:

* логотип або назву Software Hub;
* пошуковий рядок;
* категорії;
* останні оновлення;
* рекомендовані програми;
* популярні програми;
* короткий опис сервісу.

## Каталог

* список програм;
* пошук;
* фільтр за категорією;
* фільтр за тегами;
* pagination;
* сортування:

  * за назвою;
  * за датою оновлення;
  * за популярністю.

## Картка програми

* іконка;
* назва;
* короткий опис;
* поточна версія;
* категорія;
* дата оновлення;
* кнопка «Детальніше»;
* кнопка «Завантажити», якщо доступний рекомендований файл.

## Сторінка програми

* іконка;
* назва;
* розробник;
* опис;
* офіційний сайт;
* ліцензія;
* системні вимоги;
* поточна версія;
* changelog;
* доступні файли;
* architecture;
* package type;
* file size;
* SHA-256;
* дата додавання;
* кількість завантажень;
* історія версій;
* попередження про відповідальність користувача.

## Search

Пошук за:

* назвою;
* коротким описом;
* розробником;
* категорією;
* тегами.

Вимоги:

* нормалізація пробілів;
* мінімальна довжина запиту;
* обмеження максимальної довжини;
* безпечна pagination;
* зрозумілий empty state.

## UI/UX

* адаптивний дизайн;
* mobile-first;
* світла й темна тема;
* системна тема за замовчуванням;
* збереження вибору теми;
* доступна навігація з клавіатури;
* видимі focus states;
* достатній контраст;
* семантичні headings;
* labels для форм;
* коректні error messages;
* без залежності від JavaScript для основної навігації.

Не копіювати дизайн сторонніх сайтів.

Створити чистий, сучасний, технічний дизайн без надмірної анімації.

---

# 13. HTTP ROUTES

Остаточні назви можна адаптувати, але маршрути мають бути логічними.

## Public

```text
GET  /
GET  /software
GET  /software/{software_slug}
GET  /software/{software_slug}/releases
GET  /category/{category_slug}
GET  /search
GET  /download/{file_uuid}/{safe_filename}
HEAD /download/{file_uuid}/{safe_filename}
GET  /health
GET  /robots.txt
GET  /favicon.ico
```

## Authentication

```text
GET  /admin/login
POST /admin/login
POST /admin/logout
```

## Admin

```text
GET  /admin
GET  /admin/software
GET  /admin/software/new
POST /admin/software
GET  /admin/software/{id}/edit
POST /admin/software/{id}/edit
POST /admin/software/{id}/publish
POST /admin/software/{id}/archive

GET  /admin/software/{id}/releases/new
POST /admin/software/{id}/releases
GET  /admin/releases/{id}/edit
POST /admin/releases/{id}/edit

GET  /admin/releases/{id}/files/new
POST /admin/releases/{id}/files
GET  /admin/files/{id}
POST /admin/files/{id}/publish
POST /admin/files/{id}/disable
POST /admin/files/{id}/archive
POST /admin/files/{id}/delete

GET  /admin/categories
POST /admin/categories
POST /admin/categories/{id}/edit

GET  /admin/tags
POST /admin/tags

GET  /admin/audit
GET  /admin/backups
POST /admin/backups/create
```

Для HTML forms можна використовувати POST для дій замість PUT/PATCH/DELETE, але внутрішня бізнес-логіка повинна залишатися чистою.

---

# 14. NGINX

Nginx повинен:

* завершувати TLS;
* перенаправляти HTTP на HTTPS;
* передавати dynamic requests до FastAPI;
* віддавати static files;
* віддавати protected downloads через internal location;
* мати timeout settings;
* обмежувати upload size;
* мати rate limiting;
* мати security headers;
* не показувати версію Nginx;
* не дозволяти directory listing;
* не віддавати `.env`, `.git`, database, backup або internal config.

Передавати FastAPI коректні proxy headers:

* host;
* real client IP;
* scheme;
* request ID.

FastAPI повинен довіряти proxy headers тільки від відомого Nginx proxy, а не від довільного клієнта.

## Security headers

Налаштувати:

* Strict-Transport-Security після перевірки HTTPS;
* Content-Security-Policy;
* X-Content-Type-Options;
* Referrer-Policy;
* Permissions-Policy;
* frame-ancestors через CSP;
* захист від MIME sniffing.

Не використовувати застарілий `X-XSS-Protection` як основний захист.

CSP повинна бути сумісна з frontend.

Уникати inline scripts.

---

# 15. ДОСТУП ДО АДМІН-ПАНЕЛІ

Підтримати два режими.

## Звичайний режим

Admin доступний через інтернет, але захищений:

* HTTPS;
* login;
* Argon2id;
* session;
* CSRF;
* rate limit;
* temporary lockout;
* audit.

## Рекомендований production-режим

Admin доступний лише:

* через WireGuard;
* або з allowlist IP;
* або через окремий internal hostname.

Публічний каталог і downloads залишаються доступними всім.

Реалізувати це на рівні Nginx configuration, а не тільки приховуванням посилання.

Налаштування має бути задокументоване, але не повинно унеможливлювати локальну розробку.

---

# 16. DOCKER ТА CONTAINER SECURITY

Мінімальні сервіси:

```text
app
nginx
```

Опціонально:

```text
certbot
clamav
```

Вимоги:

* application container працює не від root;
* multi-stage Docker build;
* мінімальний production image;
* `.dockerignore`;
* точні залежності;
* healthcheck;
* graceful shutdown;
* restart policy;
* без `privileged: true`;
* не монтувати `/var/run/docker.sock`;
* не використовувати host network без необхідності;
* видалити зайві capabilities;
* root filesystem read-only, де можливо;
* окремий writable tmpfs для `/tmp`, якщо потрібно;
* secrets не копіювати в image;
* source code не містить production secrets.

Persistent data:

```text
database
storage
icons
backups
logs
certificates
```

Контейнер Nginx повинен мати read-only доступ до storage downloads, якщо це сумісно з конфігурацією.

App повинен мати write-доступ лише до потрібних папок:

* temporary;
* quarantine;
* software storage;
* icons;
* database;
* logs або stdout;
* backups, якщо backup запускається через app.

Не давати контейнеру доступ до всього `/srv`.

---

# 17. КОНФІГУРАЦІЯ ТА SECRETS

Використовувати typed settings через Pydantic Settings або еквівалент.

Приклади налаштувань:

```text
APP_ENV
APP_DEBUG
APP_SECRET_KEY
DATABASE_URL
SESSION_COOKIE_NAME
SESSION_IDLE_TIMEOUT
SESSION_ABSOLUTE_TIMEOUT
CSRF_SECRET
STORAGE_ROOT
TEMP_ROOT
QUARANTINE_ROOT
ICONS_ROOT
BACKUP_ROOT
MAX_UPLOAD_SIZE
ALLOWED_EXTENSIONS
PUBLIC_BASE_URL
TRUSTED_HOSTS
ADMIN_NETWORK_RESTRICTION
CLAMAV_ENABLED
LOG_LEVEL
```

Створити `.env.example` без реальних секретів.

Заборонено комітити:

* `.env`;
* password;
* private keys;
* session secrets;
* certificates;
* database;
* production backups.

У production бажано використовувати:

* Docker secrets;
* або файли з правами `600`;
* або системний secret manager.

Застосунок повинен завершувати запуск із чіткою помилкою, якщо критичні secrets відсутні або слабкі.

Не генерувати випадковий production secret при кожному старті контейнера, оскільки це зламає активні сесії.

---

# 18. LOGGING ТА OBSERVABILITY

Використовувати структуровані логи.

Кожен запит має отримувати request ID.

Логувати:

* request ID;
* method;
* route;
* status code;
* duration;
* важливі application events;
* login failures;
* upload errors;
* storage errors;
* backup errors;
* database errors.

Не логувати:

* паролі;
* cookies;
* CSRF tokens;
* secrets;
* повні download tokens;
* повний body upload;
* чутливі заголовки.

Для production:

* stdout/stderr або окремі log files;
* rotation;
* retention;
* обмеження розміру;
* зрозумілий формат.

Health endpoints:

```text
/health
```

Health check має перевіряти:

* роботу застосунку;
* можливість підключитися до бази;
* доступність storage;
* бажано достатність вільного місця.

Не повертати в health endpoint секретні внутрішні дані.

---

# 19. BACKUP І RESTORE

Резервувати:

* SQLite database;
* software storage;
* icons;
* configuration templates;
* deployment configuration;
* metadata;
* важливі logs за потреби.

Не покладатися лише на Proxmox snapshot.

## Вимоги

* окрема команда або script для backup;
* timestamped backups;
* manifest;
* checksum архіву;
* retention policy;
* cleanup старих backup;
* логування результату;
* fail-safe поведінка;
* документація restore;
* тест відновлення.

SQLite backup робити безпечним механізмом:

* SQLite backup API;
* або `.backup`;
* не копіювати довільно активний database file без урахування WAL.

Рекомендована політика:

* щоденний backup бази;
* регулярний backup metadata;
* щотижневий або інкрементальний backup storage;
* копія на іншому фізичному диску або сервері.

Створити:

```text
BACKUP_RESTORE.md
```

Документ повинен містити повний сценарій:

```text
чистий сервер
→ встановлення Docker
→ копіювання backup
→ restore database
→ restore storage
→ запуск migrations
→ перевірка checksum
→ запуск сервісів
→ health check
```

---

# 20. SQLITE

При старті connection налаштувати:

* `PRAGMA foreign_keys=ON`;
* WAL mode;
* busy timeout.

Не використовувати довгі database transactions під час upload великих файлів.

Правильний підхід:

1. Файл streaming-записується у temporary.
2. Перевіряється.
3. Створюється коротка database transaction.
4. Файл atomic move.
5. Metadata commit.
6. При помилці виконується compensation cleanup.

Продумати порядок дій, щоб не виникали:

* файл без metadata;
* metadata без файла;
* published запис із відсутнім файлом.

Створити reconciliation command, яка може:

* знайти metadata без файла;
* знайти orphan files;
* перевірити SHA-256;
* показати невідповідності;
* не видаляти нічого автоматично без explicit flag.

---

# 21. BUSINESS RULES

## Software

* draft не видно публічно;
* published видно відповідно до visibility;
* disabled не можна завантажувати;
* archived може бути доступним в історії, але не рекомендованим;
* private вимагає admin session.

## Release

* release не може бути published без software;
* release не може стати current, якщо він draft;
* current stable release має бути однозначно визначений;
* при виборі нового current release попередній автоматично втрачає цей статус у межах однієї транзакції.

## ReleaseFile

* файл не можна publish до завершення validation;
* файл у quarantine не можна завантажувати публічно;
* rejected-файл не можна publish;
* disabled-файл повертає 404 або 410 залежно від політики;
* public URL використовує UUID, а не physical path;
* видалення metadata має враховувати існування physical file;
* дублікати за SHA-256 повинні бути позначені.

## Downloads

* public файл доступний без login;
* unlisted доступний за прямим URL;
* private доступний лише admin;
* download endpoint перевіряє всі пов’язані статуси:

  * Software;
  * Release;
  * ReleaseFile.

---

# 22. ERROR HANDLING

Створити єдину систему application exceptions.

Приклади:

* EntityNotFound;
* PermissionDenied;
* InvalidStateTransition;
* FileValidationError;
* StorageError;
* DuplicateFileError;
* AuthenticationError;
* CSRFError;
* RateLimitError.

Публічний користувач не повинен бачити:

* stack trace;
* database query;
* physical path;
* internal container name;
* secret;
* environment variables.

Створити сторінки:

```text
400
401
403
404
409
413
422
429
500
503
```

Production error pages мають бути акуратними й не розкривати внутрішні деталі.

У development mode дозволити детальнішу діагностику.

---

# 23. TESTING

## Unit tests

Покрити:

* slug generation;
* password hashing;
* session expiry;
* CSRF;
* file name normalization;
* extension validation;
* magic bytes validation;
* path resolution;
* SHA-256;
* business state transitions;
* current release selection;
* visibility rules.

## Integration tests

Покрити:

* database repositories;
* Alembic migrations;
* login/logout;
* admin access;
* software CRUD;
* release CRUD;
* upload pipeline;
* publish flow;
* download authorization;
* audit logging;
* backup command;
* reconciliation command.

## Security tests

Обов’язково перевірити:

* SQL injection attempts;
* XSS payloads;
* CSRF absence;
* CSRF invalid token;
* path traversal;
* `../`;
* URL-encoded traversal;
* null byte;
* double extension;
* oversized upload;
* spoofed MIME type;
* duplicate hash;
* unauthorized admin access;
* brute-force protection;
* session fixation;
* expired session;
* revoked session;
* direct request до internal download path;
* IDOR;
* access до private file;
* access до disabled file;
* витік `.env`;
* витік backup;
* Host header manipulation.

## End-to-end tests

Мінімальний E2E набір:

1. Admin login.
2. Створення категорії.
3. Створення програми.
4. Створення релізу.
5. Upload файла.
6. Publish.
7. Відкриття публічної сторінки.
8. Завантаження файла.
9. Disable файла.
10. Перевірка, що download більше недоступний.

Для E2E можна використовувати Playwright.

## Coverage

Не вимагати штучні 100%.

Ціль:

* високе покриття business logic;
* повне покриття критичних security flows;
* повне покриття upload/download permissions;
* адекватне покриття repositories і services.

Встановити реалістичний мінімальний coverage threshold і задокументувати його.

---

# 24. CODE QUALITY

Вимоги:

* type hints для application code;
* mypy strict або близький до strict режим;
* невеликі функції;
* зрозумілі назви;
* dependency injection;
* відсутність глобальних mutable states;
* відсутність circular imports;
* єдина система часу в UTC;
* timezone-aware datetimes;
* централізована конфігурація;
* єдиний style;
* відсутність дублювання business rules;
* документація складних рішень.

Не використовувати:

* broad `except Exception` без логування та обґрунтування;
* `pass` у критичній логіці;
* приховане ігнорування помилок;
* hardcoded production paths;
* hardcoded passwords;
* hardcoded domain у business logic;
* небезпечний shell execution;
* `shell=True` із користувацькими даними;
* `eval`;
* `exec`;
* небезпечну deserialization.

---

# 25. CI/CD

GitHub Actions pipeline повинен запускати:

```text
Ruff format check
Ruff lint
mypy
pytest
coverage
security static analysis
dependency audit
Docker build
container scan
```

CI не повинен містити production secrets.

Для MVP автоматичний production deploy не є обов’язковим.

Можна реалізувати manual deployment:

```text
git pull
docker compose build
alembic upgrade head
docker compose up -d
health check
```

Але процес повинен бути задокументований і мати rollback strategy.

---

# 26. DEPLOYMENT

Ціль:

```text
software.hotzagor.tech
```

## VPS

Відкриті порти:

```text
80/tcp
443/tcp
```

SSH:

* ключі;
* password authentication disabled;
* root login disabled;
* бажано WireGuard або allowlist.

## Proxmox

Використовувати окрему Ubuntu Server VM.

Рекомендовані початкові ресурси:

```text
2 vCPU
2–4 GB RAM
20–30 GB system disk
окремий диск або mount для software storage
```

VM бажано розмістити:

* у DMZ;
* або окремому VLAN;
* без прямого доступу до management network;
* без публічного доступу до Proxmox GUI;
* без необмеженого доступу до домашньої LAN.

## DNS

```text
software.hotzagor.tech → public IP сервера
```

## HTTPS

* Let’s Encrypt;
* automatic renewal;
* redirect HTTP → HTTPS;
* перевірка renewal;
* документація аварійного поновлення.

---

# 27. PERFORMANCE

Проєкт повинен нормально працювати на слабкому VPS.

Оптимізації:

* Nginx віддає файли;
* FastAPI не стрімить великі downloads;
* pagination;
* database indexes;
* lazy loading контролюється;
* уникати N+1 queries;
* cache headers для static assets;
* thumbnails та іконки оптимізовані;
* gzip або Brotli лише для текстових ресурсів;
* не стискати EXE, ZIP, MSI повторно;
* обмежена кількість Uvicorn workers.

Для SQLite і одного application instance початково використовувати один Uvicorn worker, якщо немає підтвердженої необхідності в більшій кількості.

Nginx бере на себе downloads і static content, тому один worker достатній для MVP.

Документувати умови переходу до:

* PostgreSQL;
* кількох app instances;
* object storage;
* CDN.

---

# 28. ACCESSIBILITY І SEO

## Accessibility

* semantic HTML;
* правильні labels;
* keyboard navigation;
* focus states;
* `aria` лише там, де потрібно;
* достатній contrast;
* alt text для іконок;
* зрозумілі validation errors;
* адаптивність.

## SEO

Для публічних сторінок:

* title;
* description;
* canonical URL;
* Open Graph metadata;
* sitemap опціонально;
* robots.txt;
* noindex для admin, login, internal pages.

Не дозволяти індексацію:

```text
/admin
/backups
/internal
```

---

# 29. LEGAL І TRUST METADATA

Software Hub не повинен позиціонуватися як джерело піратського або зламаного ПЗ.

Для кожної програми передбачити:

* developer;
* official website;
* source URL;
* license;
* SHA-256;
* date added;
* optional signature status.

Адміністратор відповідає за право розповсюдження файла.

Додати коротке повідомлення:

```text
Перед встановленням перевіряйте контрольну суму та переконайтеся, що ви довіряєте джерелу файла.
```

Не змінювати цифровий підпис оригінального інсталятора.

Не модифікувати сторонні інсталятори без явної причини.

---

# 30. DOCUMENTATION

Створити якісну документацію.

## README.md

Містить:

* опис проєкту;
* можливості;
* screenshots placeholders;
* стек;
* локальний запуск;
* environment variables;
* migrations;
* tests;
* Docker;
* створення адміністратора;
* основні команди.

## DEPLOYMENT.md

* VPS deployment;
* Proxmox VM deployment;
* DNS;
* HTTPS;
* firewall;
* Docker;
* Nginx;
* WireGuard restriction;
* update process;
* rollback.

## SECURITY.md

* security model;
* threat model;
* session security;
* upload security;
* download security;
* secret management;
* vulnerability reporting;
* security checklist.

## BACKUP_RESTORE.md

* backup;
* retention;
* offsite copy;
* restore;
* verification;
* disaster recovery.

## ARCHITECTURE.md

* system overview;
* components;
* data flow;
* upload flow;
* download flow;
* authentication flow;
* database model;
* reasons for technology choices;
* scaling path.

## OPERATIONS.md

* logs;
* health checks;
* disk monitoring;
* cleanup;
* backup status;
* certificate renewal;
* common failures.

## CHANGELOG.md

Дотримуватися зрозумілого формату версій.

---

# 31. CLI ТА MAINTENANCE COMMANDS

Передбачити команди:

```text
create-admin
change-admin-password
revoke-sessions
cleanup-expired-sessions
cleanup-temporary-files
create-backup
restore-backup
verify-storage
recalculate-checksums
find-orphan-files
show-system-status
```

Команди повинні:

* мати зрозумілий help;
* повертати коректний exit code;
* не показувати секрети;
* вимагати підтвердження для destructive actions;
* підтримувати dry-run там, де це доречно.

---

# 32. MVP SCOPE

Перша версія обов’язково включає:

* публічну головну сторінку;
* каталог;
* пошук;
* категорії;
* теги;
* сторінку програми;
* історію релізів;
* кілька файлів на один реліз;
* пряме завантаження через Nginx;
* SHA-256;
* статистику завантажень;
* responsive design;
* dark/light theme;
* admin login;
* server-side sessions;
* CSRF;
* rate limiting;
* admin dashboard;
* Software CRUD;
* Release CRUD;
* ReleaseFile upload;
* quarantine;
* publish/disable/archive;
* categories/tags management;
* audit log;
* SQLite migrations;
* Docker Compose;
* Nginx;
* HTTPS documentation;
* backup/restore;
* unit tests;
* integration tests;
* security tests;
* CI;
* documentation.

---

# 33. OUT OF SCOPE ДЛЯ MVP

Не реалізовувати в першій версії без окремої команди:

* відкриту реєстрацію;
* соціальну авторизацію;
* коментарі;
* рейтинги;
* форуми;
* платні підписки;
* платежі;
* desktop client;
* package manager client;
* automatic app updates;
* GitHub Releases sync;
* Telegram bot;
* email notifications;
* CDN;
* S3 object storage;
* multi-region deployment;
* Kubernetes;
* Redis;
* Celery;
* PostgreSQL;
* автоматичне скачування файлів із довільних URL;
* автоматичне виконання EXE;
* автоматичне розпакування архівів;
* multi-tenant architecture;
* складну RBAC-систему;
* public REST API.

Архітектура не повинна блокувати ці можливості в майбутньому, але MVP не повинен бути ними перевантажений.

---

# 34. КРИТЕРІЇ ГОТОВНОСТІ

MVP вважається готовим, коли:

1. Проєкт запускається через Docker Compose.
2. Усі migrations застосовуються на чистій базі.
3. Адміністратора можна створити без default password.
4. Admin login захищений.
5. Сесії працюють правильно.
6. CSRF працює для всіх state-changing forms.
7. Можна створити категорію.
8. Можна створити програму.
9. Можна створити реліз.
10. Можна upload файл.
11. Файл проходить validation.
12. SHA-256 розраховується автоматично.
13. Файл не доступний до публікації.
14. Після публікації він доступний через download endpoint.
15. Nginx віддає файл через internal redirect.
16. Physical storage path не розкривається.
17. Path traversal не працює.
18. Private та disabled файли недоступні.
19. Статистика оновлюється.
20. Audit log записує admin actions.
21. Backup створюється.
22. Backup можна відновити.
23. Health check працює.
24. У production не показуються stack traces.
25. Усі критичні тести проходять.
26. Ruff, mypy і pytest проходять.
27. Docker image проходить security scan без невиправданих critical vulnerabilities.
28. Документація дозволяє розгорнути систему на чистому Ubuntu Server.
29. Сайт коректно працює на desktop і mobile.
30. Домен `software.hotzagor.tech` може бути підключений без зміни application code.

---

# 35. SECURITY ACCEPTANCE CHECKLIST

Перед production deployment перевірити:

```text
[ ] HTTPS працює
[ ] HTTP перенаправляється на HTTPS
[ ] Secure cookies увімкнені
[ ] HttpOnly cookies увімкнені
[ ] SameSite налаштований
[ ] CSRF працює
[ ] Argon2id використовується
[ ] Default password відсутній
[ ] Login rate limit працює
[ ] Session fixation неможлива
[ ] Expired session не приймається
[ ] Revoked session не приймається
[ ] Адмінка обмежена через VPN/IP або додатково захищена
[ ] Storage поза web-root
[ ] Internal Nginx location недоступний напряму
[ ] Path traversal tests проходять
[ ] Upload size обмежений
[ ] Extension allowlist працює
[ ] Magic bytes перевіряються
[ ] Temporary files очищаються
[ ] Quarantine працює
[ ] App працює не від root
[ ] Docker socket не змонтований
[ ] Privileged mode відсутній
[ ] Secrets не містяться в Git
[ ] .env недоступний через Nginx
[ ] Database недоступна через Nginx
[ ] Backups недоступні через Nginx
[ ] Directory listing вимкнено
[ ] Security headers налаштовані
[ ] Host validation працює
[ ] Logs не містять passwords/cookies/tokens
[ ] Backup протестований
[ ] Restore протестований
[ ] Dependency audit виконаний
[ ] Container scan виконаний
```

---

# 36. ОЧІКУВАНИЙ РЕЗУЛЬТАТ ВІД ШТУЧНОГО ІНТЕЛЕКТУ

На першому етапі не пиши повну реалізацію.

Спочатку надай:

1. Коротке резюме розуміння проєкту.
2. Остаточну архітектурну схему.
3. Перелік основних модулів.
4. Остаточну модель даних.
5. Детальний пофазний план.
6. Залежності між фазами.
7. Security plan.
8. Testing plan.
9. Deployment plan.
10. Перелік ризиків.
11. Критерії завершення кожної фази.
12. Перелік рішень, які потребують фіксації перед реалізацією.

Не пропонуй змінювати затверджений стек без вагомої причини.

Не замінюй SQLite на PostgreSQL для MVP.

Не замінюй Jinja2 на React.

Не додавай Redis, Celery або Kubernetes.

Не спрощуй security-вимоги.

Не починай реалізацію, доки не буде окремої команди перейти до конкретної фази.

Після затвердження плану реалізовуй проєкт послідовно, дотримуючись цього документа як основного технічного завдання.