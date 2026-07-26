# CSRF protection

## Scope

Phase 7 protects every state-changing HTTP route that currently exists:

```text
POST /admin/login
POST /admin/logout
```

It also introduces the reusable `CSRFProtectedAdminSession` dependency that all
future administrator POST routes must use in Phase 8 and later phases.

The implementation uses two related flows because the login form is rendered
before an authenticated server-side session exists.

## Token format

Tokens use a compact URL-safe structure:

```text
v1.<issued_at>.<random_nonce>.<HMAC-SHA256>
```

Properties:

- the nonce contains 32 cryptographically random bytes;
- the signature covers the version, purpose, timestamp and nonce;
- signatures are compared with `hmac.compare_digest`;
- malformed, oversized, expired, future-dated and incorrectly signed values
  fail closed;
- tokens are never placed in URLs;
- token values are redacted from structured logs and audit metadata.

A token is reusable within its short validity window and security context. It is
not a one-time token. This avoids server-side token storage and supports normal
form resubmission while retaining session binding and bounded lifetime.

## Pre-authentication login protection

`GET /admin/login` creates:

1. a random nonce in an HttpOnly cookie;
2. a signed hidden form token containing the same nonce.

Default login-context cookie policy:

```text
name:      software_hub_login_csrf
path:      /admin/login
HttpOnly:  true
SameSite:  Strict
Secure:    true in production
Max-Age:   10 minutes
```

The cookie is not an authentication credential. The form token is accepted only
when:

- the cookie is present;
- the cookie nonce matches the signed token context;
- the HMAC is valid;
- the token is within its configured lifetime.

A failed password attempt renders a fresh login token and rotates the nonce
cookie. Successful login deletes the pre-authentication cookie and creates a new
opaque authenticated session.

CSRF validation runs before password verification. A missing or invalid token
therefore does not increment the account failed-login counter and does not reveal
whether a username exists.

## Authenticated session protection

At login, the session row already stores a derived value:

```text
HMAC(global CSRF secret, session token hash)
```

The raw session token remains only in the HttpOnly session cookie. The derived
value is used as a per-session HMAC key for administrator form tokens.

Consequences:

- a token from one administrator session cannot be used by another session;
- a token from a previous session fails after login rotation;
- revoking or expiring the server-side session blocks the request before the
  token can authorize an action;
- the global CSRF secret is not embedded in a form or cookie;
- no raw CSRF token is stored in SQLite.

Default authenticated token lifetime is two hours and cannot exceed the absolute
session lifetime.

## FastAPI integration

The authentication dependencies are:

```text
OptionalAdminSession
RequiredAdminSession
LoginCSRFProtection
CSRFProtectedAdminSession
```

`LoginCSRFProtection` verifies the pre-authentication login form.

`CSRFProtectedAdminSession` first requires a valid administrator session, then
reads the configured hidden form field and verifies it against that session's
derived CSRF key. Future state-changing admin routes must depend on this alias
rather than merely hiding controls in HTML.

The shared template component is:

```text
app/templates/components/csrf.html
```

Forms receive `csrf_token` and `csrf_field_name` in their Jinja context. Jinja
autoescaping remains enabled.

The dependency checks the configured `X-CSRF-Token` header before reading form
data. This allows future streaming upload routes to validate CSRF without asking
Starlette to parse the complete multipart body first. No cross-origin CORS policy
is enabled, so a foreign origin cannot send this custom header without a failed
preflight.

## Failure behavior

Invalid requests raise `CSRFError` and return HTTP `403` with the stable public
code:

```json
{
  "error": {
    "code": "csrf_error",
    "message": "The security token is invalid or expired.",
    "request_id": "..."
  }
}
```

HTML clients receive the standard safe `403` page. Responses use
`Cache-Control: no-store`. Logs contain only an allowlisted failure reason such
as `missing`, `expired` or `signature_mismatch`; submitted token values are not
logged.

## Configuration

```text
SOFTWARE_HUB_CSRF_SECRET
SOFTWARE_HUB_CSRF_FORM_FIELD_NAME
SOFTWARE_HUB_CSRF_HEADER_NAME
SOFTWARE_HUB_CSRF_TOKEN_TTL_SECONDS
SOFTWARE_HUB_CSRF_TOKEN_MAX_LENGTH
SOFTWARE_HUB_LOGIN_CSRF_COOKIE_NAME
SOFTWARE_HUB_LOGIN_CSRF_COOKIE_PATH
SOFTWARE_HUB_LOGIN_CSRF_COOKIE_SAME_SITE
SOFTWARE_HUB_LOGIN_CSRF_TTL_SECONDS
```

`SOFTWARE_HUB_CSRF_SECRET` must be a strong value distinct from
`SOFTWARE_HUB_APP_SECRET_KEY`. Production startup already fails when either
secret is missing or weak.

## Security tests

Phase 7 tests cover:

- missing login token;
- missing login nonce cookie;
- malformed and oversized values;
- signature tampering;
- expiration and excessive future timestamps;
- cross-browser login token reuse;
- missing and invalid logout tokens;
- cross-session token reuse;
- reuse after session rotation;
- production `Secure` cookie flags;
- CSRF-value redaction from JSON logs;
- no failed-login counter change on CSRF rejection.

## Remaining boundaries

- Phase 8 must use `CSRFProtectedAdminSession` on every new state-changing admin
  route.
- Same-origin header transport is implemented for future JavaScript and
  streaming upload routes; current SSR forms continue to use hidden fields.
- Nginx login rate limiting and private-network administration restrictions are
  Phase 17 controls.
- CSRF does not protect against XSS or a compromised same-origin script; CSP,
  output escaping and strict content handling remain independent requirements.
