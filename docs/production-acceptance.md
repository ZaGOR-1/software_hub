# Production acceptance runbook

This runbook is executed after the release candidate passes CI and before the
public launch in Phase 20. It separates release-candidate evidence from actions
that change the real `software.hotzagor.tech` environment.

## 1. Evidence required before deployment

- CI quality, browser and container workflows are green for the exact commit;
- the RC tag resolves to that commit and the release evidence manifest agrees;
- release archive and evidence-manifest checksums pass independently;
- the persisted Sigstore bundle and GitHub build-provenance attestation ID/URL
  verify for the expected repository;
- `CHANGELOG.md` and the release version agree;
- no uncommitted migration or environment change exists;
- the threat model and security checklist have been reviewed;
- a rollback owner and maintenance window are assigned.

## 2. Fresh-host rehearsal

Use a disposable Ubuntu Server VM with the same architecture as production.

```text
1. Install current security updates.
2. Install Docker Engine and Compose plugin.
3. Clone or extract the exact release candidate.
4. Copy .env.production.example to .env.production.
5. Set strong secrets, domain, trusted hosts and absolute roots.
6. Run scripts/prepare-host.sh as root.
7. Validate both Compose configurations.
8. Build the images with --pull.
9. Apply migrations on an empty SQLite database.
10. Create the first administrator through the CLI.
11. Start the stack and verify container health.
```

Commands are documented in [DEPLOYMENT.md](../DEPLOYMENT.md).

## 3. DNS and TLS rehearsal

Before changing the real DNS record, use a test hostname or `/etc/hosts` mapping.
Verify:

- HTTP redirects to HTTPS;
- certificate name and chain are correct;
- TLS renewal dry-run succeeds;
- HSTS is enabled only after HTTPS is confirmed;
- canonical and Open Graph URLs use the configured public origin;
- direct internal, database, backup and dotfile paths are inaccessible.

## 4. Administration network policy

Production Nginx is fail-closed for `/admin`. Mount exactly one reviewed access
policy:

- WireGuard subnet allowlist, preferred;
- fixed management IP allowlist;
- a private internal hostname reachable only through the VPN.

Confirm that an Internet client receives `403` and the authorized management
client reaches the login page.

## 5. Functional acceptance

Perform the complete workflow with a harmless synthetic ZIP:

```text
login
→ create category
→ create software
→ create stable release
→ upload synthetic ZIP
→ inspect quarantine metadata and SHA-256
→ publish
→ open public page
→ full download
→ Range download
→ HEAD request
→ disable
→ verify generic 404
```

Verify that FastAPI logs authorization and Nginx serves the bytes. Confirm that
HEAD does not increment successful counters.

## 6. Backup and disaster-recovery rehearsal

```bash
python -m app.cli create-backup
python -m app.cli list-backups
python -m app.cli verify-backup --backup-id <BACKUP_ID>
```

Copy the backup to a second disposable VM or isolated root. Restore it using
[BACKUP_RESTORE.md](../BACKUP_RESTORE.md), apply migrations, create no new data,
then verify:

- administrator login;
- catalog metadata;
- physical file SHA-256;
- `verify-storage` reports no mismatches;
- `/health` is green.

A backup located only on the production disk does not satisfy acceptance.

## 7. Update and rollback rehearsal

1. Create a pre-deploy backup.
2. Deploy a no-op rebuild or the RC over the rehearsal installation.
3. Confirm migrations and health.
4. Run the critical public/admin smoke flow.
5. Execute `scripts/rollback.sh <backup-id>`.
6. Confirm database, storage, health and login after rollback.

If a migration cannot be safely downgraded, rollback must restore the pre-deploy
backup together with the previous image/tag.

## 8. Operational acceptance

Confirm:

- disk reserve is above the configured threshold;
- Docker log rotation is active;
- certificate renewal is scheduled and observable;
- daily database backup is scheduled;
- storage/offsite backup schedule is defined;
- backup retention is configured;
- alert ownership exists for health, disk and certificate failure;
- `show-system-status`, `verify-storage` and temporary cleanup run successfully.

## 9. Go/no-go record

Record the exact commit/tag, immutable workflow artifact ID, attestation
verification output, image digests, backup ID, DNS target, certificate expiry,
CI run URLs, test operator and result of every release-checklist item in
`docs/release-candidate.md` or an external immutable release record.

Phase 19 may mark the code as a release candidate. Only Phase 20 may mark the
real domain as launched.
