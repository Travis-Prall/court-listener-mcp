"""Get tools for CourtListener MCP server."""

from typing import Annotated, Any

from fastmcp import Context, FastMCP
import httpx
from pydantic import Field

from app.tools.common import (
    API_BASE_URL,
    API_KEY,
    DEFAULT_TIMEOUT,
    auth_headers,
    log_error,
    log_info,
)

# Create the get server
get_server: FastMCP[Any] = FastMCP(
    name="CourtListener Get Server",
    instructions=(
        "Retrieval server for CourtListener legal database providing direct "
        "access to specific records by ID. This server enables fetching "
        "individual records including: court opinions, opinion clusters, court "
        "information, dockets, oral argument audio recordings, and judge/legal "
        "professional profiles. Each tool requires the specific ID of the "
        "record to retrieve and returns detailed information about that record. "
        "Use this server when you have a specific ID and need complete details "
        "about a particular legal entity."
    ),
)


async def _fetch_record(
    endpoint: str,
    record_label: str,
    record_id: str,
    ctx: Context | None,
    require_api_key: bool = True,
) -> dict[str, Any]:
    """Fetch a single record by ID from the CourtListener API.

    Args:
        endpoint: CourtListener API endpoint segment (e.g., 'opinions').
        record_label: Human-readable record type used in log messages.
        record_id: The record ID to retrieve.
        ctx: Optional FastMCP context for logging and error reporting.
        require_api_key: Whether the CourtListener API key is required.

    Returns:
        dict[str, Any]: The record data as returned by the CourtListener API.

    Raises:
        ValueError: If the CourtListener API key is required but missing.
        httpx.HTTPStatusError: If the API returns an HTTP error status.

    """
    await log_info(ctx, f"Getting {record_label} with ID: {record_id}")

    if not API_KEY:
        if require_api_key:
            error_msg = "COURT_LISTENER_API_KEY not found in environment variables"
            await log_error(ctx, error_msg)
            raise ValueError(error_msg)
        await log_info(ctx, "Using public API access (no authentication)")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE_URL}/{endpoint}/{record_id}/",
                headers=auth_headers(),
                timeout=DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
    except httpx.HTTPStatusError as e:
        await log_error(ctx, f"HTTP error getting {record_label}: {e}")
        raise
    except Exception as e:
        await log_error(ctx, f"Error getting {record_label}: {e}")
        raise

    await log_info(ctx, f"Successfully retrieved {record_label} {record_id}")
    return data


@get_server.tool(tags={"requires-courtlistener-key"})
async def opinion(
    opinion_id: Annotated[str, Field(description="The opinion ID to retrieve")],
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get a specific court opinion by ID from CourtListener.

    Args:
        opinion_id: The opinion ID to retrieve.
        ctx: Optional context for logging and error reporting.

    Returns:
        dict: The opinion data as returned by the CourtListener API.

    Note:
        Works without an API key through public API access; providing the
        COURT_LISTENER_API_KEY improves rate limits.

    """
    return await _fetch_record(
        "opinions", "opinion", opinion_id, ctx, require_api_key=False
    )


@get_server.tool(tags={"requires-courtlistener-key"})
async def docket(
    docket_id: Annotated[str, Field(description="The docket ID to retrieve")],
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get a specific court docket by ID from CourtListener.

    Args:
        docket_id: The docket ID to retrieve.
        ctx: Optional context for logging and error reporting.

    Returns:
        dict: The docket data as returned by the CourtListener API.

    Note:
        Requires the COURT_LISTENER_API_KEY environment variable; the shared
        fetch helper raises ValueError when the key is missing.

    """
    return await _fetch_record("dockets", "docket", docket_id, ctx)


@get_server.tool(tags={"requires-courtlistener-key"})
async def audio(
    audio_id: Annotated[str, Field(description="The audio recording ID to retrieve")],
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get oral argument audio information by ID from CourtListener.

    Args:
        audio_id: The audio recording ID to retrieve.
        ctx: Optional context for logging and error reporting.

    Returns:
        dict: The audio data as returned by the CourtListener API.

    Note:
        Requires the COURT_LISTENER_API_KEY environment variable; the shared
        fetch helper raises ValueError when the key is missing.

    """
    return await _fetch_record("audio", "audio", audio_id, ctx)


@get_server.tool(tags={"requires-courtlistener-key"})
async def cluster(
    cluster_id: Annotated[str, Field(description="The opinion cluster ID to retrieve")],
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get an opinion cluster by ID from CourtListener.

    Args:
        cluster_id: The opinion cluster ID to retrieve.
        ctx: Optional context for logging and error reporting.

    Returns:
        dict: The opinion cluster data as returned by the CourtListener API.

    Note:
        Requires the COURT_LISTENER_API_KEY environment variable; the shared
        fetch helper raises ValueError when the key is missing.

    """
    return await _fetch_record("clusters", "cluster", cluster_id, ctx)


@get_server.tool(tags={"requires-courtlistener-key"})
async def person(
    person_id: Annotated[str, Field(description="The person (judge) ID to retrieve")],
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get judge or legal professional information by ID from CourtListener.

    Args:
        person_id: The person (judge) ID to retrieve.
        ctx: Optional context for logging and error reporting.

    Returns:
        dict: The person data as returned by the CourtListener API.

    Note:
        Requires the COURT_LISTENER_API_KEY environment variable; the shared
        fetch helper raises ValueError when the key is missing.

    """
    return await _fetch_record("people", "person", person_id, ctx)


@get_server.tool(tags={"requires-courtlistener-key"})
async def court(
    court_id: Annotated[
        str, Field(description="The court ID to retrieve (e.g., 'scotus', 'ca9')")
    ],
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get court information by ID from CourtListener.

    Args:
        court_id: The court ID to retrieve (e.g., 'scotus', 'ca9').
        ctx: Optional context for logging and error reporting.

    Returns:
        dict: The court data as returned by the CourtListener API.

    Note:
        Requires the COURT_LISTENER_API_KEY environment variable; the shared
        fetch helper raises ValueError when the key is missing.

    """
    return await _fetch_record("courts", "court", court_id, ctx)
