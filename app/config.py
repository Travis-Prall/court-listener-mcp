#!/usr/bin/env python3
"""Configuration management for CourtListener MCP Server."""

from pydantic_settings import BaseSettings


class Config(BaseSettings):
    """Configuration for CourtListener MCP Server."""

    # Server settings
    host: str = "0.0.0.0"
    mcp_port: int = 8785

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
