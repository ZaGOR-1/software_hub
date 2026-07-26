# Phase 11 completion review

## Objective

Implement review, integrity verification, publication, disable/archive/restore and
separate metadata/permanent deletion workflows for `ReleaseFile`, while preserving
private storage isolation and compensating filesystem/database partial failures.

## Delivered

- manual quarantine approve, reject and reopen actions;
- infected-file approval prevention;
- private physical-file state inspection;
- bounded SHA-256 and size verification;
- strict publication readiness checks;
- atomic quarantine-to-software publication move;
- rollback move when the publication transaction fails;
- disable and archive without byte deletion;
- restore-to-ready with software-to-quarantine compensation;
- metadata-only deletion with explicit orphan semantics;
- permanent deletion through private staging;
- physical-file restore when permanent-delete DB transaction fails;
- explicit `DELETE METADATA` and `DELETE FILE` confirmation phrases;
- public URL preview without enabling the public endpoint;
- new audit actions for every lifecycle mutation;
- CSRF inventory coverage for all new unsafe routes;
- service, HTTP workflow, failure-injection and tamper tests.

## Database

No schema migration was required. Existing `ReleaseFile` fields are sufficient.
Alembic head remains:

```text
0002_phase4_domain_schema
```

## Verification

```text
pytest:                         407 passed
branch-aware coverage:         94.04%
warnings:                       0
Python compileall:              passed
function annotation audit:      passed
Python lines over 100 chars:    0
CSRF unsafe-route inventory:    passed
publish + checksum flow:        passed
publish DB rollback restore:    passed
disable/archive/restore flow:   passed
metadata-only orphan policy:    passed
permanent deletion flow:        passed
permanent-delete DB restore:    passed
duplicate physical roots:       fail-closed passed
infected approval prevention:   passed
final unlink failure handling:  passed
Alembic upgrade/check:          passed
Alembic downgrade/re-upgrade:   passed
Alembic schema drift:           none
Jinja templates compiled:       27
Markdown internal links:        49 passed
uv export --frozen --no-dev:    passed
Uvicorn lifecycle smoke:        passed
published physical mode:        0640
```

## Key decisions

- `ready` always returns to quarantine before republishing.
- Publication recalculates SHA-256 rather than trusting upload-time metadata.
- Published files must be disabled or archived before either delete action.
- Metadata-only deletion intentionally preserves bytes and documents the orphan.
- Permanent deletion stages bytes before committing metadata deletion.
- Final staged unlink failure is surfaced as operator attention, not silently
  ignored.

## Deferred to Phase 12

- public UUID download route;
- complete software/release/file visibility authorization chain;
- HEAD semantics and counters;
- Nginx `internal` protected-download location;
- `X-Accel-Redirect` and range/resume behavior;
- public download rate limiting.

## Environment limitation

The local sandbox runs Python 3.13.5 while the project target remains Python 3.14.
Ruff, mypy, Bandit and pip-audit are not present in the offline tool cache and
remain mandatory GitHub Actions quality gates. The lock graph was verified through
`uv export --frozen --no-dev`.
