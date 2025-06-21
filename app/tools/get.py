"""Get tools for CourtListener MCP server."""

import os
from typing import Annotated, Any

from dotenv import load_dotenv
from fastmcp import Context, FastMCP
import httpx
from loguru import logger
from pydantic import Field

# Load environment variables
load_dotenv()

# Get API key from environment
API_KEY = os.getenv("COURT_LISTENER_API_KEY")

# Create the get server
get_server: FastMCP[Any] = FastMCP(
    name="CourtListener Get Server",
    instructions="Retrieval server for CourtListener legal database providing direct access to specific records by ID. "
    "This server enables fetching individual records including: court opinions, opinion clusters, court information, "
    "dockets, oral argument audio recordings, and judge/legal professional profiles. "
    "Each tool requires the specific ID of the record to retrieve and returns detailed information about that record. "
    "Use this server when you have a specific ID and need complete details about a particular legal entity.",
)


@get_server.tool()
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

    Raises:
        ValueError: If the COURT_LISTENER_API_KEY is not found in environment variables.

    """
    if ctx:
        await ctx.info(f"Getting opinion with ID: {opinion_id}")
    else:
        logger.info(f"Getting opinion with ID: {opinion_id}")

    if not API_KEY:
        error_msg = "COURT_LISTENER_API_KEY not found in environment variables"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise ValueError(error_msg)

    headers = {"Authorization": f"Token {API_KEY}"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://www.courtlistener.com/api/rest/v4/opinions/{opinion_id}/",
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()

            if ctx:
                await ctx.info(f"Successfully retrieved opinion {opinion_id}")
            else:
                logger.info(f"Successfully retrieved opinion {opinion_id}")

            return response.json()

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error getting opinion: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e
    except Exception as e:
        error_msg = f"Error getting opinion: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e


@get_server.tool()
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

    Raises:
        ValueError: If the COURT_LISTENER_API_KEY is not found in environment variables.

    """
    if ctx:
        await ctx.info(f"Getting docket with ID: {docket_id}")
    else:
        logger.info(f"Getting docket with ID: {docket_id}")

    if not API_KEY:
        error_msg = "COURT_LISTENER_API_KEY not found in environment variables"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise ValueError(error_msg)

    headers = {"Authorization": f"Token {API_KEY}"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://www.courtlistener.com/api/rest/v4/dockets/{docket_id}/",
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()

            if ctx:
                await ctx.info(f"Successfully retrieved docket {docket_id}")
            else:
                logger.info(f"Successfully retrieved docket {docket_id}")

            return response.json()

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error getting docket: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e
    except Exception as e:
        error_msg = f"Error getting docket: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e


@get_server.tool()
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

    Raises:
        ValueError: If the COURT_LISTENER_API_KEY is not found in environment variables.

    """
    if ctx:
        await ctx.info(f"Getting audio with ID: {audio_id}")
    else:
        logger.info(f"Getting audio with ID: {audio_id}")

    if not API_KEY:
        error_msg = "COURT_LISTENER_API_KEY not found in environment variables"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise ValueError(error_msg)

    headers = {"Authorization": f"Token {API_KEY}"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://www.courtlistener.com/api/rest/v4/audio/{audio_id}/",
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()

            if ctx:
                await ctx.info(f"Successfully retrieved audio {audio_id}")
            else:
                logger.info(f"Successfully retrieved audio {audio_id}")

            return response.json()

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error getting audio: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e
    except Exception as e:
        error_msg = f"Error getting audio: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e


@get_server.tool()
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

    Raises:
        ValueError: If the COURT_LISTENER_API_KEY is not found in environment variables.

    """
    if ctx:
        await ctx.info(f"Getting cluster with ID: {cluster_id}")
    else:
        logger.info(f"Getting cluster with ID: {cluster_id}")

    if not API_KEY:
        error_msg = "COURT_LISTENER_API_KEY not found in environment variables"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise ValueError(error_msg)

    headers = {"Authorization": f"Token {API_KEY}"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://www.courtlistener.com/api/rest/v4/clusters/{cluster_id}/",
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()

            if ctx:
                await ctx.info(f"Successfully retrieved cluster {cluster_id}")
            else:
                logger.info(f"Successfully retrieved cluster {cluster_id}")

            return response.json()

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error getting cluster: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e
    except Exception as e:
        error_msg = f"Error getting cluster: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e


@get_server.tool()
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

    Raises:
        ValueError: If the COURT_LISTENER_API_KEY is not found in environment variables.

    """
    if ctx:
        await ctx.info(f"Getting person with ID: {person_id}")
    else:
        logger.info(f"Getting person with ID: {person_id}")

    if not API_KEY:
        error_msg = "COURT_LISTENER_API_KEY not found in environment variables"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise ValueError(error_msg)

    headers = {"Authorization": f"Token {API_KEY}"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://www.courtlistener.com/api/rest/v4/people/{person_id}/",
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()

            if ctx:
                await ctx.info(f"Successfully retrieved person {person_id}")
            else:
                logger.info(f"Successfully retrieved person {person_id}")

            return response.json()

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error getting person: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e
    except Exception as e:
        error_msg = f"Error getting person: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e


@get_server.tool()
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

    Raises:
        ValueError: If the COURT_LISTENER_API_KEY is not found in environment variables.

    """
    if ctx:
        await ctx.info(f"Getting court with ID: {court_id}")
    else:
        logger.info(f"Getting court with ID: {court_id}")

    if not API_KEY:
        error_msg = "COURT_LISTENER_API_KEY not found in environment variables"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise ValueError(error_msg)

    headers = {"Authorization": f"Token {API_KEY}"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://www.courtlistener.com/api/rest/v4/courts/{court_id}/",
                headers=headers,
                timeout=30.0,
            )
            response.raise_for_status()

            if ctx:
                await ctx.info(f"Successfully retrieved court {court_id}")
            else:
                logger.info(f"Successfully retrieved court {court_id}")

            return response.json()

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error getting court: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e
    except Exception as e:
        error_msg = f"Error getting court: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e
