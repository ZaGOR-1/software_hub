"""Container health probe using only the Python standard library."""

from __future__ import annotations

import json
import os
import sys
from http.client import HTTPConnection


def main() -> int:
    """Return zero only when the local readiness endpoint is fully healthy."""

    host = os.environ.get("SOFTWARE_HUB_HEALTHCHECK_HOST", "127.0.0.1")
    port = int(os.environ.get("SOFTWARE_HUB_HEALTHCHECK_PORT", "8000"))
    path = os.environ.get("SOFTWARE_HUB_HEALTHCHECK_PATH", "/health")
    host_header = os.environ.get("SOFTWARE_HUB_HEALTHCHECK_HOST_HEADER", "localhost")

    connection = HTTPConnection(host, port, timeout=4)
    try:
        connection.request("GET", path, headers={"Host": host_header})
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
    except OSError, ValueError:
        return 1
    finally:
        connection.close()

    checks = payload.get("checks", {})
    expected = {"application", "database", "storage", "disk"}
    if response.status != 200 or payload.get("status") != "ok":
        return 1
    if set(checks) != expected or any(checks[name] != "ok" for name in expected):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
