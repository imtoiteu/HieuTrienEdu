# HieuTrienEducation API
#
# Multi-stage so the runtime image carries no build toolchain. uv installs dependencies far faster
# than pip, which matters because this image is rebuilt on every dependency change.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

# --- dependencies -----------------------------------------------------------------------
FROM base AS deps

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

# Copy only the manifest first so a source-only change does not invalidate the dependency layer.
COPY services/api/pyproject.toml /srv/pyproject.toml
RUN uv venv /srv/.venv && \
    VIRTUAL_ENV=/srv/.venv uv pip install --no-cache -r /srv/pyproject.toml

# --- runtime ----------------------------------------------------------------------------
FROM base AS runtime

# curl is needed by the Compose healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=deps /srv/.venv /srv/.venv
ENV PATH="/srv/.venv/bin:$PATH"

WORKDIR /srv/app_root
COPY services/api /srv/app_root
# Curriculum content is read at seed time; the container mounts or copies it at the repo-relative
# path the settings module expects (four levels up from app/core/config.py).
COPY content /srv/content

# Run as a non-root user. A container that does not need root should not have it.
RUN useradd --create-home --uid 10001 hietedu \
    && mkdir -p /srv/data \
    && chown -R hietedu:hietedu /srv
USER hietedu

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
