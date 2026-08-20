# Shared build stage for the API and the report worker (same codebase, different CMD).
FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
      curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /usr/local/bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY packages/engine-numerology packages/engine-numerology
COPY packages/engine-interpretation packages/engine-interpretation
COPY packages/engine-astrology packages/engine-astrology
COPY apps/api apps/api
COPY knowledge knowledge

# A bare `uv sync` at the workspace root only syncs the *root* project -- here an
# empty placeholder (`dependencies = []` in the top-level pyproject.toml) -- NOT the
# workspace members copied above. Confirmed the hard way: a real `docker compose up`
# (release-closure Gate C) found `alembic`/`uvicorn` missing from $PATH and
# `numra_api`/`fastapi` unimportable in the built image, because this line used to
# read plain `uv sync --frozen --no-dev` with no member packages actually installed.
# `--all-packages` is the real fix -- it syncs every workspace member's own
# dependencies into the shared venv. (`uv sync --package` repeated per-package, the
# very first form of this line, is also wrong for a different reason: uv 0.5.11
# rejects passing `--package` more than once outright.)
RUN uv sync --frozen --no-dev --all-packages

RUN addgroup --system numra && adduser --system --ingroup numra numra

# The compose `numra_exports_data` named volume mounts onto /app/data/exports. Docker
# only initializes a named volume's ownership from what already exists at that path
# in the image at first mount -- if the path doesn't pre-exist here, Docker still
# auto-creates the mountpoint, but as root:root, which the non-root `numra` user below
# then can't write into (LocalExportStorage's own `mkdir(exist_ok=True)` at startup
# silently no-ops since the directory already exists, so it never surfaces a build-time
# error, only a runtime PermissionError on the first export). Confirmed the hard way
# via a real docker-compose-e2e run: POST /v1/exports 500'd with
# "PermissionError: [Errno 13] Permission denied: '/app/data/exports/<id>.pdf'".
RUN mkdir -p /app/data/exports && chown -R numra:numra /app/data
USER numra

ENV PATH="/app/.venv/bin:$PATH"

FROM base AS api
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 \
  CMD curl --fail http://127.0.0.1:8000/v1/health/ready || exit 1
CMD ["uvicorn", "numra_api.app:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS worker
CMD ["python", "-m", "numra_api.worker"]
