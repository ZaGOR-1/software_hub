# Authentication and server-side sessions

## Scope

Phase 6 implements manually provisioned administrator accounts, Argon2id password
verification, login lockout, opaque server-side sessions, session rotation,
revocation, expiry, logout, protected admin dependencies and maintenance CLI
commands.

CSRF validation is intentionally deferred to Phase 7. Until Phase 7 is merged,
the login and logout forms are not considered production-ready state-changing
forms even though SameSite cookies and POST-only logout already reduce exposure.

## Password storage

Passwords are never stored or logged in clear text. `PasswordService` uses
`argon2-cffi` with Argon2id and explicit configurable parameters:

```text
time cost:      3
memory cost:    65,536 KiB
parallelism:    4
hash length:    32 bytes
salt length:    16 bytes
```

Production configuration cannot lower the approved time or memory settings.
The current password policy is intentionally length-focused:

- minimum 12 characters;
- maximum 1,024 characters;
- no leading or trailing whitespace;
- password cannot equal the normalized username;
- no brittle character-class composition rules.

Successful login transparently rehashes an older valid password hash when the
configured Argon2 parameters change.

Unknown usernames still trigger one process-cached dummy Argon2 verification so
that the major password-hashing work is not skipped. HTTP feedback remains the
same for an unknown username, wrong password, inactive account and temporary
lockout:

```text
Невірний логін або пароль.
```

## Administrator provisioning

There is no public registration and no default production account. Administrators
are created from the maintenance CLI:

```bash
export SOFTWARE_HUB_ADMIN_PASSWORD='use-a-strong-secret'
uv run python -m app.cli create-admin --username admin
unset SOFTWARE_HUB_ADMIN_PASSWORD
```

Interactive `getpass` input is used when the environment variable is absent.
Passwords are deliberately not accepted as command-line arguments because
process lists and shell history can expose them.

Available Phase 6 commands:

```bash
uv run python -m app.cli create-admin --username admin
uv run python -m app.cli change-admin-password --username admin
uv run python -m app.cli revoke-sessions --username admin
uv run python -m app.cli cleanup-expired-sessions
```

`change-admin-password` revokes every active session for that administrator.
All commands return a non-zero exit status on validation or application errors
and never print a password, hash, raw session token or secret.

## Login lockout

The default policy is:

```text
failed attempts: 5
lockout period:  15 minutes
```

Rules:

1. A wrong password increments the account counter.
2. The threshold sets `locked_until`.
3. Requests during lockout still perform password verification to reduce obvious
   timing differences, but cannot authenticate.
4. An expired lockout resets the counter before the next attempt.
5. A successful login resets the failure counter and lockout timestamp.
6. Inactive accounts cannot log in.
7. Every success and failure creates a sanitized audit event.

This app-level lockout must be combined with Nginx login rate limiting in Phase
17. Account lockout alone is not sufficient against distributed password
spraying and can be abused for denial of service against a known username.

## Session token design

The browser cookie contains only a cryptographically random opaque bearer token.
The token is generated with 32 random bytes and URL-safe encoding.

The database stores only:

- SHA-256 hash of the token;
- user relation;
- creation and activity timestamps;
- idle and absolute expiry timestamps;
- revocation timestamp;
- HMAC-derived IP and User-Agent identifiers;
- a session-bound CSRF derivation value reserved for Phase 7.

The raw token is returned once by `SessionService.create_record()` and is never
stored in SQLite, audit rows or application logs.

## Cookie policy

Default cookie settings:

```text
name:      software_hub_session
path:      /admin
HttpOnly:  true
SameSite:  Lax
Secure:    true in production
Max-Age:   absolute session lifetime
```

Production startup fails when secure cookies are explicitly disabled. HTTPS is
also a required production invariant.

The cookie path deliberately limits browser delivery to `/admin`. Public catalog
routes do not receive the administrator session cookie.

## Rotation and fixation protection

Every successful login creates a new random server-side session. A previous
session token supplied with the login request is revoked before the new session
is returned. An attacker-controlled pre-login cookie therefore cannot become the
new authenticated session identifier.

The application never upgrades an anonymous client token into an authenticated
record.

## Expiry and activity

Defaults:

```text
idle timeout:       30 minutes
absolute lifetime:  12 hours
activity write:     at most once per 60 seconds
```

The idle deadline slides only after the configured touch interval and can never
exceed the absolute deadline. This reduces unnecessary SQLite writes while
preserving bounded inactivity expiry.

A session is rejected when it is:

- absent or malformed;
- unknown;
- revoked;
- past idle expiry;
- past absolute expiry;
- linked to an inactive user.

Expired rows are removed by the maintenance command. Expiry checks do not depend
on cleanup having already run.

## Client metadata

Raw IP addresses and User-Agent values are not persisted. Separate HMAC purposes
produce non-reversible identifiers using the application secret.

A changed IP or User-Agent is returned as an audit signal on the authenticated
session context. It does not automatically invalidate the session because mobile
networks, VPNs and browser updates make strict fingerprint binding unreliable.

## Route protection

Phase 6 adds:

```text
GET  /admin/login
POST /admin/login
POST /admin/logout
GET  /admin
```

`OptionalAdminSession` resolves a session when present. `RequiredAdminSession`
redirects unauthenticated browser requests to `/admin/login` and exposes the
validated administrator through request state.

The current `/admin` page is intentionally a minimal protected proof of the auth
boundary. Full dashboard and CRUD behavior remain Phase 8 scope.

## Audit events

Authentication workflows append sanitized rows for:

```text
admin_created
admin_login_success
admin_login_failed
admin_logout
admin_password_changed
admin_sessions_revoked
expired_sessions_cleaned
```

Audit metadata rejects sensitive key fragments such as password, token, cookie,
session, CSRF, authorization and secret. Raw credentials and session tokens are
never audit metadata.

## Configuration reference

```text
SOFTWARE_HUB_SESSION_COOKIE_NAME
SOFTWARE_HUB_SESSION_COOKIE_PATH
SOFTWARE_HUB_SESSION_COOKIE_SAME_SITE
SOFTWARE_HUB_SESSION_COOKIE_SECURE
SOFTWARE_HUB_SESSION_IDLE_TIMEOUT_SECONDS
SOFTWARE_HUB_SESSION_ABSOLUTE_TIMEOUT_SECONDS
SOFTWARE_HUB_SESSION_TOUCH_INTERVAL_SECONDS
SOFTWARE_HUB_LOGIN_MAX_FAILED_ATTEMPTS
SOFTWARE_HUB_LOGIN_LOCKOUT_SECONDS
SOFTWARE_HUB_PASSWORD_MIN_LENGTH
SOFTWARE_HUB_PASSWORD_MAX_LENGTH
SOFTWARE_HUB_ARGON2_TIME_COST
SOFTWARE_HUB_ARGON2_MEMORY_COST_KIB
SOFTWARE_HUB_ARGON2_PARALLELISM
```

## Security boundaries retained for later phases

- Phase 7 adds session-bound CSRF tokens to every state-changing form.
- Phase 8 replaces the protected placeholder with admin CRUD.
- Phase 15 expands audit browsing and operational visibility.
- Phase 17 adds Nginx login rate limiting and optional VPN/IP restriction.
- Phase 18 runs the complete production-like security and E2E suite.
