# syntax=docker/dockerfile:1.7

# ----------------------------------------------------------------------------
# YourTube runtime image
#
# Multi-stage build: `web-build` compiles the Svelte app, and the `runtime`
# stage ships it with the Python server, matching the project's
# "one process, one image" deployment model.
#
# Migration ownership lives in the FastAPI lifespan (see app.main), so the
# container intentionally starts uvicorn directly. There is no
# `alembic upgrade head && uvicorn ...` wrapper command here; doing so
# would split schema authority between Docker and the application.
# ----------------------------------------------------------------------------

FROM node:24-trixie-slim AS node-runtime

FROM node:24-trixie-slim AS web-build
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/server/package.json apps/server/
COPY apps/web/package.json apps/web/
RUN pnpm install --frozen-lockfile
COPY apps/web apps/web
COPY tsconfig.base.json ./
RUN pnpm --filter @app/web build

FROM python:3.12-slim-trixie AS runtime

# System dependencies:
#   - ffmpeg: required by yt-dlp for muxing/transcoding video and audio
#   - curl: used for in-container diagnostics and yt-dlp's HLS fetcher
#   - ca-certificates: keeps TLS verification working against CDNs
#   - libatomic1: required by the bundled Node.js runtime on ARM
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        ffmpeg \
        libatomic1 \
    && rm -rf /var/lib/apt/lists/*

# yt-dlp's EJS solver requires Node.js 22 or newer (24 here). npm is not needed.
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node

# Install uv. Copying the prebuilt binary keeps the image small and
# avoids the cost of pip-installing uv itself. The version pin matches
# the latest release at the time of the last dependency bump.
COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /uvx /usr/local/bin/

# Run as a dedicated non-root user. UID 65532 is the "nonroot" UID used
# by distroless images and avoids colliding with typical host users.
RUN groupadd --system --gid 65532 yourtube \
    && useradd --system --uid 65532 --gid yourtube \
        --home-dir /app --shell /usr/sbin/nologin yourtube

WORKDIR /app/apps/server
ENV PATH="/app/apps/server/.venv/bin:${PATH}"

# ---- Dependency layer ----------------------------------------------------
# Copy the lockfile and project metadata first so dependency installation
# is cached separately from application code changes.
COPY apps/server/pyproject.toml apps/server/uv.lock ./
COPY apps/server/alembic.ini ./
COPY apps/server/alembic ./alembic
COPY apps/server/app ./app

# Production-only install (no dev/test extras). --frozen ensures the
# lockfile is honoured exactly, so image builds are reproducible.
RUN uv sync --frozen --no-dev

COPY --from=web-build /app/apps/web/dist /app/apps/web/dist

# Hand the application files off to the non-root user. uv created the
# project-local .venv under /app/apps/server/.venv which must be readable by
# the runtime user.
RUN chown -R yourtube:yourtube /app

USER yourtube

EXPOSE 8000

# Boot directly with the uvicorn entrypoint installed in /app/apps/server/.venv/bin.
# The FastAPI lifespan in app.main runs `alembic upgrade head` before the
# first request is served, which is why no separate migration command is
# included here.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
