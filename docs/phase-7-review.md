# Phase 7 completion review

## Scope

Phase 7 implements pre-authentication login CSRF protection, authenticated
session-bound CSRF tokens, reusable FastAPI dependencies, hidden Jinja form
fields and security tests for every state-changing route currently present.

It does not implement the Phase 8 CRUD routes, upload forms, Nginx rate
limiting or origin-wide middleware that tries to infer whether an arbitrary
route is state changing. A same-origin header path is included so later
streaming uploads can validate CSRF before multipart parsing.

## Implemented files

```text
app/core/csrf.py
app/routers/auth/dependencies.py
app/routers/auth/login.py
app/routers/admin/dashboard.py
app/templates/components/csrf.html
app/templates/auth/login.html
app/templates/admin/dashboard.html
tests/unit/core/test_csrf.py
tests/integration/test_auth_routes.py
tests/security/test_auth_security.py
```

Additional changes:

- typed CSRF and login-context settings;
- per-session CSRF material exposed only in an internal, redacted session
  context;
- login-context cookie creation, rotation and deletion;
- README, environment example, documentation index, authentication guide,
  technical decisions and threat-model updates;
- corrected `pyproject.toml` runtime dependency declarations so they match the
  already committed `uv.lock` root metadata.

## Acceptance results

```text
[PASS] POST /admin/login rejects a missing token
[PASS] POST /admin/login rejects a missing context cookie
[PASS] POST /admin/login rejects malformed, oversized and tampered tokens
[PASS] Cross-browser login token reuse is rejected
[PASS] CSRF rejection does not increment failed-login attempts
[PASS] Password validation runs only after successful CSRF validation
[PASS] Failed login returns a fresh token and rotated context cookie
[PASS] Successful login removes the pre-authentication cookie
[PASS] POST /admin/logout requires an authenticated session and CSRF token
[PASS] Missing and invalid logout tokens do not revoke the session
[PASS] Session token from one session fails in another session
[PASS] Old token fails after authenticated session rotation
[PASS] Token expiration and future timestamp checks work
[PASS] HMAC comparisons use constant-time comparison
[PASS] Tokens never appear in form action URLs
[PASS] CSRF fields are emitted by one shared Jinja component
[PASS] CSRF values are redacted from structured logs
[PASS] Login and session cookies use Secure in production
[PASS] No database schema migration is required
```

## Test result

```text
283 tests passed
98.36% branch-aware coverage
0 warnings
```

The full suite includes unit tests for token format and cryptography, HTTP tests
for login/logout forms, cross-browser and cross-session security tests,
production cookie tests, automatic unsafe-route inventory checks and all prior
database, model, repository, authentication and session tests.

## Design decisions

Authenticated forms use a synchronizer-token design based on a key derived from
the server-side session token hash and the global CSRF secret.

Login has no authenticated session, so it uses a short-lived signed
pre-authentication nonce cookie plus hidden token. The nonce cookie is HttpOnly,
`SameSite=Strict`, scoped to `/admin/login` and deleted after successful login.

Tokens are short-lived but not single-use. This supports resubmission without a
write per rendered form. Rotation or revocation of the session invalidates the
security context.

## Quality checks performed locally

```text
python -m compileall app tests alembic
python -m pytest
clean Alembic upgrade/current/check/downgrade/re-upgrade
real Uvicorn login → admin → CSRF logout smoke flow
production-cookie integration test
Python AST parsing
TOML/YAML parsing
internal Markdown-link validation
source line and generated-artifact checks
archive checksum and ZIP integrity
```

## Known limitations

- New Phase 8 admin POST routes must explicitly use
  `CSRFProtectedAdminSession`; this is documented and will be enforced by Phase
  8 route tests.
- Same-origin `X-CSRF-Token` transport is implemented, but no cross-origin CORS
  policy is enabled or planned for the MVP.
- Nginx rate limiting and VPN/IP restriction remain Phase 17.
- Local validation uses Python 3.13.5 because Python 3.14 is unavailable in the
  execution sandbox.
- Ruff, mypy, Bandit and pip-audit are not installed locally. Network
  restrictions also prevent `uv` from downloading the configured Python 3.14
  runtime. These remain mandatory GitHub Actions gates.

## Definition of Done

```text
[x] Every current state-changing route is CSRF protected
[x] Missing, invalid, expired and cross-context tokens fail closed
[x] Session-bound tokens rotate with the authenticated session
[x] Login has a safe pre-authentication CSRF context
[x] No raw token is persisted or logged
[x] Existing and new tests pass
[x] Coverage remains above the documented threshold
[x] No database schema change or drift
[x] Documentation and .env.example updated
[x] Phase boundaries respected
```

## Next phase

Phase 8 implements the administrator layout and metadata CRUD for categories,
tags, software and releases. Every write route must use the Phase 7
`CSRFProtectedAdminSession` dependency.
