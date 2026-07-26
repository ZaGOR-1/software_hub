# Software Hub `1.0.0-rc.3` release-candidate evidence

**Prepared:** 2026-07-26
**Scope:** code and documentation readiness after Phases 0–19
**Production status:** not deployed; Phase 20 remains required

## Decision

The repository is a **code-level release candidate**. It is suitable for tagging
and running the blocking CI/release workflows. It is not yet approved as the
live `software.hotzagor.tech` production service.

```text
Code-level RC: conditional GO after all tag workflows are green
Production launch: NO-GO until Phase 20 acceptance
```

## Local evidence

The following checks were executed in the available sandbox:

| Check | Result |
|---|---|
| Version/package/lock consistency | passed |
| Runtime dependency declaration vs lock metadata | passed |
| Phase 19 documentation invariants | passed |
| Clean Alembic upgrade | passed |
| Alembic downgrade to base and re-upgrade | passed |
| Alembic schema drift check | passed |
| Administrator bootstrap through CLI | passed |
| Online backup creation and verification | passed |
| Deliberate SQLite mutation and restore | passed |
| Storage reconciliation after restore | passed |
| Real Uvicorn `/health` check | passed |
| Regression test suite | recorded in `docs/phase-19-review.md` |

The deterministic rehearsal command is:

```bash
PYTHON="$PWD/.venv/bin/python" ./scripts/rehearse-release-candidate.sh
```

It returned a JSON result containing `status: passed` and an isolated backup ID.
The temporary runtime and backup were removed after the test.

## Blocking tag workflows

Tag `v1.0.0-rc.3` must pass all of the following:

1. **CI** — lock check, frozen sync/export, pre-commit, Ruff, strict mypy,
   pytest/coverage, Bandit and pip-audit.
2. **Browser E2E** — Chromium, Firefox and WebKit full flow with axe-core.
3. **Container Build and Scan** — Compose validation, app/Nginx build, Trivy and
   non-root runtime health smoke.
4. **Release Candidate Evidence** — exact RC tag validation, documentation
   invariants, isolated migration/admin/backup/restore rehearsal, deterministic
   source archive, SHA-256 evidence manifest and signed GitHub build provenance.

No `continue-on-error` is allowed for a blocking security or correctness gate.

## Immutable evidence and provenance

The release-candidate workflow succeeds only when the workflow ref is the exact
`v<app version>` tag and that tag resolves to `GITHUB_SHA`. It creates the source
archive from the committed Git tree with `git archive | gzip -n`, so a rebuild of
the same commit produces the same archive bytes.

The uploaded artifact is uniquely named with the commit SHA and workflow attempt.
It contains:

- `software-hub-<version>.tar.gz`;
- the archive SHA-256 file;
- `evidence-manifest.json`, binding version, tag, commit, repository, workflow and
  GitHub Actions run URL to the archive digest;
- the manifest SHA-256 file;
- the isolated migration/admin/backup/restore rehearsal JSON;
- the signed Sigstore provenance bundle, its checksum and an attestation reference
  containing the immutable GitHub attestation ID and URL.

GitHub signs a SLSA build-provenance attestation for the archive, both checksum
records, the evidence manifest and rehearsal result. Verify the downloaded
evidence before promotion:

```bash
sha256sum --check software-hub-1.0.0-rc.3.tar.gz.sha256
sha256sum --check evidence-manifest.json.sha256
gh attestation verify software-hub-1.0.0-rc.3.tar.gz \
  --repo OWNER/software_hub
```

The tag workflow URL, artifact ID and attestation verification output are part of
the Phase 20 acceptance record. A manually copied archive without this evidence
is not a promotable release candidate.

GitHub artifact attestations are available for public repositories on current
plans; private/internal repositories require GitHub Enterprise Cloud. The
workflow intentionally fails closed if the repository is not eligible. In that
case release engineering must enable an eligible plan or implement and review an
approved Sigstore signer before creating the RC tag; the attestation gate must
not be removed or marked non-blocking.

## Environment-specific evidence still required

Phase 20 must record:

- production host and firewall configuration;
- real DNS target;
- TLS certificate issuance and renewal;
- WireGuard/IP administration allowlist behavior;
- source artifact checksum and container image digests;
- full upload/publish/download/disable flow on the deployed stack;
- first production backup ID;
- isolated/offsite restore result;
- monitoring and alert ownership;
- rollback operator and maintenance window.

## Known release-candidate limitations

- SQLite supports one application instance and one Uvicorn worker.
- Download statistics record authorized GET starts rather than completed
  transfers.
- ClamAV is optional and disabled by default.
- The release contains no public registration, public REST API, object storage,
  CDN, automatic URL importer or archive extraction.
- Local browser and Docker evidence may be unavailable in constrained sandboxes;
  the GitHub workflows remain authoritative for those gates.

## Artifact policy

The release source archive must exclude:

- `.env` and production secrets;
- SQLite/WAL files;
- persistent storage and backups;
- virtual environments and caches;
- browser videos/screenshots except separately retained failure evidence.

The archive SHA-256, provenance verification output, immutable workflow artifact
ID and image digests belong in the final immutable release record.

## Related documents

- [Architecture](../ARCHITECTURE.md)
- [Changelog](../CHANGELOG.md)
- [Security model](../SECURITY.md)
- [Deployment](../DEPLOYMENT.md)
- [Backup and restore](../BACKUP_RESTORE.md)
- [Production acceptance](production-acceptance.md)
- [Release checklist](release-checklist.md)
