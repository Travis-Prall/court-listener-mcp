"""Get tools for CourtListener MCP server."""

from typing import Annotated, Any

from fastmcp import Context, FastMCP
import httpx
from pydantic import Field

from app.config import config, get_auth_headers, get_http_client

# Create the get server
get_server: FastMCP[Any] = FastMCP(
    name="CourtListener Get Server",
    instructions="Retrieval server for CourtListener legal database providing direct access to specific records by ID. "
    "This server enables fetching individual records including: court opinions, opinion clusters, court information, "
    "dockets, oral argument audio recordings, and judge/legal professional profiles. "
    "Each tool requires the specific ID of the record to retrieve and returns detailed information about that record. "
    "Use this server when you have a specific ID and need complete details about a particular legal entity.",
)


async def _fetch_resource(
    ctx: Context,
    resource_type: str,
    resource_id: str,
    endpoint: str,
) -> dict[str, Any]:
    """Fetch a resource by ID from the CourtListener API.

    Args:
        ctx: The FastMCP context for logging and accessing shared resources.
        resource_type: Human-readable name of the resource (for logging).
        resource_id: The ID of the resource to retrieve.
        endpoint: The API endpoint path (e.g., 'opinions', 'dockets').

    Returns:
        dict: The resource data as returned by the CourtListener API.

    Raises:
        ValueError: If the COURT_LISTENER_API_KEY is not found in environment variables.
        httpx.HTTPStatusError: If the API request fails.

    """
    await ctx.info(f"Getting {resource_type} with ID: {resource_id}")

    headers = get_auth_headers()

    try:
        async with get_http_client(ctx) as http_client:
            response = await http_client.get(
                f"{config.courtlistener_base_url}{endpoint}/{resource_id}/",
                headers=headers,
            )
            response.raise_for_status()
            await ctx.info(f"Successfully retrieved {resource_type} {resource_id}")
            return response.json()

    except httpx.HTTPStatusError as e:
        await ctx.error(f"HTTP error getting {resource_type}: {e}")
        raise
    except Exception as e:
        await ctx.error(f"Error getting {resource_type}: {e}")
        raise


@get_server.tool()
async def opinion(
    opinion_id: Annotated[str, Field(description="The opinion ID to retrieve")],
    ctx: Context,
) -> dict[str, Any]:
    """Get a specific court opinion by ID from CourtListener."""
    return await _fetch_resource(ctx, "opinion", opinion_id, "opinions")


@get_server.tool()
async def docket(
    docket_id: Annotated[str, Field(description="The docket ID to retrieve")],
    ctx: Context,
) -> dict[str, Any]:
    """Get a specific court docket by ID from CourtListener."""
    return await _fetch_resource(ctx, "docket", docket_id, "dockets")


@get_server.tool()
async def audio(
    audio_id: Annotated[str, Field(description="The audio recording ID to retrieve")],
    ctx: Context,
) -> dict[str, Any]:
    """Get oral argument audio information by ID from CourtListener."""
    return await _fetch_resource(ctx, "audio", audio_id, "audio")


@get_server.tool()
async def cluster(
    cluster_id: Annotated[str, Field(description="The opinion cluster ID to retrieve")],
    ctx: Context,
) -> dict[str, Any]:
    """Get an opinion cluster by ID from CourtListener."""
    return await _fetch_resource(ctx, "cluster", cluster_id, "clusters")


@get_server.tool()
async def person(
    person_id: Annotated[str, Field(description="The person (judge) ID to retrieve")],
    ctx: Context,
) -> dict[str, Any]:
    """Get judge or legal professional information by ID from CourtListener."""
    return await _fetch_resource(ctx, "person", person_id, "people")


@get_server.tool()
async def court(
    court_id: Annotated[
        str, Field(description="The court ID to retrieve (e.g., 'scotus', 'ca9')")
    ],
    ctx: Context,
) -> dict[str, Any]:
    """Get court information by ID from CourtListener."""
    return await _fetch_resource(ctx, "court", court_id, "courts")
