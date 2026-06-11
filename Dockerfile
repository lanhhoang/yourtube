# syntax=docker/dockerfile:1.7

# ----------------------------------------------------------------------------
# YourTube runtime image
#
# Single-stage build: keeps the Dockerfile easy to read and matches the
# project's "one process, one image" deployment model.
#
# Migration ownership lives in the FastAPI lifespan (see app.main), so the
# container intentionally starts uvicorn directly. There is no
# `alembic upgrade head && uvicorn ...` wrapper command here; doing so
# would split schema authority between Docker and the application.
# ----------------------------------------------------------------------------

FROM python:3.12-slim AS runtime

# System dependencies:
#   - ffmpeg: required by yt-dlp for muxing/transcoding video and audio
#   - curl: used for in-container diagnostics and yt-dlp's HLS fetcher
#   - ca-certificates: keeps TLS verification working against CDNs
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install uv. Copying the prebuilt binary keeps the image small and
# avoids the cost of pip-installing uv itself. The version pin matches
# the one used in CI (.github/workflows/quality.yml) for reproducibility.
COPY --from=ghcr.io/astral-sh/uv:0.7.21 /uv /uvx /usr/local/bin/

# Run as a dedicated non-root user. UID 65532 is the "nonroot" UID used
# by distroless images and avoids colliding with typical host users.
RUN groupadd --system --gid 65532 yourtube \
    && useradd --system --uid 65532 --gid yourtube \
        --home-dir /app --shell /usr/sbin/nologin yourtube

WORKDIR /app
ENV PATH="/app/.venv/bin:${PATH}"

# ---- Dependency layer ----------------------------------------------------
# Copy the lockfile and project metadata first so dependency installation
# is cached separately from application code changes.
COPY pyproject.toml uv.lock ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

# Production-only install (no dev/test extras). --frozen ensures the
# lockfile is honoured exactly, so image builds are reproducible.
RUN uv sync --frozen --no-dev

# Hand the application files off to the non-root user. uv created the
# project-local .venv under /app/.venv which must also be readable by
# the runtime user.
RUN chown -R yourtube:yourtube /app

USER yourtube

EXPOSE 8000

# Boot directly with the uvicorn entrypoint installed in /app/.venv/bin.
# The FastAPI lifespan in app.main runs `alembic upgrade head` before the
# first request is served, which is why no separate migration command is
# included here.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
