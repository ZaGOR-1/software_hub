#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "${project_root}"

python_bin="${PYTHON:-python}"
runtime=$(mktemp -d "${TMPDIR:-/tmp}/software-hub-rc.XXXXXX")
uvicorn_pid=""

cleanup() {
    if [ -n "${uvicorn_pid}" ]; then
        kill "${uvicorn_pid}" 2>/dev/null || true
        wait "${uvicorn_pid}" 2>/dev/null || true
    fi
    rm -rf "${runtime}"
}
trap cleanup EXIT HUP INT TERM

mkdir -p \
    "${runtime}/database" \
    "${runtime}/storage/software" \
    "${runtime}/storage/icons" \
    "${runtime}/storage/import" \
    "${runtime}/storage/temporary" \
    "${runtime}/storage/quarantine" \
    "${runtime}/backups"

port=$(${python_bin} - <<'PY'
import socket

with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)

export SOFTWARE_HUB_APP_ENVIRONMENT=test
export SOFTWARE_HUB_APP_DEBUG=false
export SOFTWARE_HUB_DOCS_ENABLED=false
export SOFTWARE_HUB_APP_SECRET_KEY='phase19-app-secret-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ'
export SOFTWARE_HUB_CSRF_SECRET='phase19-csrf-secret-9876543210-ZYXWVUTSRQPONMLKJIHGFEDCBA'
export SOFTWARE_HUB_DATABASE_URL="sqlite+pysqlite:////${runtime#/}/database/software-hub.db"
export SOFTWARE_HUB_PUBLIC_BASE_URL="http://127.0.0.1:${port}"
export SOFTWARE_HUB_TRUSTED_HOSTS='127.0.0.1,localhost'
export SOFTWARE_HUB_TRUSTED_PROXY_NETWORKS='127.0.0.1/32'
export SOFTWARE_HUB_STORAGE_ROOT="${runtime}/storage"
export SOFTWARE_HUB_TEMPORARY_ROOT="${runtime}/storage/temporary"
export SOFTWARE_HUB_QUARANTINE_ROOT="${runtime}/storage/quarantine"
export SOFTWARE_HUB_ICONS_ROOT="${runtime}/storage/icons"
export SOFTWARE_HUB_BACKUP_ROOT="${runtime}/backups"
export SOFTWARE_HUB_STORAGE_MIN_FREE_BYTES=0
export SOFTWARE_HUB_BACKUP_MIN_FREE_BYTES=0
export SOFTWARE_HUB_ADMIN_PASSWORD='Phase19-Rehearsal-Admin-Password-4827!'

${python_bin} -m alembic upgrade head >/dev/null
${python_bin} -m alembic downgrade base >/dev/null
${python_bin} -m alembic upgrade head >/dev/null
${python_bin} -m alembic check >/dev/null

${python_bin} -m app.cli create-admin --username rc-admin >/dev/null
backup_json=$(${python_bin} -m app.cli create-backup)
backup_id=$(printf '%s' "${backup_json}" | ${python_bin} -c \
    'import json, sys; print(json.load(sys.stdin)["backup_id"])')
${python_bin} -m app.cli verify-backup --backup-id "${backup_id}" >/dev/null

${python_bin} - <<'PY'
import os
import sqlite3
from pathlib import Path

url = os.environ["SOFTWARE_HUB_DATABASE_URL"]
prefix = "sqlite+pysqlite:///"
path = Path(url.removeprefix(prefix))
with sqlite3.connect(path) as connection:
    connection.execute("UPDATE users SET is_active = 0 WHERE username = ?", ("rc-admin",))
    connection.commit()
PY

${python_bin} -m app.cli restore-backup \
    --backup-id "${backup_id}" --no-safety-backup --yes >/dev/null

${python_bin} - <<'PY'
import os
import sqlite3
from pathlib import Path

url = os.environ["SOFTWARE_HUB_DATABASE_URL"]
path = Path(url.removeprefix("sqlite+pysqlite:///"))
with sqlite3.connect(path) as connection:
    row = connection.execute(
        "SELECT is_active FROM users WHERE username = ?", ("rc-admin",)
    ).fetchone()
if row != (1,):
    raise SystemExit("restored administrator state does not match backup")
PY

${python_bin} -m app.cli verify-storage >/dev/null
${python_bin} -m app.cli show-system-status >/dev/null

${python_bin} -m uvicorn app.main:app \
    --host 127.0.0.1 --port "${port}" --workers 1 --no-access-log \
    >"${runtime}/uvicorn.log" 2>&1 &
uvicorn_pid=$!

${python_bin} - <<'PY'
import json
import os
import time
from urllib.error import URLError
from urllib.request import urlopen

url = os.environ["SOFTWARE_HUB_PUBLIC_BASE_URL"] + "/health"
last_error: Exception | None = None
for _ in range(80):
    try:
        with urlopen(url, timeout=1.0) as response:  # noqa: S310 - loopback rehearsal URL
            payload = json.load(response)
            if response.status == 200 and payload.get("status") == "ok":
                checks = payload.get("checks", {})
                if all(checks.get(name) == "ok" for name in ("database", "storage", "disk")):
                    break
    except (OSError, URLError, ValueError) as exc:
        last_error = exc
    time.sleep(0.1)
else:
    raise SystemExit(f"health rehearsal failed: {last_error}")
PY

kill -INT "${uvicorn_pid}"
wait "${uvicorn_pid}" 2>/dev/null || true
uvicorn_pid=""

${python_bin} - <<PY
import json
print(json.dumps({
    "status": "passed",
    "version": "1.0.0-rc.3",
    "migration": "upgrade-downgrade-reupgrade",
    "administrator_bootstrap": "passed",
    "backup_id": "${backup_id}",
    "restore": "passed",
    "storage_reconciliation": "passed",
    "health": "passed",
}, sort_keys=True))
PY
