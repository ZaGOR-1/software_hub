# Local development guide

## Prerequisites

- Git;
- `uv`;
- Python 3.14 installed through `uv`;
- optional Nginx for local protected-download testing;
- optional Node.js and Playwright only for browser/accessibility work.

## Bootstrap

```bash
git clone <repository>
cd software-hub
uv python install 3.14
uv sync --all-groups --locked
cp .env.example .env
./scripts/prepare-local.sh
```

Generate separate local secrets and add them to `.env`:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(48))'
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Use absolute runtime paths. The default local runtime created by
`prepare-local.sh` is `.runtime`; update `SOFTWARE_HUB_DATABASE_URL` and all
storage roots accordingly.

## Database and administrator

```bash
uv run alembic upgrade head
SOFTWARE_HUB_ADMIN_PASSWORD='use-a-long-local-password' \
  uv run python -m app.cli create-admin --username admin
```

Remove the temporary password variable from the shell after the command.

## Start the application

```bash
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. The application can be developed without Nginx,
but protected download responses contain `X-Accel-Redirect`; use the local
Compose/Nginx path to test actual file bytes and Range requests.

## Local Compose

```bash
cp .env.example .env
./scripts/prepare-local.sh
SOFTWARE_HUB_UID=$(id -u) SOFTWARE_HUB_GID=$(id -g) \
  docker compose up --build
```

The development edge listens on `http://127.0.0.1:8080`.

## Quality commands

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uvx --from 'bandit[toml]==1.9.4' bandit -c pyproject.toml -r app
uvx --from 'pip-audit==2.10.1' pip-audit
```

The regression suite excludes opt-in browser tests. For the browser matrix:

```bash
npm install --no-save --package-lock=false --ignore-scripts axe-core@4.11.4
uv run --with 'playwright==1.61.0' playwright install chromium firefox webkit
SOFTWARE_HUB_RUN_E2E=1 \
SOFTWARE_HUB_E2E_BROWSERS=chromium,firefox,webkit \
AXE_CORE_PATH="$PWD/node_modules/axe-core/axe.min.js" \
uv run --with 'playwright==1.61.0' \
  pytest -o addopts='' -m e2e tests/e2e -q
```

## Migrations

Create a migration only when ORM metadata changes:

```bash
uv run alembic revision --autogenerate -m 'describe change'
uv run alembic upgrade head
uv run alembic check
```

Review generated SQL and downgrade behavior. Do not edit an already released
migration.

## Test data and files

Use only synthetic fixtures. Do not commit installer binaries, SQLite databases,
secrets, backups, Playwright videos or generated runtime directories.

## Common local failures

### Startup rejects paths

All database and storage paths must be absolute and non-overlapping. Run
`prepare-local.sh`, then verify the `.env` paths.

### Login POST returns 403

Open the login page first so the signed pre-authentication CSRF cookie and form
token are generated.

### Download response has no file body

This is expected without Nginx. FastAPI authorizes the request and emits
`X-Accel-Redirect`; Nginx serves the bytes.

### SQLite is locked

Ensure only one application instance/worker is running. Do not keep manual
write transactions open. WAL and busy timeout are not a substitute for long
transactions.
