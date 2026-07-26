# ADR-0004: Видача файлів через Nginx X-Accel-Redirect

- **Статус:** Accepted
- **Дата:** 2026-07-23
- **Реалізовано:** 2026-07-24 (Phase 12)

## Контекст

Software Hub віддає великі EXE, MSI, ZIP і 7z. FastAPI повинен перевіряти metadata, statuses та visibility, але не повинен витрачати Python worker на передачу великих response bodies.

## Рішення

FastAPI authorization endpoint після перевірок повертає internal redirect header:

```text
X-Accel-Redirect: /protected-downloads/<internal-relative-path>
```

Nginx location `/protected-downloads/` налаштовується як `internal` і має read-only доступ до permanent storage. FastAPI повертає порожню upstream-відповідь; після internal redirect Nginx сам визначає фактичний `Content-Length` і обробляє Range/resume.

## Обов’язкові перевірки перед redirect

- valid public UUID;
- safe requested filename;
- Software status і visibility;
- Release status;
- ReleaseFile status і visibility;
- private access requires active admin session;
- physical file exists inside storage root;
- resolved path не виходить за storage root.

## Statistics semantics

- `HEAD` не збільшує counter.
- Authorized `GET` збільшує counter після всіх checks і до internal redirect.
- Для MVP це означає authorized download start, а не confirmed completion.
- Blocked requests можуть збільшувати aggregate blocked counter, але не public download count.

## Наслідки

### Позитивні

- low RAM/CPU usage у Python;
- підтримка Range/resume силами Nginx;
- application worker швидко звільняється;
- storage залишається непублічним.

### Негативні

- потрібна точна відповідність app і Nginx path mapping;
- completion analytics неточна без аналізу Nginx logs;
- production-like integration tests складніші.

## Security requirements

- direct request до internal location має бути заборонений;
- directory listing вимкнений;
- response не містить physical path;
- Nginx не віддає database, backups, temp або quarantine;
- user filename використовується лише для безпечного `Content-Disposition` і cosmetic URL.

## Відхилені альтернативи

- `FileResponse` для великих файлів;
- public static storage path;
- signed direct URLs без application authorization у MVP.
