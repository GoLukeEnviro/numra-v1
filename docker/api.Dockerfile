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

# The four packages copied above are the workspace's entire membership (see
# [tool.uv.workspace] in pyproject.toml) -- a plain sync already covers exactly them;
# `uv sync --package` cannot be repeated to name more than one (uv 0.5.11 rejects that
# outright), which is what this line used to (incorrectly) attempt.
RUN uv sync --frozen --no-dev

RUN addgroup --system numra && adduser --system --ingroup numra numra
USER numra

ENV PATH="/app/.venv/bin:$PATH"

FROM base AS api
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 \
  CMD curl --fail http://127.0.0.1:8000/v1/health/ready || exit 1
CMD ["uvicorn", "numra_api.app:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS worker
CMD ["python", "-m", "numra_api.worker"]
