# syntax=docker/dockerfile:1.7

ARG PYTHON_IMAGE=python:3.14.6-slim-bookworm
ARG UV_VERSION=0.10.0

FROM ${PYTHON_IMAGE} AS dependency-builder
ARG UV_VERSION
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_NO_PROGRESS=1
WORKDIR /build

RUN python -m pip install --no-cache-dir "uv==${UV_VERSION}"
COPY pyproject.toml uv.lock ./
RUN uv export \
      --frozen \
      --no-dev \
      --no-emit-project \
      --format requirements.txt \
      --output-file requirements.txt \
    && python -m venv /opt/software-hub/venv \
    && /opt/software-hub/venv/bin/python -m pip install \
      --no-cache-dir \
      --require-hashes \
      --requirement requirements.txt

FROM ${PYTHON_IMAGE} AS runtime
ARG APP_UID=10001
ARG APP_GID=10001

ENV PATH=/opt/software-hub/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONFAULTHANDLER=1 \
    SOFTWARE_HUB_FORWARDED_ALLOW_IPS=172.30.0.10 \
    SOFTWARE_HUB_RUN_MIGRATIONS=true

RUN groupadd --gid "${APP_GID}" softwarehub \
    && useradd \
      --uid "${APP_UID}" \
      --gid "${APP_GID}" \
      --home-dir /nonexistent \
      --no-create-home \
      --shell /usr/sbin/nologin \
      softwarehub \
    && mkdir -p /app /srv/software-hub/database /srv/software-hub/storage /srv/software-hub/backups \
    && chown -R softwarehub:softwarehub /app /srv/software-hub

WORKDIR /app
COPY --from=dependency-builder /opt/software-hub/venv /opt/software-hub/venv
COPY --chown=softwarehub:softwarehub app ./app
COPY --chown=softwarehub:softwarehub alembic ./alembic
COPY --chown=softwarehub:softwarehub alembic.ini ./alembic.ini
COPY --chown=softwarehub:softwarehub docker/app-entrypoint.sh /usr/local/bin/software-hub-entrypoint
COPY --chown=softwarehub:softwarehub docker/healthcheck.py /usr/local/bin/software-hub-healthcheck.py

RUN chmod 0555 /usr/local/bin/software-hub-entrypoint \
    && chmod 0444 /usr/local/bin/software-hub-healthcheck.py

USER softwarehub:softwarehub
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "/usr/local/bin/software-hub-healthcheck.py"]

ENTRYPOINT ["/usr/local/bin/software-hub-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--no-access-log", "--timeout-graceful-shutdown", "25"]
