# ADR-0002: SQLite як база даних MVP

- **Статус:** Accepted
- **Дата:** 2026-07-23

## Контекст

Software Hub має низький і помірний обсяг metadata writes. Великі файли віддає Nginx, а application не стрімить downloads. Deployment розрахований на один VPS/VM та один application instance.

## Рішення

Використовувати SQLite через SQLAlchemy 2.x і Alembic для MVP.

Обов’язкові параметри:

- foreign keys для кожного connection;
- WAL mode;
- configurable busy timeout, початково 5000 ms;
- один Uvicorn worker;
- короткі transactions;
- pagination та indexes;
- SQLite backup API або `.backup`;
- reconciliation command для DB/filesystem consistency.

## Transaction policy

Upload flow не тримає transaction під час передачі файла:

```text
stream → validate → hash → quarantine → short DB transaction
```

Publish flow використовує контрольований filesystem move і коротку transaction із compensation/reconciliation strategy.

## Наслідки

### Позитивні

- мінімальна інфраструктура;
- прості backup і local development;
- достатньо для одного writer-oriented admin workflow;
- низьке споживання RAM.

### Негативні

- обмежений write concurrency;
- не підходить для кількох app instances;
- database file потребує коректних filesystem permissions;
- backup не можна робити наївним копіюванням active DB/WAL.

## Умови переходу на PostgreSQL

Міграція розглядається, якщо з’явиться хоча б одна умова:

- потрібні кілька app instances;
- регулярні lock timeouts навіть після оптимізації transactions;
- значно зростає write concurrency;
- потрібні складні analytics/query capabilities;
- база стає operational bottleneck.

Business logic не повинна містити SQLite-specific SQL, окрім infrastructure/migration layer.

## Відхилені альтернативи

- PostgreSQL від першого дня;
- MySQL;
- зберігання metadata у JSON files;
- зберігання binaries у BLOB.
