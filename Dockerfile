# syntax=docker/dockerfile:1
# Only the official docker/dockerfile frontend is used (no third-party frontends).

###############################################################################
# Builder stage: resolves dependencies with uv (build tools stay out of runtime)
###############################################################################

# Base image pinned to an immutable multi-arch manifest digest for reproducibility.
# To bump: docker buildx imagetools inspect python:3.14-slim  (keep both stages in sync)
FROM python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6 AS builder

WORKDIR /app

# uv binary copied from the official uv image, pinned by tag + digest.
# To bump: docker buildx imagetools inspect ghcr.io/astral-sh/uv:<version>
COPY --from=ghcr.io/astral-sh/uv:0.12.12@sha256:73d2665b478d8fa2de1cf105c6841f8e9cb6b09e568fc7700440c09f8fcd7ac4 /uv /uvx /usr/local/bin/

# Dependency manifests first (least frequently changing) for layer-cache hits.
COPY pyproject.toml uv.lock ./

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Lockfile-frozen install of runtime dependencies only (no dev group, no project
# install). BuildKit cache mount persists downloads across builds.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

###############################################################################
# Runtime stage: slim base, non-root fixed UID, no build tools, no curl
###############################################################################

FROM python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6 AS runtime

# Non-root user with a fixed UID/GID (works with orchestrator runAsNonRoot checks).
# No login shell; HOME is redirected to tmpfs via ENV below.
RUN groupadd -r -g 10001 courtlistener \
    && useradd -r -u 10001 -g courtlistener -d /nonexistent -s /usr/sbin/nologin courtlistener

WORKDIR /src

# Runtime dependencies only - the venv carries no pip/uv and the final image
# ships no shell utilities or compiler toolchain.
COPY --from=builder --chown=10001:10001 /app/.venv /app/.venv

# Application source (changes most frequently -> copied last for cache hits).
COPY --chown=10001:10001 app /src/app

# pyproject.toml is read at runtime by app.server.get_version() for the /health
# endpoint (contains no secrets; ~2 KB).
COPY --from=builder --chown=10001:10001 /app/pyproject.toml /src/pyproject.toml

# Writable log directory for plain `docker run` (the hardened Compose file
# mounts a tmpfs here; see docker-compose.yml).
RUN mkdir -p /src/app/logs \
    && chown 10001:10001 /src/app/logs

# Non-root user, numeric UID/GID (safe for runAsNonRoot admission checks).
USER 10001:10001

# Set Python-related environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/src \
    PATH="/app/.venv/bin:$PATH" \
    HOME=/tmp \
    LOG_LEVEL=INFO \
    LOG_FORMAT=json \
    API_BASE_URL=https://www.courtlistener.com/api/rest/v4/

# Expose the MCP HTTP (streamable) port
EXPOSE 8785

# Liveness probe for orchestrators - hits the unauthenticated /health route
# documented in the FastMCP HTTP deployment guide. Uses the Python standard
# library so the image ships no curl/wget.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8785/health', timeout=4)"]

# Graceful shutdown on `docker stop` / orchestrator SIGTERM.
STOPSIGNAL SIGTERM

# Labels for container metadata
LABEL org.opencontainers.image.title="CourtListener ++ MCP Server" \
      org.opencontainers.image.description="Model Context Protocol server providing LLM-friendly access to legal cases and court data through the CourtListener API v4" \
      org.opencontainers.image.version="0.2.2" \
      org.opencontainers.image.source="https://github.com/Travis-Prall/court-listener-mcp" \
      org.opencontainers.image.url="https://www.travisprall.com/" \
      org.opencontainers.image.vendor="Travis-Prall"

# Default command: run the MCP server with HTTP (streamable) transport on :8785.
# docker-compose.yml overrides this with the same command.
CMD ["python", "-m", "app"]
