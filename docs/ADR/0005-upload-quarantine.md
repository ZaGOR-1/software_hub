# ADR-0005: Streaming upload із quarantine та ручною публікацією

- **Статус:** Accepted
- **Дата:** 2026-07-23

## Контекст

Адміністратор завантажує потенційно небезпечні executable та archive files. Навіть trusted admin може випадково завантажити неправильний, заражений або підмінений файл. Перевірка лише extension чи browser MIME недостатня.

## Рішення

Кожен upload проходить pipeline:

```text
auth → CSRF → size pre-check → streaming temp write
→ actual size limit → filename normalization
→ extension allowlist → magic bytes → SHA-256
→ duplicate lookup → optional scanner
→ quarantine → metadata record → manual publish
```

Жоден новий файл не стає public автоматично.

## Validation policy

- allowlist: EXE, MSI, ZIP, 7z;
- browser-provided MIME — untrusted metadata;
- detect PE, Compound File Binary, ZIP і 7z signatures;
- unknown/mismatch залишається у quarantine або rejected;
- archive contents не розпаковуються;
- uploaded binaries не виконуються;
- original filename не використовується як storage path;
- SHA-256 обчислюється під час streaming;
- max size за замовчуванням 2 GiB, configurable;
- insufficient free space блокує upload до запису повного файла.

## Failure handling

- temp file видаляється при validation, DB або move failure;
- permanent move виконується атомарно, де це можливо;
- reconciliation command знаходить metadata without file та orphan files;
- destructive automatic cleanup orphan files заборонений без explicit flag.

## Malware scanner

Визначається interface:

```text
scan(path) → clean | infected | error | unavailable
```

Scanner optional. `infected` блокує publish. `unavailable` не ламає базовий application, але статус відображається адміністратору й застосовується policy, зафіксована в settings.

## Наслідки

### Позитивні

- файл не потрапляє в public storage до review;
- мінімальний memory footprint;
- defense-in-depth проти spoofed upload;
- зрозумілий audit trail.

### Негативні

- publish стає двоетапним;
- потрібна cleanup і consistency logic;
- signature checks не доводять безпечність вмісту.

## Відхилені альтернативи

- автоматична публікація після extension check;
- читання всього upload у RAM;
- обов’язковий ClamAV як hard dependency;
- розпакування й аналіз archives у MVP.
