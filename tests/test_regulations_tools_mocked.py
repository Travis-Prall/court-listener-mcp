"""Mocked-API tests for the Regulations.gov tools.

All HTTP traffic is intercepted with respx, so these tests exercise the
real Regulations.gov tool code without contacting the live
api.regulations.gov API.
"""

# Pytest assertions are the idiomatic test mechanism in this file.
# ruff: file-ignore[assert, unused-function-argument]

import json
from typing import Any

from fastmcp import Client
from fastmcp.exceptions import ToolError
import httpx
import pytest
import respx

from app.server import mcp
from app.tools.regulations import DOCUMENTS_URL

# Expected values for the mocked Regulations.gov API responses
DOCUMENT_RESULT_COUNT = 2
EXPECTED_DEFAULT_PAGE_SIZE = 25

DOCUMENT_ID = "EPA-2023-0001-0001"


@pytest.fixture
def client() -> Client[Any]:
    """Create a test client connected to the composed MCP server.

    Returns:
        Client: A FastMCP test client connected to the server instance.

    """
    return Client(mcp)


def _documents_response() -> dict[str, Any]:
    """Build a realistic mocked documents search response.

    Returns:
        dict[str, Any]: A JSON:API style documents payload.

    """
    return {
        "data": [
            {
                "id": DOCUMENT_ID,
                "type": "documents",
                "attributes": {
                    "title": "Clean Air Act Implementation",
                    "documentType": "Rule",
                    "postedDate": "2023-06-15",
                },
            },
            {
                "id": "DOT-2023-0002-0001",
                "type": "documents",
                "attributes": {
                    "title": "Highway Safety Standards",
                    "documentType": "Proposed Rule",
                    "postedDate": "2023-07-01",
                },
            },
        ],
        "meta": {"results": {"total": DOCUMENT_RESULT_COUNT}},
    }


@pytest.mark.parametrize(
    ("tool_name", "tool_args"),
    [
        ("regulations_search_documents", {"query": "clean air"}),
        ("regulations_get_document", {"document_id": DOCUMENT_ID}),
    ],
)
@pytest.mark.asyncio
async def test_regulations_tools_require_api_key(
    client: Client[Any], no_api_key: None, tool_name: str, tool_args: dict[str, Any]
) -> None:
    """Every networked Regulations.gov tool requires an API key.

    Args:
        client: FastMCP test client fixture.
        no_api_key: Fixture forcing the Regulations.gov API key to None.
        tool_name: Prefixed MCP tool name to call.
        tool_args: Valid minimal arguments for the tool.

    """
    async with client:
        with pytest.raises(ToolError):
            await client.call_tool(tool_name, tool_args)


@pytest.mark.asyncio
async def test_search_documents_with_api_key(client: Client[Any], api_key: str) -> None:
    """A document search sends the search term and pagination params.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake Regulations.gov API key.

    """
    async with client, respx.mock:
        route = respx.get(f"{DOCUMENTS_URL}").mock(
            return_value=httpx.Response(200, json=_documents_response())
        )
        result = await client.call_tool(
            "regulations_search_documents", {"query": "clean air"}
        )

        assert result.content
        data = json.loads(result.content[0].text)
        assert data["meta"]["results"]["total"] == DOCUMENT_RESULT_COUNT
        assert len(data["data"]) == DOCUMENT_RESULT_COUNT
        assert data["data"][0]["id"] == DOCUMENT_ID

        params = route.calls.last.request.url.params
        assert params["filter[searchTerm]"] == "clean air"
        assert params["page[size]"] == str(EXPECTED_DEFAULT_PAGE_SIZE)
        assert params["page[number]"] == "1"

        headers = route.calls.last.request.headers
        assert headers["X-Api-Key"] == api_key


@pytest.mark.asyncio
async def test_search_documents_with_filters(client: Client[Any], api_key: str) -> None:
    """Optional filters are forwarded as filter[...] query params.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake Regulations.gov API key.

    """
    async with client, respx.mock:
        route = respx.get(f"{DOCUMENTS_URL}").mock(
            return_value=httpx.Response(200, json=_documents_response())
        )
        result = await client.call_tool(
            "regulations_search_documents",
            {
                "query": "emissions",
                "filter_agency": "EPA",
                "filter_posted_date": "2023-06-15",
                "filter_document_type": "Rule",
                "sort": "date",
                "page_size": 10,
                "page": 2,
            },
        )

        assert result.content
        params = route.calls.last.request.url.params
        assert params["filter[searchTerm]"] == "emissions"
        assert params["filter[agencyId]"] == "EPA"
        assert params["filter[postedDate]"] == "2023-06-15"
        assert params["filter[documentType]"] == "Rule"
        assert params["sort"] == "date"
        assert params["page[size]"] == "10"
        assert params["page[number]"] == "2"


@pytest.mark.asyncio
async def test_search_documents_rejects_invalid_date(
    client: Client[Any], api_key: str
) -> None:
    """A malformed posted date filter fails validation before any HTTP call.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake Regulations.gov API key.

    """
    async with client, respx.mock:
        route = respx.get(f"{DOCUMENTS_URL}").mock(
            return_value=httpx.Response(200, json=_documents_response())
        )
        with pytest.raises(ToolError):
            await client.call_tool(
                "regulations_search_documents",
                {"query": "clean air", "filter_posted_date": "06/15/2023"},
            )

        assert route.call_count == 0


@pytest.mark.asyncio
async def test_search_documents_rejects_small_page_size(
    client: Client[Any], api_key: str
) -> None:
    """A page_size below the API minimum of 5 fails validation.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake Regulations.gov API key.

    """
    async with client, respx.mock:
        route = respx.get(f"{DOCUMENTS_URL}").mock(
            return_value=httpx.Response(200, json=_documents_response())
        )
        with pytest.raises(ToolError):
            await client.call_tool(
                "regulations_search_documents",
                {"query": "clean air", "page_size": 2},
            )

        assert route.call_count == 0


@pytest.mark.asyncio
async def test_get_document_with_attachments(client: Client[Any], api_key: str) -> None:
    """include_attachments adds the attachments include parameter.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake Regulations.gov API key.

    """
    async with client, respx.mock:
        route = respx.get(f"{DOCUMENTS_URL}/{DOCUMENT_ID}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": {
                        "id": DOCUMENT_ID,
                        "type": "documents",
                        "attributes": {"title": "Clean Air Act Implementation"},
                    }
                },
            )
        )
        result = await client.call_tool(
            "regulations_get_document",
            {"document_id": DOCUMENT_ID, "include_attachments": True},
        )

        assert result.content
        data = json.loads(result.content[0].text)
        assert data["data"]["id"] == DOCUMENT_ID

        params = route.calls.last.request.url.params
        assert params["include"] == "attachments"


@pytest.mark.asyncio
async def test_search_documents_http_error(client: Client[Any], api_key: str) -> None:
    """HTTP errors from the Regulations.gov API surface as ToolError.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake Regulations.gov API key.

    """
    async with client, respx.mock:
        respx.get(f"{DOCUMENTS_URL}").mock(
            return_value=httpx.Response(500, json={"errors": [{"detail": "boom"}]})
        )
        with pytest.raises(ToolError):
            await client.call_tool(
                "regulations_search_documents", {"query": "clean air"}
            )


@pytest.mark.asyncio
async def test_search_documents_connection_error(
    client: Client[Any], api_key: str
) -> None:
    """Connection failures from the Regulations.gov API surface as ToolError.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake Regulations.gov API key.

    """
    async with client, respx.mock:
        respx.get(f"{DOCUMENTS_URL}").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        with pytest.raises(ToolError):
            await client.call_tool(
                "regulations_search_documents", {"query": "clean air"}
            )
