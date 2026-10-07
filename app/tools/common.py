"""Shared helpers for CourtListener MCP tool servers.

This module centralizes CourtListener API configuration and the logging and
authentication helpers used by the tool modules, so each tool server can
delegate fetch/error-handling logic to small, focused helpers.
"""

# ``request_with_retry`` legitimately exposes the full httpx request surface.
# ruff: file-ignore[too-many-arguments]

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv
import httpx
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

# Transient-failure retry policy. The upstream APIs used by this server
# (CourtListener, GovInfo, and Regulations.gov) intermittently return 5xx
# gateway errors or drop connections. Retrying a few times with exponential
# backoff turns those blips into successful calls instead of hard failures.
RETRY_MAX_ATTEMPTS = 4
RETRY_BACKOFF_SECONDS = 1.0
RETRY_BACKOFF_MAX_SECONDS = 8.0
# 429 (rate limited) and 5xx gateway errors are transient and safe to retry.
RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 500, 502, 503, 504})


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

    Always records the message with the process logger, then mirrors it
    to the MCP context when one is active. Context mirroring is
    best-effort: in background task execution the worker has no MCP
    session, so context errors are swallowed after the process logger
    has captured the message.

    Args:
        ctx: Optional FastMCP context used when a tool call is active.
        message: The informational message to log.

    """
    logger.info(message)
    if ctx:
        try:
            await ctx.info(message)
        except Exception as exc:
            logger.debug(f"MCP context logging unavailable: {exc}")


async def log_error(ctx: Context | None, message: str) -> None:
    """Log an error message through the context or fallback logger.

    Always records the message with the process logger, then mirrors it
    to the MCP context when one is active. Context mirroring is
    best-effort: in background task execution the worker has no MCP
    session, so context errors are swallowed after the process logger
    has captured the message.

    Args:
        ctx: Optional FastMCP context used when a tool call is active.
        message: The error message to log.

    """
    logger.error(message)
    if ctx:
        try:
            await ctx.error(message)
        except Exception as exc:
            logger.debug(f"MCP context logging unavailable: {exc}")


def _retry_delay(
    attempt: int,
    response: httpx.Response | None = None,
    backoff_seconds: float | None = None,
    max_delay: float | None = None,
) -> float:
    """Compute how long to wait before the next retry attempt.

    Args:
        attempt: The attempt number that just finished (1-based).
        response: Optional response that triggered the retry. A numeric
            ``Retry-After`` header on it takes precedence over the
            computed exponential backoff.
        backoff_seconds: Base backoff delay in seconds. Defaults to
            :data:`RETRY_BACKOFF_SECONDS`, read at call time so tests can
            override it.
        max_delay: Upper bound for the delay. Defaults to
            :data:`RETRY_BACKOFF_MAX_SECONDS`.

    Returns:
        float: The number of seconds to snooze before the next attempt.

    """
    cap = RETRY_BACKOFF_MAX_SECONDS if max_delay is None else max_delay
    base = RETRY_BACKOFF_SECONDS if backoff_seconds is None else backoff_seconds
    if response is not None:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return max(0.0, min(float(retry_after), cap))
            except ValueError:
                logger.debug(f"Ignoring non-numeric Retry-After header: {retry_after}")
    return min(base * (2 ** (attempt - 1)), cap)


async def request_with_retry(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json: Any | None = None,
    data: Any | None = None,
    request_timeout: float = DEFAULT_TIMEOUT,
    ctx: Context | None = None,
    error_label: str = "Request",
    max_attempts: int | None = None,
    backoff_seconds: float | None = None,
) -> httpx.Response:
    """Perform an HTTP request, retrying transient upstream failures.

    Every endpoint used by this server is a non-mutating read, so a
    request can safely be repeated. Transient failures are transport
    errors (timeouts, dropped connections) and the HTTP statuses listed
    in :data:`RETRYABLE_STATUS_CODES` (rate limiting and gateway errors).
    Retries are spaced by an exponential backoff that honors a numeric
    ``Retry-After`` header when the server sends one.

    Args:
        method: HTTP method (e.g. ``"GET"`` or ``"POST"``).
        url: The full URL to request.
        headers: Optional request headers.
        params: Optional query parameters.
        json: Optional JSON request body.
        data: Optional form-encoded request body.
        request_timeout: Per-attempt timeout in seconds.
        ctx: Optional FastMCP context for logging and error reporting.
        error_label: Human-readable label used in log messages.
        max_attempts: Total attempts before giving up. Defaults to
            :data:`RETRY_MAX_ATTEMPTS`.
        backoff_seconds: Base backoff delay in seconds. Defaults to
            :data:`RETRY_BACKOFF_SECONDS`.

    Returns:
        httpx.Response: The final response. If every attempt returned a
        retryable status, this is the last such response, so the caller
        can still surface it via ``response.raise_for_status()``.

    Raises:
        httpx.TransportError: If every attempt failed at the transport
            level (timeout, connection error, and the like).

    """
    attempts = RETRY_MAX_ATTEMPTS if max_attempts is None else max_attempts
    backoff = RETRY_BACKOFF_SECONDS if backoff_seconds is None else backoff_seconds

    last_error: httpx.TransportError | None = None
    async with httpx.AsyncClient() as client:
        for attempt in range(1, attempts + 1):
            try:
                response = await client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json,
                    data=data,
                    timeout=request_timeout,
                )
            except httpx.TransportError as exc:
                last_error = exc
                if attempt >= attempts:
                    await log_error(
                        ctx,
                        f"{error_label} failed after {attempt} attempt(s): {exc}",
                    )
                    raise
                delay = _retry_delay(attempt, backoff_seconds=backoff)
                await log_info(
                    ctx,
                    f"{error_label} transport error on attempt "
                    f"{attempt}/{attempts}; retrying in {delay:.1f}s: {exc}",
                )
                await asyncio.sleep(delay)
                continue

            if response.status_code in RETRYABLE_STATUS_CODES and attempt < attempts:
                delay = _retry_delay(attempt, response, backoff_seconds=backoff)
                await log_info(
                    ctx,
                    f"{error_label} returned HTTP {response.status_code} on "
                    f"attempt {attempt}/{attempts}; retrying in {delay:.1f}s",
                )
                await asyncio.sleep(delay)
                continue

            return response

    raise last_error or RuntimeError(f"{error_label}: no attempts performed")
