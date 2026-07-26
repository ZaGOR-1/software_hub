# ADR-0003: Server-side sessions замість JWT у браузері

- **Статус:** Accepted
- **Дата:** 2026-07-23
- **Оновлено:** 2026-07-24 (Phase 12)

## Контекст

Admin panel — звичайний SSR web application із невеликою кількістю адміністраторів. Потрібні logout, revocation, idle timeout, absolute lifetime, lockout і можливість відкликати sessions після зміни пароля.

JWT у localStorage збільшив би XSS impact і ускладнив би revocation без додаткового server-side state.

## Рішення

Використовувати opaque server-side sessions.

- Browser cookie містить лише випадковий session token.
- База зберігає cryptographic hash token.
- Cookie: `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/` у production.
- Session ID регенерується після login.
- Idle timeout: 30 хвилин.
- Absolute lifetime: 12 годин.
- Logout відкликає server-side record.
- Password change відкликає інші активні sessions.
- Cleanup expired sessions запускається maintenance command.

## Security properties

- session fixation блокується rotation;
- викрадений database dump не містить reusable raw tokens;
- session можна відкликати негайно;
- cookie не доступна JavaScript;
- CSRF вирішується окремим session-bound token.
- root-scoped cookie потрібна для авторизації private downloads на `/download/...`;
- session lookup виконується лише в routes, які явно підключають auth dependency.

## Наслідки

### Позитивні

- просте й зрозуміле SSR authentication;
- повний контроль revocation;
- коректний logout;
- мінімум client-side security state.

### Негативні

- кожен authenticated request виконує session lookup;
- потрібна cleanup policy;
- cookie configuration залежить від HTTPS/proxy correctness.

## Відхилені альтернативи

- JWT у localStorage;
- long-lived signed cookie з усіма user claims;
- OAuth/social login у MVP.
