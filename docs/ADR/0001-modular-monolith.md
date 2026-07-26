# ADR-0001: Модульний моноліт

- **Статус:** Accepted
- **Дата:** 2026-07-23

## Контекст

Software Hub має публічний каталог, admin panel, authentication, upload/download, audit, backup і maintenance. Проєкт підтримує одна людина та розгортає на одному слабкому VPS або Ubuntu VM.

Мікросервісна архітектура створила б додаткові межі deployment, network failure modes, distributed logging, service authentication і складність consistency без користі для MVP.

## Рішення

Реалізувати один FastAPI application як модульний моноліт із чіткими шарами:

```text
Router → Application Service → Repository → Database
Router → Application Service → Storage Service → File System
```

Модулі мають окремі routers, services, repositories, schemas і templates, але працюють в одному process та одному repository.

## Правила

- HTTP router не містить основну бізнес-логіку.
- Repository не приймає HTTP objects.
- Service не залежить від Jinja templates.
- Storage path logic ізольована в `app/storage`.
- Business rules не дублюються в routes і templates.
- Заборонені circular imports і глобальний mutable state.

## Наслідки

### Позитивні

- простий deployment;
- одна транзакційна межа;
- легший local development;
- менше operational overhead;
- модулі можна тестувати окремо;
- у майбутньому конкретний модуль можна виділити лише за доведеної потреби.

### Негативні

- application modules ділять один process;
- помилка process впливає на весь dynamic application;
- потрібна дисципліна залежностей, щоб не отримати «великий файл із усім».

## Відхилені альтернативи

- мікросервіси;
- Kubernetes;
- event-driven architecture;
- окремий API gateway;
- надмірне DDD.
