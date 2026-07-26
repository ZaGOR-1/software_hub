# Software Hub deployment

This runbook deploys the application as two mandatory containers:

```text
Internet
→ Nginx container (HTTP/TLS, static, limits, X-Accel-Redirect)
→ private Docker backend network
→ FastAPI container (one Uvicorn worker, SQLite, storage services)
```

An optional one-shot Certbot profile manages HTTP-01 certificates. The application
container is never published on a host port.

## 1. Host prerequisites

Recommended Ubuntu Server baseline:

- Docker Engine with the Compose plugin;
- 2 vCPU and 2–4 GiB RAM;
- 20–30 GiB system disk;
- a separate filesystem or virtual disk for `/srv/software-hub/storage` when the
  catalog will contain large installers;
- TCP 80 and 443 open to the public server;
- SSH keys, disabled root login and disabled password authentication;
- WireGuard or an explicit source-IP allowlist for `/admin`.

Do not publish Docker, Proxmox or SSH management ports through the application
reverse proxy.

## 2. Prepare persistent paths

The containers use UID/GID `10001` by default. Create bind mounts before the first
Compose start so Docker does not create root-owned directories:

```bash
sudo SOFTWARE_HUB_DATA_ROOT=/srv/software-hub \
  SOFTWARE_HUB_UID=10001 SOFTWARE_HUB_GID=10001 \
  ./scripts/prepare-host.sh
```

The resulting write boundaries are:

```text
app rw:    database/, storage/, backups/, /tmp tmpfs
nginx ro:  storage/software/, Let's Encrypt data, admin allowlist
nginx rw:  /tmp tmpfs only
certbot:   letsencrypt/, certbot/www/, certbot/logs/, /tmp tmpfs
```

All containers use a read-only root filesystem, drop every Linux capability and
set `no-new-privileges`.

## 3. Production environment

Create a private file and restrict it to the deployment account:

```bash
cp .env.production.example .env.production
chmod 0600 .env.production
```

Replace both secret placeholders with independent high-entropy values. A convenient
command is:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

At minimum, verify:

```text
SOFTWARE_HUB_DOMAIN=software.hotzagor.tech
SOFTWARE_HUB_PUBLIC_BASE_URL=https://software.hotzagor.tech
SOFTWARE_HUB_TRUSTED_HOSTS=software.hotzagor.tech
SOFTWARE_HUB_DATA_ROOT=/srv/software-hub
SOFTWARE_HUB_APP_SECRET_KEY=<unique secret>
SOFTWARE_HUB_CSRF_SECRET=<different unique secret>
```

The example intentionally uses `admin-access-deny.conf`. Admin access remains
blocked until a tested allowlist is configured.

## 4. Configure admin network restriction

WireGuard example:

```bash
cp nginx/snippets/admin-access-wireguard.conf.example \
  deployment-admin-access.conf
chmod 0644 deployment-admin-access.conf
```

Edit the tunnel subnet, then set:

```text
SOFTWARE_HUB_ADMIN_ACCESS_CONF=./deployment-admin-access.conf
```

For a fixed public IP, start from `admin-access-ip.conf.example`. Test from both an
allowed and denied source before relying on the restriction. Keep an SSH recovery
path that does not depend on the web admin panel.

## 5. Bootstrap HTTP and issue a certificate

The first certificate cannot be loaded before it exists. Start the base Compose
file in development Nginx mode on public port 80:

```bash
docker compose --env-file .env.production -f docker-compose.yml \
  up -d --build app nginx
```

Confirm the HTTP challenge path can be reached, then issue the certificate:

```bash
SOFTWARE_HUB_CERTBOT_EMAIL=admin@example.com \
  SOFTWARE_HUB_COMPOSE_ENV_FILE=.env.production \
  ./scripts/certbot.sh issue
```

The Certbot profile runs as UID/GID `10001` and writes only to the prepared
certificate and challenge mounts.

## 6. Start the TLS deployment

```bash
docker compose --env-file .env.production \
  -f docker-compose.yml \
  -f docker-compose.production.yml \
  up -d --build --remove-orphans
```

The production override:

- redirects HTTP to HTTPS with status `308` except ACME challenges;
- listens internally on high port `8443` and maps host port 443;
- enables TLS 1.2/1.3, HSTS, CSP and other security headers;
- disables application docs;
- runs the application in production mode;
- mounts the software download directory and certificates read-only into Nginx.

## 7. Create the administrator

Run the command in a one-shot app container. The password is read from a hidden
prompt or a temporary protected environment variable; never pass it as a command
argument.

```bash
docker compose --env-file .env.production \
  -f docker-compose.yml -f docker-compose.production.yml \
  run --rm --no-deps app python -m app.cli create-admin --username admin
```

## 8. Acceptance checks

```bash
curl -I http://software.hotzagor.tech/
curl --fail https://software.hotzagor.tech/health
curl -I https://software.hotzagor.tech/static/css/public.css
```

Expected properties:

- HTTP redirects to the configured HTTPS domain;
- `/health` reports all four components as `ok`;
- `/protected-downloads/...` is not directly addressable;
- `.env`, database, backup and storage paths return `404`;
- an allowed WireGuard/IP source can open `/admin/login`;
- a denied source receives Nginx access denial;
- uploads larger than the configured 2 GiB limit are rejected by Nginx;
- a published download supports `HEAD` and byte ranges.

## 9. Certificate renewal

```bash
SOFTWARE_HUB_COMPOSE_ENV_FILE=.env.production ./scripts/certbot.sh renew
```

Schedule the command twice daily. Certbot performs renewal only when necessary;
the script reloads Nginx after a successful run. Monitor both the exit status and
the certificate expiry date.

## 10. Updates

Use immutable Git tags or image tags. Before a risky deployment, create and verify
a backup. The helper performs a best-effort pre-deploy backup, builds with fresh
base images, starts the services and checks `/health`:

```bash
SOFTWARE_HUB_COMPOSE_ENV_FILE=.env.production ./scripts/deploy.sh
```

For an initial deployment with no existing image, create the administrator and the
first verified backup immediately after startup.

## 11. Rollback

Keep the previous source/image tag. For a data rollback:

```bash
SOFTWARE_HUB_COMPOSE_ENV_FILE=.env.production \
  ./scripts/rollback.sh <BACKUP_ID>
```

The script stops app/Nginx, runs the tested restore workflow, and starts both
services. A code-only rollback should restore the previous image/source tag and
must not downgrade the database unless that exact downgrade was rehearsed.

## 12. Proxmox notes

Deploy inside a dedicated Ubuntu Server VM, preferably in a DMZ or isolated VLAN.
Do not expose the Proxmox GUI or management network. Use a separate virtual disk or
mount for storage and include both application-level backups and hypervisor-level
backups. A VM snapshot is not a replacement for the SQLite-aware backup workflow.

## 13. Release-candidate rehearsal

Before touching the real DNS record, run the code-level rehearsal in the locked
Python environment:

```bash
PYTHON="$PWD/.venv/bin/python" ./scripts/rehearse-release-candidate.sh
```

It performs a clean migration, downgrade/re-upgrade, administrator bootstrap,
online backup, manifest verification, deliberate database mutation, restore,
storage reconciliation and a real Uvicorn health check in an isolated temporary
root.

Run the complete quality wrapper in a network-enabled environment:

```bash
./scripts/verify-release-candidate.sh
```

A production-like Compose build/runtime smoke remains mandatory in GitHub Actions
or on a disposable Ubuntu host because the rehearsal script does not emulate the
Docker daemon, certificate authority, firewall or real DNS.

## 14. VPS-specific notes

For a VPS, confirm that the provider firewall and `ufw`/nftables agree. Expose
only `80/tcp`, `443/tcp` and a restricted SSH source. Store `/srv/software-hub`
on persistent storage that survives VM rebuilds, and send verified backups to a
different provider, account or host.

Do not use provider snapshots as the only backup: they may capture SQLite WAL and
application storage at different moments and are commonly stored in the same
failure domain.

## 15. Production acceptance boundary

This deployment guide prepares the host. The go/no-go sequence, disaster-recovery
rehearsal and evidence record are in
[`docs/production-acceptance.md`](docs/production-acceptance.md). Phase 19 creates
a release candidate; Phase 20 performs the real deployment and domain acceptance.
