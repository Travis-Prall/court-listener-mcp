#!/usr/bin/env python3
"""Configuration management for CourtListener MCP Server."""

from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """Configuration for CourtListener MCP Server."""

    # Server settings
    # Binding to all interfaces is intentional so the containerized MCP
    # server is reachable from outside its container.
    host: str = "0.0.0.0"  # ruff: ignore[hardcoded-bind-all-interfaces]
    mcp_port: int = 8785
    mcp_path: str = "/mcp/"

    # cors_allow_origins: browser-based MCP clients (e.g. MCP Inspector) are
    # the only case that needs CORS. Empty (default) means no CORS
    # middleware is added, since the current clients are not browser-based.
    # Host/Origin protection and stateless HTTP are left to FastMCP's own
    # FASTMCP_STATELESS_HTTP / FASTMCP_HTTP_HOST_ORIGIN_PROTECTION settings,
    # which the server defers to (see the README HTTP deployment notes).
    cors_allow_origins: list[str] = []

    # Logging
    courtlistener_log_level: str = "INFO"
    courtlistener_debug: bool = False

    # Environment
    environment: str = "production"

    # CourtListener API
    courtlistener_base_url: str = "https://www.courtlistener.com/api/rest/v4/"
    courtlistener_api_key: str | None = None
    courtlistener_timeout: int = 30

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",  # Ignore extra environment variables
    }


# Global config instance
config = Config()


def is_development() -> bool:
    """Check if running in development environment.

    Returns:
        True if in development mode, False otherwise.

    """
    return config.environment.lower() == "development"


def is_debug_enabled() -> bool:
    """Check if debug mode is enabled.

    Returns:
        True if debug is enabled, False otherwise.

    """
    return (
        config.courtlistener_debug or config.courtlistener_log_level.upper() == "DEBUG"
    )
