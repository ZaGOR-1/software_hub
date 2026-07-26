# Software Hub security model

## Container boundary

The application and Nginx images run as UID/GID `10001`; the optional Certbot
container uses the same unprivileged identity. Compose applies:

```text
read_only: true
cap_drop: ALL
security_opt: no-new-privileges:true
init: true
no privileged mode
no host network
no Docker socket
```

The application has no host port and is reachable only from the internal Docker
backend network. Nginx has a fixed backend address, and both Uvicorn and the
application proxy middleware trust only that address for forwarding headers.

## Filesystem boundary

The app receives write access only to:

- SQLite database directory;
- managed private storage;
- backup directory;
- bounded `/tmp` tmpfs.

Nginx receives read-only access only to permanent published software, the admin
allowlist and certificate data. It cannot read quarantine, temporary uploads,
SQLite or backups. Static assets are copied into the Nginx image at build time.

## Reverse-proxy boundary

Nginx owns production browser headers and hides equivalent upstream headers to
avoid duplicates. It enforces:

- TLS 1.2 and TLS 1.3;
- HTTP-to-HTTPS redirect;
- HSTS after TLS deployment;
- CSP without `unsafe-inline`;
- `nosniff`, referrer, permissions and framing policies;
- login, general and download rate limits;
- per-IP connection limits;
- 2 GiB request-body limit;
- disabled proxy request buffering on the upload endpoint;
- direct denial of dotfiles and internal data paths;
- `internal` protected-download location;
- no directory listing and no server version disclosure.

## Admin access

The production example is fail-closed and denies every `/admin` request. Replace it
with a WireGuard or explicit IP allowlist. Authentication, Argon2id, server-side
sessions, lockout and CSRF remain mandatory even behind the network restriction.

## Secrets

Production secrets live only in a mode-`0600` environment file or an external
secret manager. They are never copied into either image. The application fails
startup when secrets are missing, weak, equal, or when the public URL/trusted host
contract is invalid.

## Image and dependency policy

The Dockerfiles use exact patch-level base image tags. CI must rebuild with `--pull`
and scan the produced images before production. A changed base-image digest is
reviewed like any dependency update. Critical findings require remediation or a
written, time-bounded exception.

## Residual risks

- Docker bind-mount permissions are a host responsibility; run `prepare-host.sh`
  before Compose.
- Fixed Docker backend addresses can conflict with an existing host subnet; change
  the entire subnet and both addresses together.
- Nginx counts an authorized download start, not completed transfer; completion
  analytics require a separate bounded log-processing design.
- Certbot renewal and Nginx reload require host scheduling and monitoring.
- Container isolation does not replace host patching, SSH hardening, firewalling,
  offsite backups or Proxmox network isolation.

## Release-candidate security acceptance

Release `1.0.0-rc.2` is a code-level release candidate, not a claim that the real
production domain has passed acceptance. The candidate contains automated gates
for authentication, CSRF, authorization, upload/download boundaries, backup
integrity, container configuration, browser accessibility and dependency/image
scanning.

Before Phase 20, the operator must still provide environment-specific evidence:

- the exact CI commit passed all four workflows;
- the production `/admin` policy allows only the approved VPN/IP source;
- real TLS issuance and renewal succeed;
- the host firewall exposes only required services;
- offsite backup and isolated restore have been demonstrated;
- no HIGH/CRITICAL scan exception is accepted without a written expiry and owner;
- production secrets are unique, persistent and stored outside Git;
- container image digests and the source artifact checksum are recorded.

The authoritative checklists are
[`docs/release-checklist.md`](docs/release-checklist.md) and
[`docs/production-acceptance.md`](docs/production-acceptance.md).
