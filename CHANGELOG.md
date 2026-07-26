# Changelog

All notable changes to Software Hub are documented here. The format follows
Keep a Changelog principles and semantic versioning.

## [1.0.0-rc.1] - 2026-07-26

First release candidate of the production-ready MVP.

### Added

- public Ukrainian software catalog, search, categories, tags and release history;
- administrator CRUD for categories, tags, software, releases and release files;
- Argon2id authentication, server-side sessions, lockout, rotation and revocation;
- pre-authentication and session-bound CSRF protection;
- quarantine-based upload with bounded multipart handling, SHA-256 and file
  signature assessment for EXE, MSI, ZIP and 7z;
- optional non-blocking ClamAV adapter;
- compensated publish, disable, archive, restore and deletion workflows;
- protected Nginx downloads through `X-Accel-Redirect`, Range support and daily
  aggregate statistics;
- light, dark and system themes, accessibility hardening, canonical/Open Graph
  metadata and a public-only sitemap;
- structured logs, request IDs, audit log, dashboard and bounded health checks;
- SQLite online backup, manifest verification, staged restore, retention and
  filesystem reconciliation;
- hardened non-root Docker Compose deployment with TLS-ready Nginx and optional
  Certbot;
- Ruff, strict mypy, pytest coverage, Bandit, pip-audit, Playwright/axe, Docker
  build and Trivy CI quality gates;
- architecture, security, deployment, recovery, operations and production
  acceptance runbooks.

### Security

- storage is outside the public web root;
- physical paths are never accepted from users or exposed in responses;
- production administration access is fail-closed until a VPN/IP allowlist is
  configured;
- secrets, cookies, passwords, CSRF values and physical paths are removed from
  structured logging and audit metadata;
- containers run without root, privileged mode, host networking or Docker socket
  access.

### Known limitations

- the MVP supports SQLite and one application instance only;
- download statistics count authorized GET starts, not completed transfers;
- malware scanning is optional and disabled by default;
- no public registration, public REST API, automatic URL import, archive
  extraction, object storage or CDN is included;
- final production acceptance on `software.hotzagor.tech` is Phase 20 and is not
  claimed by this release candidate.

[1.0.0-rc.1]: docs/release-candidate.md
