"""GovInfo statute tools for the CourtListener MCP server.

Provides United States statute search and lookup tools backed by the
official GovInfo API from the U.S. Government Publishing Office (GPO),
covering the United States Code (USCODE), Statutes at Large (STATUTE),
Public and Private Laws (PLAW), and Statutes Compilations (COMPS)
collections. All tools require the ``GOVINFO_API_KEY`` environment
variable (a free api.data.gov key).
"""

# GovInfo tool definitions legitimately expose more than the configured
# maximum of six parameters, matching the upstream GovInfo API surface.
# ruff: file-ignore[too-many-arguments, too-many-positional-arguments]

import os
from typing import Annotated, Any

from fastmcp import Context, FastMCP
import httpx
from pydantic import Field

from app.tools.common import DEFAULT_TIMEOUT, log_error, log_info

# GovInfo API configuration
API_KEY: str | None = os.getenv("GOVINFO_API_KEY")
GOVINFO_BASE_URL = "https://api.govinfo.gov"
SEARCH_URL = f"{GOVINFO_BASE_URL}/search"

# Create the GovInfo statutes server
govinfo_server: FastMCP[Any] = FastMCP(
    name="GovInfo Statutes Server",
    instructions=(
        "Statute lookup server backed by the official GovInfo API from the "
        "U.S. Government Publishing Office (GPO). Provides search and "
        "retrieval across statute-related collections: United States Code "
        "(USCODE), Statutes at Large (STATUTE), Public and Private Laws "
        "(PLAW), and Statutes Compilations (COMPS). Use these tools to find "
        "enacted federal laws and codified statutory sections, retrieve "
        "package and granule summaries, and locate XML, PDF, or text "
        "download links for statute documents. All tools require the "
        "GOVINFO_API_KEY environment variable."
    ),
)

# Statute-related GovInfo collection codes
STATUTE_COLLECTIONS: dict[str, str] = {
    "USCODE": "United States Code",
    "STATUTE": "Statutes at Large",
    "PLAW": "Public and Private Laws",
    "COMPS": "Statutes Compilations",
}

# Map requested content types to GovInfo download link keys
_CONTENT_KEY_MAP: dict[str, str] = {
    "xml": "xmlLink",
    "pdf": "pdfLink",
    "text": "txtLink",
}
_VALID_CONTENT_TYPES: tuple[str, ...] = ("summary", "xml", "pdf", "text")


def _govinfo_headers() -> dict[str, str]:
    """Build request headers with the GovInfo API key.

    Returns:
        dict[str, str]: Headers containing the ``X-Api-Key`` header when the
        GOVINFO_API_KEY environment variable is set, empty otherwise.

    """
    headers: dict[str, str] = {}
    if API_KEY:
        headers["X-Api-Key"] = API_KEY
    return headers


def _require_api_key() -> None:
    """Ensure the GovInfo API key is configured.

    Raises:
        ValueError: If GOVINFO_API_KEY is not found in environment variables.

    """
    if not API_KEY:
        msg = "GOVINFO_API_KEY not found in environment variables"
        raise ValueError(msg)


async def _search_govinfo(
    request_body: dict[str, Any],
    ctx: Context | None,
    error_label: str,
) -> dict[str, Any]:
    """Execute a search request against the GovInfo search API.

    Args:
        request_body: The JSON request body for the GovInfo search endpoint.
        ctx: Optional FastMCP context for logging and error reporting.
        error_label: Human-readable label used in error log messages.

    Returns:
        dict[str, Any]: The parsed JSON response from the GovInfo search API.

    Raises:
        httpx.HTTPStatusError: If the API returns an HTTP error status.

    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                SEARCH_URL,
                json=request_body,
                headers=_govinfo_headers(),
                timeout=DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
    except httpx.HTTPStatusError as e:
        await log_error(ctx, f"{error_label} HTTP error: {e}")
        raise
    except Exception as e:
        await log_error(ctx, f"{error_label} error: {e}")
        raise
    return data


async def _govinfo_get(
    url: str,
    ctx: Context | None,
    error_label: str,
) -> dict[str, Any]:
    """Execute a GET request against the GovInfo API.

    Args:
        url: The full GovInfo API URL to request.
        ctx: Optional FastMCP context for logging and error reporting.
        error_label: Human-readable label used in error log messages.

    Returns:
        dict[str, Any]: The parsed JSON response from the GovInfo API.

    Raises:
        httpx.HTTPStatusError: If the API returns an HTTP error status.

    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=_govinfo_headers(),
                timeout=DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
    except httpx.HTTPStatusError as e:
        await log_error(ctx, f"{error_label} HTTP error: {e}")
        raise
    except Exception as e:
        await log_error(ctx, f"{error_label} error: {e}")
        raise
    return data


def _get_collection_description(collection_code: str) -> str:
    """Get a detailed description for a statute collection.

    Args:
        collection_code: The collection code to get a description for.

    Returns:
        str: Detailed description of the statute collection.

    """
    descriptions = {
        "USCODE": (
            "The United States Code (USC) is the official codification of "
            "the general and permanent laws of the United States. It is "
            "organized into 54 titles covering broad subject areas."
        ),
        "STATUTE": (
            "The Statutes at Large is the official record of laws enacted by "
            "Congress. It contains the text of public and private laws, "
            "joint resolutions, and concurrent resolutions."
        ),
        "PLAW": (
            "Public and Private Laws are the individual laws enacted by "
            "Congress before they are codified into the United States Code. "
            "Public laws affect the general public, while private laws "
            "affect specific individuals or entities."
        ),
        "COMPS": (
            "Statutes Compilations contain various compilations and "
            "collections of statutes, including subject-specific "
            "compilations and historical collections."
        ),
    }
    return descriptions.get(collection_code, "No description available.")


@govinfo_server.tool(tags={"requires-govinfo-key"})
async def search_statutes(
    query: Annotated[str, Field(description="Search query text for US statutes")],
    collection: Annotated[
        str,
        Field(
            description=(
                "Statute collection to search: 'USCODE', 'STATUTE', 'PLAW', "
                "'COMPS', or leave empty for all statute collections"
            )
        ),
    ] = "",
    congress: Annotated[
        int | None,
        Field(
            description="Filter by Congress number (for PLAW collection)",
            ge=1,
            le=200,
        ),
    ] = None,
    title_number: Annotated[
        str, Field(description="Filter by USC title number (for USCODE collection)")
    ] = "",
    section: Annotated[str, Field(description="Filter by section number")] = "",
    start_date: Annotated[
        str, Field(description="Filter results after this date (YYYY-MM-DD)")
    ] = "",
    end_date: Annotated[
        str, Field(description="Filter results before this date (YYYY-MM-DD)")
    ] = "",
    page_size: Annotated[
        int, Field(description="Number of results per page", ge=1, le=100)
    ] = 50,
    offset_mark: Annotated[
        str, Field(description="Pagination offset mark for next page")
    ] = "*",
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Search for US statutes across statute-related collections.

    Searches within United States Code (USCODE), Statutes at Large
    (STATUTE), Public and Private Laws (PLAW), and Statutes Compilations
    (COMPS). When no specific collection is provided, results are filtered
    to only statute-related collections.

    Args:
        query: Search query text for US statutes.
        collection: Optional statute collection code to restrict the search.
        congress: Optional Congress number filter (for PLAW).
        title_number: Optional USC title number filter (for USCODE).
        section: Optional section number filter.
        start_date: Optional start date filter (YYYY-MM-DD).
        end_date: Optional end date filter (YYYY-MM-DD).
        page_size: Number of results per page.
        offset_mark: Pagination offset mark for the next page.
        ctx: Optional context for logging and error reporting.

    Returns:
        dict: Search results with statute packages and metadata.

    Note:
        The GovInfo search API rejects dedicated section facets and quoted
        values with HTTP 500, so ``section`` is matched as free text, and
        date ranges use the supported ``publishdate:range(start,end)``
        syntax. Date filtering is most meaningful for the PLAW collection.

    Raises:
        ValueError: If GOVINFO_API_KEY is not found in environment variables.
        ValueError: If an invalid collection code is provided.

    """
    await log_info(ctx, f"Searching US statutes with query: {query}")
    _require_api_key()

    if collection and collection not in STATUTE_COLLECTIONS:
        msg = (
            f"Invalid collection '{collection}'. Must be one of: "
            f"{', '.join(STATUTE_COLLECTIONS.keys())}"
        )
        await log_error(ctx, msg)
        raise ValueError(msg)

    if collection:
        search_query = f"collection:{collection} AND ({query})"
    else:
        # Search across all statute collections
        collections_query = " OR ".join(
            f"collection:{code}" for code in STATUTE_COLLECTIONS
        )
        search_query = f"({collections_query}) AND ({query})"

    if congress is not None:
        search_query = f"{search_query} AND congress:{congress}"
    if title_number:
        search_query = f"{search_query} AND title:{title_number}"
    if section:
        search_query = f"{search_query} AND {section}"
    if start_date or end_date:
        range_start = start_date or "0001-01-01"
        range_end = end_date or "9999-12-31"
        search_query = (
            f"{search_query} AND publishdate:range({range_start},{range_end})"
        )

    request_body = {
        "query": search_query,
        "pageSize": page_size,
        "offsetMark": offset_mark,
        "sorts": [{"field": "score", "sortOrder": "DESC"}],
    }

    data = await _search_govinfo(request_body, ctx, "Statute search")

    # Filter results to only statute collections when no specific
    # collection was requested
    if not collection and "results" in data:
        data["results"] = [
            result
            for result in data.get("results", [])
            if result.get("collectionCode") in STATUTE_COLLECTIONS
        ]
        data["count"] = len(data["results"])

    await log_info(
        ctx, f"Found {data.get('count', 0)} statute results for query: {query}"
    )
    return data


@govinfo_server.tool(tags={"requires-govinfo-key"})
async def get_uscode_title(
    title_number: Annotated[
        str, Field(description="USC title number (e.g., '42' for Title 42)")
    ],
    edition: Annotated[
        str, Field(description="Optional USC edition date (YYYY-MM-DD)")
    ] = "",
    chapter: Annotated[str, Field(description="Optional chapter number filter")] = "",
    section: Annotated[str, Field(description="Optional section number filter")] = "",
    page_size: Annotated[
        int, Field(description="Number of results per page", ge=1, le=100)
    ] = 50,
    offset_mark: Annotated[
        str, Field(description="Pagination offset mark for next page")
    ] = "*",
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Search for United States Code sections within a specific title.

    Uses the GovInfo search API to find USC sections, chapters, and
    subchapters for a given title number.

    Args:
        title_number: The USC title number to search.
        edition: Optional USC edition date filter (YYYY-MM-DD).
        chapter: Optional chapter number filter.
        section: Optional section number filter.
        page_size: Number of results per page.
        offset_mark: Pagination offset mark for the next page.
        ctx: Optional context for logging and error reporting.

    Returns:
        dict: Search results with USC packages and metadata.

    Note:
        Requires the GOVINFO_API_KEY environment variable; the shared key
        check raises ValueError when the key is missing. The GovInfo
        search API has no dedicated chapter/section facets, so those
        filters are matched as free text and may return related sections.

    """
    await log_info(ctx, f"Searching USC Title {title_number}")
    _require_api_key()

    # Build search query for USC title using field operators and a
    # collection filter
    search_query = f"collection:USCODE AND title:{title_number}"
    # The GovInfo search API rejects the chapter/section facets with
    # HTTP 500, so these filters are appended as free-text terms instead.
    if edition:
        search_query += f" AND publishdate:{edition}"
    if chapter:
        search_query += f" AND {chapter}"
    if section:
        search_query += f" AND {section}"

    request_body = {
        "query": search_query,
        "pageSize": page_size,
        "offsetMark": offset_mark,
        "sorts": [{"field": "title", "sortOrder": "ASC"}],
    }

    data = await _search_govinfo(request_body, ctx, "USC title search")
    await log_info(
        ctx, f"Found {data.get('count', 0)} results for USC Title {title_number}"
    )
    return data


@govinfo_server.tool(tags={"requires-govinfo-key"}, task=True)
async def get_statute_content(
    package_id: Annotated[
        str, Field(description="Package ID (e.g., 'PLAW-117publ58')")
    ],
    content_type: Annotated[
        str,
        Field(description="Content type: 'summary', 'xml', 'pdf', or 'text'"),
    ] = "summary",
    granule_id: Annotated[
        str, Field(description="Optional granule ID for specific section")
    ] = "",
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get content or metadata for a specific statute package.

    Retrieves a package or granule summary, or locates download links for
    content in XML, PDF, or text formats.

    Note:
        For content requests (xml, pdf, text), the GovInfo API returns
        download URLs rather than the actual file content; the resolved
        URL is placed in ``requested_content_url``.

    Args:
        package_id: The GovInfo package ID to retrieve.
        content_type: The requested content type.
        granule_id: Optional granule ID for a specific section.
        ctx: Optional context for logging and error reporting.

    Returns:
        dict: The package/granule summary or download link information.

    Raises:
        ValueError: If GOVINFO_API_KEY is not found in environment variables.
        ValueError: If an invalid content_type is provided.

    """
    await log_info(ctx, f"Getting {content_type} for package: {package_id}")
    _require_api_key()

    if content_type not in _VALID_CONTENT_TYPES:
        msg = (
            f"Invalid content_type '{content_type}'. "
            f"Must be one of: {', '.join(_VALID_CONTENT_TYPES)}"
        )
        await log_error(ctx, msg)
        raise ValueError(msg)

    if granule_id:
        url = f"{GOVINFO_BASE_URL}/packages/{package_id}/granules/{granule_id}/summary"
    else:
        url = f"{GOVINFO_BASE_URL}/packages/{package_id}/summary"

    data = await _govinfo_get(url, ctx, "Statute content retrieval")

    # For content requests, resolve the matching download URL
    if content_type != "summary":
        download_links = data.get("download", {})
        content_key = _CONTENT_KEY_MAP.get(content_type)
        if content_key and content_key in download_links:
            data["requested_content_url"] = download_links[content_key]
            data["content_type"] = content_type
            await log_info(ctx, f"Found {content_type} download link for {package_id}")
        else:
            await log_info(ctx, f"No {content_type} content available for {package_id}")

    return data


@govinfo_server.tool(tags={"requires-govinfo-key"})
async def list_statute_collections(
    ctx: Context | None = None,
) -> dict[str, Any]:
    """List all available statute-related collections with descriptions.

    Returns information about the statute collections available for search
    through the GovInfo API.

    Args:
        ctx: Optional context for logging.

    Returns:
        dict: Statute collections and their descriptions.

    """
    await log_info(ctx, "Listing available statute collections")
    return {
        "statute_collections": [
            {
                "code": code,
                "name": name,
                "description": _get_collection_description(code),
            }
            for code, name in STATUTE_COLLECTIONS.items()
        ],
        "total_collections": len(STATUTE_COLLECTIONS),
    }
