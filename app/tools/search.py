"""Search tools for CourtListener MCP server."""

from typing import Annotated, Any

from fastmcp import Context, FastMCP
import httpx
from pydantic import Field

from app.tools.common import (
    API_KEY,
    DEFAULT_TIMEOUT,
    SEARCH_URL,
    auth_headers,
    log_error,
    log_info,
)

# Create the search server
search_server: FastMCP[Any] = FastMCP(
    name="CourtListener Search Server",
    instructions=(
        "Search server for CourtListener legal database providing comprehensive "
        "search capabilities. This server enables searching across different "
        "types of legal content including: court opinions and cases, oral "
        "argument audio recordings, federal dockets from PACER, RECAP filing "
        "documents, and judges/legal professionals. Search parameters include "
        "date ranges, court filters, case names, judge names, and full-text "
        "queries. Results are returned with detailed metadata and can be sorted "
        "by relevance or date."
    ),
)


def _build_search_params(
    q: str,
    order_by: str,
    search_type: str,
    filters: dict[str, str | int],
    limit: int,
) -> dict[str, Any]:
    """Build query parameters for a CourtListener search request.

    Args:
        q: Search query text.
        order_by: Result ordering expression.
        search_type: CourtListener search type code (e.g., 'o', 'd', 'rd').
        filters: Optional filter name/value pairs; empty values are skipped.
        limit: Maximum number of results to request.

    Returns:
        dict[str, Any]: Query parameters for the search request.

    """
    params: dict[str, Any] = {"q": q, "order_by": order_by, "type": search_type}
    for key, value in filters.items():
        if value:
            params[key] = str(value)
    if limit:
        # V4 uses 'hit' instead of 'limit'
        params["hit"] = str(limit)
    return params


async def _execute_search(
    params: dict[str, Any],
    ctx: Context | None,
    result_label: str,
) -> dict[str, Any]:
    """Execute a search request against the CourtListener search endpoint.

    Args:
        params: Query parameters for the search request.
        ctx: Optional FastMCP context for logging and error reporting.
        result_label: Human-readable label used in log messages.

    Returns:
        dict[str, Any]: The raw search response data.

    Raises:
        httpx.HTTPStatusError: If the API returns an HTTP error status.

    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                SEARCH_URL,
                params=params,
                headers=auth_headers(),
                timeout=DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
    except httpx.HTTPStatusError as e:
        await log_error(ctx, f"HTTP error: {e}")
        raise
    except Exception as e:
        await log_error(ctx, f"Search error: {e}")
        raise

    await log_info(ctx, f"Found {data.get('count', 0)} {result_label}")
    return data


@search_server.tool(tags={"requires-courtlistener-key"})
async def opinions(  # ruff: ignore[too-many-arguments, too-many-positional-arguments] (MCP tool signature is the public API)
    q: Annotated[str, Field(description="Search query for full text of opinions")],
    court: Annotated[
        str, Field(description="Court ID filter (e.g., 'scotus', 'ca9')")
    ] = "",
    case_name: Annotated[str, Field(description="Filter by case name")] = "",
    judge: Annotated[str, Field(description="Filter by judge name")] = "",
    filed_after: Annotated[
        str, Field(description="Only show opinions filed after this date (YYYY-MM-DD)")
    ] = "",
    filed_before: Annotated[
        str, Field(description="Only show opinions filed before this date (YYYY-MM-DD)")
    ] = "",
    cited_gt: Annotated[
        int, Field(description="Minimum number of times opinion has been cited", ge=0)
    ] = 0,
    cited_lt: Annotated[
        int, Field(description="Maximum number of times opinion has been cited", ge=0)
    ] = 0,
    order_by: Annotated[
        str,
        Field(description="Sort by 'score desc', 'dateFiled desc', or 'dateFiled asc'"),
    ] = "score desc",
    limit: Annotated[
        int, Field(description="Maximum results to return", ge=1, le=100)
    ] = 20,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Search case law opinion clusters with nested Opinion documents.

    Searches CourtListener case law and returns up to `limit` matching
    clusters, each with its nested Opinion documents.

    Returns:
        A dictionary containing search results with opinion clusters and
        nested opinions.

    Note:
        Works without an API key through public API access; providing the
        COURT_LISTENER_API_KEY improves rate limits.

    """
    await log_info(ctx, f"Searching opinions with query: {q}")

    if not API_KEY:
        await log_info(ctx, "Using public API access (no authentication)")

    params = _build_search_params(
        q,
        order_by,
        "o",  # Opinion type for V4 API
        {
            "court": court,
            "case_name": case_name,
            "judge": judge,
            "filed_after": filed_after,
            "filed_before": filed_before,
            "cited_gt": cited_gt,
            "cited_lt": cited_lt,
        },
        limit,
    )
    return await _execute_search(params, ctx, "opinions")


@search_server.tool(tags={"requires-courtlistener-key"})
async def dockets(  # ruff: ignore[too-many-arguments, too-many-positional-arguments] (MCP tool signature is the public API)
    q: Annotated[str, Field(description="Search query for docket text")],
    court: Annotated[
        str, Field(description="Court ID filter (e.g., 'scotus', 'ca9')")
    ] = "",
    case_name: Annotated[str, Field(description="Filter by case name")] = "",
    judge: Annotated[str, Field(description="Filter by judge name")] = "",
    filed_after: Annotated[
        str, Field(description="Only show dockets filed after this date (YYYY-MM-DD)")
    ] = "",
    filed_before: Annotated[
        str, Field(description="Only show dockets filed before this date (YYYY-MM-DD)")
    ] = "",
    docket_number: Annotated[str, Field(description="Filter by docket number")] = "",
    nature_of_suit: Annotated[
        int, Field(description="Nature of suit code filter", ge=0)
    ] = 0,
    order_by: Annotated[
        str,
        Field(description="Sort by 'score desc', 'dateFiled desc', or 'dateFiled asc'"),
    ] = "score desc",
    limit: Annotated[
        int, Field(description="Maximum results to return", ge=1, le=100)
    ] = 20,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Search federal case dockets in CourtListener with PACER data.

    Args:
        q: Search query for docket text.
        court: Court ID filter (e.g., 'scotus', 'ca9').
        case_name: Filter by case name.
        judge: Filter by judge name.
        filed_after: Only show dockets filed after this date (YYYY-MM-DD).
        filed_before: Only show dockets filed before this date (YYYY-MM-DD).
        docket_number: Filter by docket number.
        nature_of_suit: Nature of suit code filter.
        order_by: Sort by 'score desc', 'dateFiled desc', or 'dateFiled asc'.
        limit: Maximum results to return.
        ctx: Optional context for logging and error reporting.

    Returns:
        dict: The search results with docket information.

    Raises:
        ValueError: If the COURT_LISTENER_API_KEY is not set.

    """
    await log_info(ctx, f"Searching dockets with query: {q}")

    if not API_KEY:
        error_msg = "COURT_LISTENER_API_KEY not found in environment variables"
        await log_error(ctx, error_msg)
        raise ValueError(error_msg)

    params = _build_search_params(
        q,
        order_by,
        "d",  # Docket type for V4 API
        {
            "court": court,
            "case_name": case_name,
            "judge": judge,
            "filed_after": filed_after,
            "filed_before": filed_before,
            "docket_number": docket_number,
            "nature_of_suit": nature_of_suit,
        },
        limit,
    )
    return await _execute_search(params, ctx, "dockets")


@search_server.tool(tags={"requires-courtlistener-key"})
async def dockets_with_documents(  # ruff: ignore[too-many-arguments, too-many-positional-arguments] (MCP tool signature is the public API)
    q: Annotated[
        str,
        Field(
            description=(
                "Search query for docket or related document content, e.g., "
                "'voting rights'"
            )
        ),
    ],
    court: Annotated[
        str, Field(description="Court ID filter (e.g., 'scotus', 'ca9')")
    ] = "",
    case_name: Annotated[str, Field(description="Filter by case name")] = "",
    judge: Annotated[str, Field(description="Filter by judge name")] = "",
    filed_after: Annotated[
        str, Field(description="Only show dockets filed after this date (YYYY-MM-DD)")
    ] = "",
    filed_before: Annotated[
        str, Field(description="Only show dockets filed before this date (YYYY-MM-DD)")
    ] = "",
    docket_number: Annotated[str, Field(description="Filter by docket number")] = "",
    nature_of_suit: Annotated[
        int, Field(description="Nature of suit code filter", ge=0)
    ] = 0,
    order_by: Annotated[
        str,
        Field(description="Sort by 'score desc', 'dateFiled desc', or 'dateFiled asc'"),
    ] = "score desc",
    limit: Annotated[
        int, Field(description="Maximum results to return", ge=1, le=100)
    ] = 20,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Search federal cases (dockets) with up to three nested documents.

    If there are more than three matching documents, the more_docs field will
    be true.

    Args:
        q: Search query for docket or related document content.
        court: Court ID filter (e.g., 'scotus', 'ca9').
        case_name: Filter by case name.
        judge: Filter by judge name.
        filed_after: Only show dockets filed after this date (YYYY-MM-DD).
        filed_before: Only show dockets filed before this date (YYYY-MM-DD).
        docket_number: Filter by docket number.
        nature_of_suit: Nature of suit code filter.
        order_by: Sort by 'score desc', 'dateFiled desc', or 'dateFiled asc'.
        limit: Maximum results to return.
        ctx: Optional context for logging and error reporting.

    Returns:
        dict: The search results with dockets and their nested documents.

    """
    await log_info(ctx, f"Searching dockets with documents using query: {q}")

    if not API_KEY:
        await log_info(ctx, "Using public API access (no authentication)")

    params = _build_search_params(
        q,
        order_by,
        "d",  # Docket type for V4 API (includes nested documents)
        {
            "court": court,
            "case_name": case_name,
            "judge": judge,
            "filed_after": filed_after,
            "filed_before": filed_before,
            "docket_number": docket_number,
            "nature_of_suit": nature_of_suit,
        },
        limit,
    )
    return await _execute_search(params, ctx, "dockets with documents")


@search_server.tool(tags={"requires-courtlistener-key"})
async def recap_documents(  # ruff: ignore[too-many-arguments, too-many-positional-arguments] (MCP tool signature is the public API)
    q: Annotated[str, Field(description="Search query for document content")],
    court: Annotated[
        str, Field(description="Court ID filter (e.g., 'scotus', 'ca9')")
    ] = "",
    case_name: Annotated[str, Field(description="Filter by case name")] = "",
    docket_number: Annotated[str, Field(description="Filter by docket number")] = "",
    available_only: Annotated[
        bool,
        Field(description="If True, only show documents available for free"),
    ] = False,
    document_type: Annotated[
        str, Field(description="Filter by document type (e.g., 'minutes', 'opinion')")
    ] = "",
    order_by: Annotated[
        str,
        Field(description="Sort by 'score desc', 'dateFiled desc', or 'dateFiled asc'"),
    ] = "score desc",
    limit: Annotated[
        int, Field(description="Maximum results to return", ge=1, le=100)
    ] = 20,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Search RECAP filing documents in CourtListener with PACER data.

    Args:
        q: Search query for document content.
        court: Court ID filter (e.g., 'scotus', 'ca9').
        case_name: Filter by case name.
        docket_number: Filter by docket number.
        available_only: If True, only show documents available for free.
        document_type: Filter by document type (e.g., 'minutes', 'opinion').
        order_by: Sort by 'score desc', 'dateFiled desc', or 'dateFiled asc'.
        limit: Maximum results to return.
        ctx: Optional context for logging and error reporting.

    Returns:
        dict: The search results with document information.

    Raises:
        ValueError: If the COURT_LISTENER_API_KEY is not set.

    """
    await log_info(ctx, f"Searching RECAP documents with query: {q}")

    if not API_KEY:
        error_msg = "COURT_LISTENER_API_KEY not found in environment variables"
        await log_error(ctx, error_msg)
        raise ValueError(error_msg)

    params = _build_search_params(
        q,
        order_by,
        "rd",  # RECAP documents type for V4 API
        {
            "court": court,
            "case_name": case_name,
            "docket_number": docket_number,
            "available_only": "true" if available_only else "",
            "document_type": document_type,
        },
        limit,
    )
    return await _execute_search(params, ctx, "RECAP documents")


@search_server.tool(tags={"requires-courtlistener-key"})
async def audio(  # ruff: ignore[too-many-arguments, too-many-positional-arguments] (MCP tool signature is the public API)
    q: Annotated[str, Field(description="Search query for oral argument audio")],
    court: Annotated[
        str, Field(description="Court ID filter (e.g., 'scotus', 'ca9')")
    ] = "",
    case_name: Annotated[str, Field(description="Filter by case name")] = "",
    judge: Annotated[str, Field(description="Filter by judge name")] = "",
    argued_after: Annotated[
        str, Field(description="Only show audio argued after this date (YYYY-MM-DD)")
    ] = "",
    argued_before: Annotated[
        str, Field(description="Only show audio argued before this date (YYYY-MM-DD)")
    ] = "",
    order_by: Annotated[
        str,
        Field(
            description=("Sort by 'score desc', 'dateArgued desc', or 'dateArgued asc'")
        ),
    ] = "score desc",
    limit: Annotated[
        int, Field(description="Maximum results to return", ge=1, le=100)
    ] = 20,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Search oral argument audio recordings in CourtListener.

    Args:
        q: Search query for oral argument audio.
        court: Court ID filter (e.g., 'scotus', 'ca9').
        case_name: Filter by case name.
        judge: Filter by judge name.
        argued_after: Only show audio argued after this date (YYYY-MM-DD).
        argued_before: Only show audio argued before this date (YYYY-MM-DD).
        order_by: Sort by 'score desc', 'dateArgued desc', or 'dateArgued asc'.
        limit: Maximum results to return.
        ctx: Optional context for logging and error reporting.

    Returns:
        dict: The search results with audio information.

    Note:
        Works without an API key through public API access; providing the
        COURT_LISTENER_API_KEY improves rate limits.

    """
    await log_info(ctx, f"Searching oral argument audio with query: {q}")

    if not API_KEY:
        await log_info(ctx, "Using public API access (no authentication)")

    params = _build_search_params(
        q,
        order_by,
        "oa",  # Oral arguments type for V4 API
        {
            "court": court,
            "case_name": case_name,
            "judge": judge,
            "argued_after": argued_after,
            "argued_before": argued_before,
        },
        limit,
    )
    return await _execute_search(params, ctx, "audio recordings")


@search_server.tool(tags={"requires-courtlistener-key"})
async def people(  # ruff: ignore[too-many-arguments, too-many-positional-arguments] (MCP tool signature is the public API)
    q: Annotated[
        str,
        Field(
            description=(
                "Search query for judges or legal professionals, e.g., 'John Roberts'"
            )
        ),
    ],
    name: Annotated[
        str, Field(description="Filter by full name (e.g., 'John Roberts')")
    ] = "",
    court: Annotated[
        str, Field(description="Court ID filter (e.g., 'scotus', 'ca9')")
    ] = "",
    position_type: Annotated[str, Field(description="Filter by position type")] = "",
    order_by: Annotated[
        str,
        Field(description="Sort by 'score desc', 'name_rev desc', or 'dob desc'"),
    ] = "score desc",
    limit: Annotated[
        int, Field(description="Maximum results to return", ge=1, le=100)
    ] = 20,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Search judges and legal professionals in CourtListener.

    Args:
        q: Search query for judges or legal professionals.
        name: Filter by full name (e.g., 'John Roberts').
        court: Court ID filter (e.g., 'scotus', 'ca9').
        position_type: Filter by position type.
        order_by: Sort by 'score desc', 'name_rev desc', or 'dob desc'.
        limit: Maximum results to return.
        ctx: Optional context for logging and error reporting.

    Returns:
        dict: The search results with people information.

    Raises:
        ValueError: If the COURT_LISTENER_API_KEY is not set.

    """
    await log_info(ctx, f"Searching judges/legal professionals with query: {q}")

    if not API_KEY:
        error_msg = "COURT_LISTENER_API_KEY not found in environment variables"
        await log_error(ctx, error_msg)
        raise ValueError(error_msg)

    params = _build_search_params(
        q,
        order_by,
        "p",  # People type for V4 API
        {"name": name, "court": court, "position_type": position_type},
        limit,
    )
    return await _execute_search(params, ctx, "people")
