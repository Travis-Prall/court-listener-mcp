"""Shared helpers for CourtListener MCP tool servers.

This module centralizes CourtListener API configuration and the logging and
authentication helpers used by the tool modules, so each tool server can
delegate fetch/error-handling logic to small, focused helpers.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from loguru import logger

if TYPE_CHECKING:
    from fastmcp import Context

# Load environment variables
load_dotenv()

# CourtListener API configuration
API_KEY: str | None = os.getenv("COURT_LISTENER_API_KEY")
API_BASE_URL = "https://www.courtlistener.com/api/rest/v4"
SEARCH_URL = f"{API_BASE_URL}/search/"
CITATION_LOOKUP_URL = f"{API_BASE_URL}/citation-lookup/"
DEFAULT_TIMEOUT = 30.0
BATCH_TIMEOUT = 60.0  # Longer timeout for batch citation requests
HTTP_OK = 200


def auth_headers() -> dict[str, str]:
    """Build request headers with token authentication when a key is available.

    Returns:
        dict[str, str]: Headers containing the Authorization token when the
        COURT_LISTENER_API_KEY environment variable is set, empty otherwise.

    """
    headers: dict[str, str] = {}
    if API_KEY:
        headers["Authorization"] = f"Token {API_KEY}"
    return headers


async def log_info(ctx: Context | None, message: str) -> None:
    """Log an informational message through the context or fallback logger.

    Args:
        ctx: Optional FastMCP context used when a tool call is active.
        message: The informational message to log.

    """
    if ctx:
        await ctx.info(message)
    else:
        logger.info(message)


async def log_error(ctx: Context | None, message: str) -> None:
    """Log an error message through the context or fallback logger.

    Args:
        ctx: Optional FastMCP context used when a tool call is active.
        message: The error message to log.

    """
    if ctx:
        await ctx.error(message)
    else:
        logger.error(message)
