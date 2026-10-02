# Production image for the contact form, published to ghcr.io/abrunacci/abrunacci-dev-backend
# by .github/workflows/deploy.yml. Local development runs with uv instead (README.md).
#
# Two stages: the first installs with uv, the second carries only the virtualenv. No uv, no dev
# dependencies, no tests (.dockerignore keeps them out of the context).

# 3.13: what pyproject.toml requires and CI runs.
FROM python:3.13-slim AS build

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /bin/

WORKDIR /app

# Dependency layer: only invalidated when pyproject.toml or uv.lock change.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# --no-editable: the package (with its templates and font) is copied into the virtualenv, so the
# runtime stage needs no src/.
COPY README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable


FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# A fixed uid. On the server infra runs it as its own backends user anyway.
RUN useradd --system --uid 10001 --no-create-home --home-dir /nonexistent app

WORKDIR /app

COPY --from=build /app/.venv ./.venv

USER app

EXPOSE 8000

# No HEALTHCHECK: infra checks /api/health through Caddy after each deploy.
# One process, no --reload: the limits live in this process's memory. --factory: create_app()
# reads the settings when the server starts.
CMD ["uvicorn", "contact.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
