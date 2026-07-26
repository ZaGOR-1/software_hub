# Phase 19 review — documentation and release candidate

**Version:** `1.0.0-rc.3`
**Date:** 2026-07-26
**Status:** completed as a code-level release candidate

## Scope completed

Phase 19 turned the implemented MVP into a maintainable release candidate rather
than adding new catalog features. The phase completed:

- root architecture documentation based on the actual source tree;
- semantic-version changelog and RC known limitations;
- complete environment-variable reference;
- local development guide;
- production acceptance and go/no-go runbook;
- reviewed security model and threat model;
- release-candidate evidence record;
- deterministic migration/admin/backup/restore/health rehearsal;
- release-tag workflow that produces an evidence bundle and source checksum;
- version synchronization across Python, package metadata and `uv.lock`;
- correction of the runtime dependency declaration in `pyproject.toml`.

No database schema or business behavior changed. Alembic head remains
`0002_phase4_domain_schema`.

## Important correction

The committed `uv.lock` correctly listed Alembic, Argon2, SQLAlchemy and
`python-multipart`, but the Phase 18 `pyproject.toml` runtime dependency list had
lost those declarations. Phase 19 restored the complete dependency list and
added an automated equality check against lock metadata. Without this correction,
a clean project install could omit required runtime packages even though an
older environment continued to work.

## Release-candidate rehearsal

`scripts/rehearse-release-candidate.sh` creates an isolated temporary runtime and
performs:

```text
clean Alembic upgrade
→ downgrade to base
→ re-upgrade to head
→ schema drift check
→ administrator bootstrap
→ online backup
→ manifest and SQLite integrity verification
→ deliberate administrator-state mutation
→ staged restore
→ restored-state assertion
→ storage reconciliation
→ real Uvicorn health request
```

The final rehearsal returned `status: passed`, version `1.0.0-rc.3`, and passed
all migration, administrator, backup, restore, reconciliation and health steps.
The temporary database, storage and backup were removed after execution.

## Verification results

```text
Regression tests:               503 passed
Opt-in browser tests:           10 skipped locally by design
Branch-aware coverage:          92.82%
Coverage threshold:             passed (90%)
Warnings:                       0
Phase 18/19 infrastructure:     12 passed
Release-candidate rehearsal:    passed
Python compileall:              passed
Shell syntax:                   passed
TOML/YAML parsing:              passed
Jinja compilation:              passed
Theme JavaScript runtime:       passed
Alembic upgrade/downgrade:      passed in rehearsal
Alembic schema drift:           absent
Runtime dependency alignment:   passed
Version consistency:            passed
```

## Environment limitations

The sandbox contains Python 3.13.5 while the target is Python 3.14. It has no
network access to download the managed Python 3.14 build. Therefore local
`uv lock --check`, frozen export on the target interpreter, Ruff, mypy, Bandit,
pip-audit, Docker builds, Trivy and the Playwright browser matrix are not claimed
as locally executed in Phase 19.

They are blocking steps in the four tag workflows:

- CI;
- Browser E2E;
- Container Build and Scan;
- Release Candidate Evidence.

## Security review

The threat model was reviewed against the final Nginx/FastAPI/container and
backup topology. No new trust boundary was introduced. The remaining risks are
environment-specific: real DNS/TLS, firewall, administrator VPN/IP policy,
offsite backup, alert delivery and host compromise.

Production administration remains fail-closed. The release candidate does not
change the real domain and must not be described as production-launched.

## Definition of done

- [x] README and documentation index updated.
- [x] ARCHITECTURE, CHANGELOG and environment reference created.
- [x] Deployment, security, operations and recovery runbooks completed.
- [x] VPS and Proxmox guidance present.
- [x] DNS, TLS, certificate renewal and admin allowlist documented.
- [x] Update and rollback procedures documented.
- [x] Common failures and disk/backup monitoring documented.
- [x] Threat model reviewed.
- [x] Release checklist extended with evidence requirements.
- [x] Clean migration rehearsal passed.
- [x] Fresh administrator bootstrap passed.
- [x] Backup/restore rehearsal passed.
- [x] Health and storage reconciliation passed.
- [x] Version and dependency metadata synchronized.
- [x] Production launch explicitly deferred to Phase 20.

## Result

Software Hub is prepared as **`1.0.0-rc.3`**. The code-level release candidate
is ready to be tagged and subjected to all blocking GitHub Actions gates. A real
production deployment and acceptance record remain Phase 20.
