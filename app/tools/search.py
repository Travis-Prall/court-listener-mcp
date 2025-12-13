"""Search tools for CourtListener MCP server."""

from typing import Annotated, Any

from fastmcp import Context, FastMCP
import httpx
from pydantic import Field

from app.config import config, get_auth_headers, get_http_client

# Create the search server
search_server: FastMCP[Any] = FastMCP(
    name="CourtListener Search Server",
    instructions="Search server for CourtListener legal database providing comprehensive search capabilities. "
    "This server enables searching across different types of legal content including: "
    "court opinions and cases, oral argument audio recordings, federal dockets from PACER, "
    "RECAP filing documents, and judges/legal professionals. "
    "Search parameters include date ranges, court filters, case names, judge names, and full-text queries. "
    "Results are returned with detailed metadata and can be sorted by relevance or date.",
)


async def _search_courtlistener(
    ctx: Context,
    resource_type: str,
    search_type: str,
    q: str,
    order_by: str,
    limit: int,
    filters: dict[str, Any],
) -> dict[str, Any]:
    """Execute a search against the CourtListener API.

    Args:
        ctx: The FastMCP context for logging and accessing shared resources.
        resource_type: Human-readable name of the resource type (for logging).
        search_type: The CourtListener V4 API type parameter (e.g., 'o', 'd', 'p').
        q: The search query string.
        order_by: Sort order for results.
        limit: Maximum number of results to return.
        filters: Dictionary of optional filter parameters.

    Returns:
        dict: The search results as returned by the CourtListener API.

    Raises:
        ValueError: If COURT_LISTENER_API_KEY is not found in environment variables.
        httpx.HTTPStatusError: If the API request fails.

    """
    await ctx.info(f"Searching {resource_type} with query: {q}")

    headers = get_auth_headers()

    params: dict[str, str | int] = {
        "q": q,
        "order_by": order_by,
        "type": search_type,
    }

    # Add limit (V4 uses 'hit' instead of 'limit')
    if limit:
        params["hit"] = limit

    # Add optional filters (only non-empty/non-zero values)
    for key, value in filters.items():
        if value:
            params[key] = value

    try:
        async with get_http_client(ctx) as http_client:
            response = await http_client.get(
                f"{config.courtlistener_base_url}search/",
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        await ctx.info(f"Found {data.get('count', 0)} {resource_type}")
        return data

    except httpx.HTTPStatusError as e:
        await ctx.error(f"HTTP error: {e}")
        raise
    except Exception as e:
        await ctx.error(f"Search error: {e}")
        raise


@search_server.tool()
async def opinions(
    q: Annotated[str, Field(description="Search query for full text of opinions")],
    ctx: Context,
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
) -> dict[str, Any]:
    """Search case law opinion clusters with nested Opinion documents in CourtListener."""
    return await _search_courtlistener(
        ctx=ctx,
        resource_type="opinions",
        search_type="o",
        q=q,
        order_by=order_by,
        limit=limit,
        filters={
            "court": court,
            "case_name": case_name,
            "judge": judge,
            "filed_after": filed_after,
            "filed_before": filed_before,
            "cited_gt": cited_gt,
            "cited_lt": cited_lt,
        },
    )


@search_server.tool()
async def dockets(
    q: Annotated[str, Field(description="Search query for docket text")],
    ctx: Context,
    court: Annotated[
        str, Field(description="Court ID filter (e.g., 'scotus', 'ca9')")
    ] = "",
    case_name: Annotated[str, Field(description="Filter by case name")] = "",
    docket_number: Annotated[
        str, Field(description="Specific docket number to search for")
    ] = "",
    date_filed_after: Annotated[
        str, Field(description="Filter dockets filed after this date (YYYY-MM-DD)")
    ] = "",
    date_filed_before: Annotated[
        str, Field(description="Filter dockets filed before this date (YYYY-MM-DD)")
    ] = "",
    party_name: Annotated[str, Field(description="Filter by party name")] = "",
    order_by: Annotated[
        str,
        Field(description="Sort by 'score desc', 'dateFiled desc', or 'dateFiled asc'"),
    ] = "score desc",
    limit: Annotated[
        int, Field(description="Maximum results to return", ge=1, le=100)
    ] = 20,
) -> dict[str, Any]:
    """Search federal cases (dockets) from PACER in CourtListener."""
    return await _search_courtlistener(
        ctx=ctx,
        resource_type="dockets",
        search_type="d",
        q=q,
        order_by=order_by,
        limit=limit,
        filters={
            "court": court,
            "case_name": case_name,
            "docket_number": docket_number,
            "date_filed_after": date_filed_after,
            "date_filed_before": date_filed_before,
            "party_name": party_name,
        },
    )


@search_server.tool()
async def dockets_with_documents(
    q: Annotated[str, Field(description="Search query for federal cases")],
    ctx: Context,
    court: Annotated[
        str, Field(description="Court ID filter (e.g., 'scotus', 'ca9')")
    ] = "",
    case_name: Annotated[str, Field(description="Filter by case name")] = "",
    docket_number: Annotated[
        str, Field(description="Specific docket number to search for")
    ] = "",
    date_filed_after: Annotated[
        str, Field(description="Filter dockets filed after this date (YYYY-MM-DD)")
    ] = "",
    date_filed_before: Annotated[
        str, Field(description="Filter dockets filed before this date (YYYY-MM-DD)")
    ] = "",
    party_name: Annotated[str, Field(description="Filter by party name")] = "",
    order_by: Annotated[
        str,
        Field(description="Sort by 'score desc', 'dateFiled desc', or 'dateFiled asc'"),
    ] = "score desc",
    limit: Annotated[
        int, Field(description="Maximum results to return", ge=1, le=100)
    ] = 20,
) -> dict[str, Any]:
    """Search federal cases (dockets) with up to three nested documents.

    If there are more than three matching documents, the more_docs field will be true.
    """
    return await _search_courtlistener(
        ctx=ctx,
        resource_type="dockets with documents",
        search_type="r",
        q=q,
        order_by=order_by,
        limit=limit,
        filters={
            "court": court,
            "case_name": case_name,
            "docket_number": docket_number,
            "date_filed_after": date_filed_after,
            "date_filed_before": date_filed_before,
            "party_name": party_name,
        },
    )


@search_server.tool()
async def recap_documents(
    q: Annotated[str, Field(description="Search query for RECAP filing documents")],
    ctx: Context,
    court: Annotated[
        str, Field(description="Court ID filter (e.g., 'scotus', 'ca9')")
    ] = "",
    case_name: Annotated[str, Field(description="Filter by case name")] = "",
    docket_number: Annotated[
        str, Field(description="Specific docket number to search for")
    ] = "",
    document_number: Annotated[
        str, Field(description="Specific document number to search for")
    ] = "",
    attachment_number: Annotated[
        str, Field(description="Specific attachment number to search for")
    ] = "",
    filed_after: Annotated[
        str, Field(description="Filter documents filed after this date (YYYY-MM-DD)")
    ] = "",
    filed_before: Annotated[
        str, Field(description="Filter documents filed before this date (YYYY-MM-DD)")
    ] = "",
    party_name: Annotated[str, Field(description="Filter by party name")] = "",
    order_by: Annotated[
        str,
        Field(description="Sort by 'score desc', 'dateFiled desc', or 'dateFiled asc'"),
    ] = "score desc",
    limit: Annotated[
        int, Field(description="Maximum results to return", ge=1, le=100)
    ] = 20,
) -> dict[str, Any]:
    """Search federal filing documents from PACER in the RECAP archive."""
    return await _search_courtlistener(
        ctx=ctx,
        resource_type="RECAP documents",
        search_type="rd",
        q=q,
        order_by=order_by,
        limit=limit,
        filters={
            "court": court,
            "case_name": case_name,
            "docket_number": docket_number,
            "document_number": document_number,
            "attachment_number": attachment_number,
            "filed_after": filed_after,
            "filed_before": filed_before,
            "party_name": party_name,
        },
    )


@search_server.tool()
async def audio(
    q: Annotated[str, Field(description="Search query for oral argument audio")],
    ctx: Context,
    court: Annotated[
        str, Field(description="Court ID filter (e.g., 'scotus', 'ca9')")
    ] = "",
    case_name: Annotated[str, Field(description="Filter by case name")] = "",
    judge: Annotated[str, Field(description="Filter by judge name")] = "",
    argued_after: Annotated[
        str, Field(description="Filter arguments after this date (YYYY-MM-DD)")
    ] = "",
    argued_before: Annotated[
        str, Field(description="Filter arguments before this date (YYYY-MM-DD)")
    ] = "",
    order_by: Annotated[
        str,
        Field(
            description="Sort by 'score desc', 'dateArgued desc', or 'dateArgued asc'"
        ),
    ] = "score desc",
    limit: Annotated[
        int, Field(description="Maximum results to return", ge=1, le=100)
    ] = 20,
) -> dict[str, Any]:
    """Search oral argument audio recordings in CourtListener."""
    return await _search_courtlistener(
        ctx=ctx,
        resource_type="audio recordings",
        search_type="oa",
        q=q,
        order_by=order_by,
        limit=limit,
        filters={
            "court": court,
            "case_name": case_name,
            "judge": judge,
            "dateArgued_after": argued_after,
            "dateArgued_before": argued_before,
        },
    )


@search_server.tool()
async def people(
    q: Annotated[
        str, Field(description="Search query for judges and legal professionals")
    ],
    ctx: Context,
    name: Annotated[str, Field(description="Filter by person's name")] = "",
    position_type: Annotated[
        str, Field(description="Filter by position type (e.g., 'jud' for judge)")
    ] = "",
    political_affiliation: Annotated[
        str, Field(description="Filter by political affiliation")
    ] = "",
    school: Annotated[str, Field(description="Filter by school attended")] = "",
    appointed_by: Annotated[
        str, Field(description="Filter by appointing authority")
    ] = "",
    selection_method: Annotated[
        str, Field(description="Filter by selection method")
    ] = "",
    order_by: Annotated[
        str, Field(description="Sort by 'score desc' or 'name asc'")
    ] = "score desc",
    limit: Annotated[
        int, Field(description="Maximum results to return", ge=1, le=100)
    ] = 20,
) -> dict[str, Any]:
    """Search judges and legal professionals in the CourtListener database."""
    return await _search_courtlistener(
        ctx=ctx,
        resource_type="people",
        search_type="p",
        q=q,
        order_by=order_by,
        limit=limit,
        filters={
            "name": name,
            "position_type": position_type,
            "political_affiliation": political_affiliation,
            "school": school,
            "appointed_by": appointed_by,
            "selection_method": selection_method,
        },
    )
