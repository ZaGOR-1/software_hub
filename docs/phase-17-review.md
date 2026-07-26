# Phase 17 review

## Scope completed

Phase 17 packages the Phase 16 application into hardened Docker and Nginx units.
No domain model or database migration changed.

Created or substantially replaced:

```text
Dockerfile
docker/app-entrypoint.sh
docker/healthcheck.py
docker/nginx-entrypoint.sh
docker/nginx-healthcheck.sh
nginx/Dockerfile
nginx/nginx.conf
nginx/templates/development.conf.template
nginx/templates/production.conf.template
nginx/snippets/*
docker-compose.yml
docker-compose.production.yml
.env.production.example
scripts/prepare-host.sh
scripts/prepare-local.sh
scripts/deploy.sh
scripts/rollback.sh
scripts/certbot.sh
DEPLOYMENT.md
SECURITY.md
docs/container-deployment.md
.github/workflows/container-build.yml
```

## Security decisions

- App, Nginx and optional Certbot use non-root UID/GID `10001`.
- App and Nginx root filesystems are read-only.
- Every container drops all capabilities and forbids privilege escalation.
- The app has no published port and joins only an internal backend network.
- Nginx reads only permanent published files, never quarantine or SQLite.
- Production admin access defaults to `deny all` until an allowlist is selected.
- Proxy trust is tied to one fixed internal Nginx address.
- TLS and security headers are owned by Nginx in Compose deployments.
- Certificates and production secrets are bind-mounted or environment-provided,
  never copied into images.

## Verification completed locally

- `491` pytest tests passed;
- branch-aware coverage reached `92.82%` and passed the configured threshold;
- Python compile and function-annotation checks;
- shell syntax checks;
- YAML/TOML parsing;
- `uv export --frozen --no-dev --no-emit-project`;
- development and production Nginx template rendering;
- `nginx -t` for both rendered configurations;
- a real local Uvicorn → Nginx development smoke test;
- a real local Uvicorn → TLS Nginx production-template smoke test;
- HTTP `308`, HTTPS health, HSTS, CSP, request ID and fail-closed `/admin` behavior;
- no Docker socket, privileged mode, host network or root service user;
- read-only Nginx software and certificate mounts;
- internal download location never aliases quarantine;
- Nginx healthcheck uses `GET`, not `HEAD`, because `/health` is a GET endpoint.

Docker Engine is not installed in the execution sandbox, so actual image build,
Compose startup and container-runtime execution are not claimed as locally passed.
The CI workflow validates the Compose model and builds both images on every push
and pull request. Full Trivy image scanning remains Phase 18.

## Known operational constraints

- Host directories must be prepared before Compose startup.
- TLS production mode cannot start until a readable certificate exists; bootstrap
  uses base HTTP mode and the optional Certbot profile.
- The fixed default backend subnet may need adjustment on hosts with an overlapping
  route.
- The deployment helper's pre-deploy backup is best effort for first deployment;
  operators must verify a backup before subsequent risky updates.
