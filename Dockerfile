# Use Python 3.12 slim image for smaller size
FROM python:3.12-slim AS builder

# Set working directory
WORKDIR /opt/courtlistener

# Install system dependencies needed for building
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Copy dependency files first (for better caching)
COPY pyproject.toml uv.lock ./

# Install dependencies (not the local package yet)
RUN uv sync --frozen --no-dev --no-install-project

# Multi-stage build for smaller final image
FROM python:3.12-slim

# Set working directory
WORKDIR /opt/courtlistener

# Create non-root user
RUN groupadd -r courtlistener && useradd -r -g courtlistener -m courtlistener

# Copy virtual environment and project files from builder
COPY --from=builder /opt/courtlistener/.venv .venv
COPY --from=builder /opt/courtlistener/pyproject.toml /opt/courtlistener/uv.lock ./

# Copy application code
COPY app ./app

# Pre-compile Python bytecode for faster startup
RUN python -m compileall -q ./app .venv/lib

# Set ownership for non-root user
RUN chown -R courtlistener:courtlistener /opt/courtlistener

# Switch to non-root user
USER courtlistener

# Set Python-related environment variables
ENV PYTHONUNBUFFERED=1 \
    PATH="/opt/courtlistener/.venv/bin:$PATH"

# Expose default MCP port
EXPOSE 8000

# Labels for container metadata
LABEL org.opencontainers.image.title="CourtListener MCP Server" \
      org.opencontainers.image.description="MCP server providing LLM access to CourtListener legal database" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.source="https://github.com/Travis-Prall/court-listener-mcp"

# Default to HTTP transport for container use, bound to all interfaces
# Override with MCP_TRANSPORT=stdio for CLI integration
CMD ["python", "-m", "app", "--transport", "http", "--host", "0.0.0.0"]
