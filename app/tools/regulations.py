"""Regulations.gov tools for the CourtListener MCP server.

Provides search and retrieval of federal rulemaking documents backed by
the documents endpoint of the official Regulations.gov v4 REST API
(api.regulations.gov). All tools require the ``REGULATIONS_API_KEY``
environment variable (a free api.data.gov key).
"""

# Regulations tool definitions legitimately expose more than the
# configured maximum of six parameters, matching the upstream
# Regulations.gov API surface.
# ruff: file-ignore[too-many-arguments, too-many-positional-arguments]

import os
import re
from typing import Annotated, Any, Literal

from fastmcp import Context, FastMCP
import httpx
from pydantic import Field

from app.tools.common import DEFAULT_TIMEOUT, log_error, log_info

# Regulations.gov API configuration
API_KEY: str | None = os.getenv("REGULATIONS_API_KEY")
REGULATIONS_BASE_URL = "https://api.regulations.gov"
DOCUMENTS_URL = f"{REGULATIONS_BASE_URL}/v4/documents"

# Create the Regulations.gov server
regulations_server: FastMCP[Any] = FastMCP(
    name="Regulations.gov Server",
    instructions=(
        "Federal rulemaking server backed by the official Regulations.gov "
        "API. Provides search and retrieval of federal regulation "
        "documents (rules, proposed rules, notices). Use these tools to "
        "find dockets and documents by keyword, agency, document type, or "
        "posted date, and retrieve document details with attachments. All "
        "tools require the REGULATIONS_API_KEY environment variable."
    ),
)

# Precompiled validator for YYYY-MM-DD date filters
_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _regulations_headers() -> dict[str, str]:
    """Build request headers with the Regulations.gov API key.

    Returns:
        dict[str, str]: Headers containing the ``X-Api-Key`` header when
        the REGULATIONS_API_KEY environment variable is set, empty
        otherwise.

    """
    headers: dict[str, str] = {}
    if API_KEY:
        headers["X-Api-Key"] = API_KEY
    return headers


def _require_api_key() -> None:
    """Ensure the Regulations.gov API key is configured.

    Raises:
        ValueError: If REGULATIONS_API_KEY is not found in environment
            variables.

    """
    if not API_KEY:
        msg = "REGULATIONS_API_KEY not found in environment variables"
        raise ValueError(msg)


async def _regulations_get(
    url: str,
    params: dict[str, Any],
    ctx: Context | None,
    error_label: str,
) -> dict[str, Any]:
    """Execute a GET request against the Regulations.gov API.

    Args:
        url: The full Regulations.gov API URL to request.
        params: Query parameters for the request.
        ctx: Optional FastMCP context for logging and error reporting.
        error_label: Human-readable label used in error log messages.

    Returns:
        dict[str, Any]: The parsed JSON response from the API.

    Raises:
        httpx.HTTPStatusError: If the API returns an HTTP error status.

    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                params=params,
                headers=_regulations_headers(),
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


@regulations_server.tool(tags={"requires-regulations-key"})
async def search_documents(
    query: Annotated[
        str,
        Field(
            description="Search query text for federal documents",
            min_length=1,
            max_length=500,
        ),
    ],
    filter_agency: Annotated[
        str | None,
        Field(description="Agency ID filter (e.g. 'EPA', 'DOT')"),
    ] = None,
    filter_posted_date: Annotated[
        str | None,
        Field(description="Posted date filter in YYYY-MM-DD format"),
    ] = None,
    filter_document_type: Annotated[
        str | None,
        Field(
            description=(
                "Document type filter (e.g. 'Rule', 'Proposed Rule', 'Notice')"
            )
        ),
    ] = None,
    sort: Annotated[
        Literal["date", "relevance", "title"] | None,
        Field(description="Sort order for results"),
    ] = None,
    page_size: Annotated[
        int,
        Field(
            description="Results per page (the API requires a value of 5-250)",
            ge=5,
            le=250,
        ),
    ] = 25,
    page: Annotated[
        int,
        Field(description="Page number for pagination", ge=1),
    ] = 1,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Search for federal regulations and documents on Regulations.gov.

    Searches rulemaking documents (rules, proposed rules, notices, and
    supporting material) by keyword, with optional filters for agency,
    posted date, and document type.

    Args:
        query: Search query text for federal documents.
        filter_agency: Optional agency ID filter (e.g. 'EPA', 'DOT').
        filter_posted_date: Optional posted date filter (YYYY-MM-DD).
        filter_document_type: Optional document type filter.
        sort: Optional sort order (date, relevance, or title).
        page_size: Number of results per page (the API requires 5-250).
        page: Page number for pagination.
        ctx: Optional context for logging and error reporting.

    Returns:
        dict: Search results with document metadata, pagination info,
        and relationships.

    Note:
        Requires the REGULATIONS_API_KEY environment variable; the shared
        key check raises ValueError when the key is missing.

    Raises:
        ValueError: If the posted date filter is not in YYYY-MM-DD
            format.

    """
    await log_info(ctx, f"Searching Regulations.gov documents: {query}")
    _require_api_key()

    if filter_posted_date and not _DATE_PATTERN.match(filter_posted_date):
        msg = (
            f"filter_posted_date must be in YYYY-MM-DD format, "
            f"got '{filter_posted_date}'"
        )
        await log_error(ctx, msg)
        raise ValueError(msg)

    params: dict[str, Any] = {
        "filter[searchTerm]": query,
        "page[size]": page_size,
        "page[number]": page,
    }
    if filter_agency:
        params["filter[agencyId]"] = filter_agency
    if filter_posted_date:
        params["filter[postedDate]"] = filter_posted_date
    if filter_document_type:
        params["filter[documentType]"] = filter_document_type
    if sort:
        params["sort"] = sort

    data = await _regulations_get(DOCUMENTS_URL, params, ctx, "Document search")
    await log_info(ctx, f"Document search complete for query: {query}")
    return data


@regulations_server.tool(tags={"requires-regulations-key"})
async def get_document(
    document_id: Annotated[
        str,
        Field(
            description=("Regulations.gov document ID (e.g. 'EPA-2020-1234-0001')"),
            min_length=1,
        ),
    ],
    include_attachments: Annotated[
        bool,
        Field(description="Include document attachments in the response"),
    ] = False,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get detailed information about a specific regulation document.

    Retrieves the full Regulations.gov record for a single document,
    including its attributes, docket and comment relationships, and
    optionally its attached files.

    Args:
        document_id: Regulations.gov document ID.
        include_attachments: Whether to include attachments in the
            response.
        ctx: Optional context for logging and error reporting.

    Returns:
        dict: Document details from the Regulations.gov API.

    Note:
        Requires the REGULATIONS_API_KEY environment variable; the shared
        key check raises ValueError when the key is missing.

    """
    await log_info(ctx, f"Getting Regulations.gov document: {document_id}")
    _require_api_key()

    params: dict[str, Any] = {}
    if include_attachments:
        params["include"] = "attachments"

    data = await _regulations_get(
        f"{DOCUMENTS_URL}/{document_id}", params, ctx, "Get document"
    )
    await log_info(ctx, f"Retrieved document: {document_id}")
    return data
