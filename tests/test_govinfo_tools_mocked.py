"""Mocked-API tests for the GovInfo statute tools.

All HTTP traffic is intercepted with respx, so these tests exercise the
real GovInfo tool code without contacting the live api.govinfo.gov API.
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
from app.tools.govinfo import GOVINFO_BASE_URL, SEARCH_URL

# Expected values for the mocked GovInfo API responses
EXPECTED_TOTAL_COLLECTIONS = 4
EXPECTED_DEFAULT_PAGE_SIZE = 50
USC_TITLE_RESULT_COUNT = 3
PUBLIC_LAWS_RESULT_COUNT = 2
STATUTES_AT_LARGE_RESULT_COUNT = 5


@pytest.fixture
def client() -> Client[Any]:
    """Create a test client connected to the composed MCP server.

    Returns:
        Client: A FastMCP test client connected to the server instance.

    """
    return Client(mcp)


@pytest.mark.asyncio
async def test_list_statute_collections(client: Client[Any]) -> None:
    """The collection listing tool returns all statute collections.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        result = await client.call_tool("statutes_list_statute_collections", {})

        assert result.content
        data = json.loads(result.content[0].text)
        assert data["total_collections"] == EXPECTED_TOTAL_COLLECTIONS
        codes = [coll["code"] for coll in data["statute_collections"]]
        assert "USCODE" in codes
        assert "STATUTE" in codes
        assert "PLAW" in codes
        assert "COMPS" in codes
        assert all("description" in coll for coll in data["statute_collections"])


@pytest.mark.parametrize(
    ("tool_name", "tool_args"),
    [
        ("statutes_search_statutes", {"query": "test"}),
        ("statutes_get_uscode_title", {"title_number": "42"}),
        ("statutes_get_public_laws_by_congress", {"congress": 117}),
        ("statutes_get_statutes_at_large", {"volume": "135"}),
        ("statutes_get_statute_content", {"package_id": "PLAW-1"}),
    ],
)
@pytest.mark.asyncio
async def test_govinfo_tools_require_api_key(
    client: Client[Any], no_api_key: None, tool_name: str, tool_args: dict[str, Any]
) -> None:
    """Every networked GovInfo tool requires an API key.

    Args:
        client: FastMCP test client fixture.
        no_api_key: Fixture forcing the GovInfo API key to None.
        tool_name: Prefixed MCP tool name to call.
        tool_args: Valid minimal arguments for the tool.

    """
    async with client:
        with pytest.raises(ToolError):
            await client.call_tool(tool_name, tool_args)


@pytest.mark.asyncio
async def test_search_statutes_with_api_key(client: Client[Any], api_key: str) -> None:
    """A statute search posts the query and filters to statute collections.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake GovInfo API key.

    """
    async with client, respx.mock:
        route = respx.post(f"{SEARCH_URL}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "count": 2,
                    "results": [
                        {
                            "packageId": "USCODE-2022-title42",
                            "collectionCode": "USCODE",
                        },
                        {"packageId": "FR-2024-01-01", "collectionCode": "FR"},
                    ],
                },
            )
        )
        result = await client.call_tool(
            "statutes_search_statutes", {"query": "civil rights"}
        )

        assert result.content
        data = json.loads(result.content[0].text)
        # Non-statute results (e.g., Federal Register) are filtered out
        assert data["count"] == 1
        assert data["results"][0]["collectionCode"] == "USCODE"

        request = route.calls.last.request
        assert request.headers["X-Api-Key"] == api_key
        body = json.loads(request.content)
        assert "civil rights" in body["query"]
        assert "collection:USCODE" in body["query"]
        assert body["pageSize"] == EXPECTED_DEFAULT_PAGE_SIZE


@pytest.mark.asyncio
async def test_search_statutes_specific_collection(
    client: Client[Any], api_key: str
) -> None:
    """A collection-scoped search builds the collection query without filtering.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake GovInfo API key.

    """
    async with client, respx.mock:
        route = respx.post(f"{SEARCH_URL}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "count": 1,
                    "results": [
                        {"packageId": "USCODE-2022-title42", "collectionCode": "USCODE"}
                    ],
                },
            )
        )
        result = await client.call_tool(
            "statutes_search_statutes",
            {"query": "social security", "collection": "USCODE", "congress": 118},
        )

        assert result.content
        data = json.loads(result.content[0].text)
        assert data["count"] == 1

        body = json.loads(route.calls.last.request.content)
        assert (
            body["query"] == "collection:USCODE AND (social security) AND congress:118"
        )


@pytest.mark.asyncio
async def test_search_statutes_invalid_collection(
    client: Client[Any], api_key: str
) -> None:
    """An unknown collection code is rejected before any API call.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake GovInfo API key.

    """
    async with client, respx.mock:
        route = respx.post(f"{SEARCH_URL}").mock(
            return_value=httpx.Response(200, json={})
        )
        with pytest.raises(ToolError):
            await client.call_tool(
                "statutes_search_statutes",
                {"query": "test", "collection": "NOT_A_COLLECTION"},
            )
        assert not route.called


@pytest.mark.asyncio
async def test_get_uscode_title(client: Client[Any], api_key: str) -> None:
    """The USC title tool builds a field-operator query for the title.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake GovInfo API key.

    """
    async with client, respx.mock:
        route = respx.post(f"{SEARCH_URL}").mock(
            return_value=httpx.Response(
                200,
                json={"count": 3, "results": [{"packageId": "USCODE-2022-title42"}]},
            )
        )
        result = await client.call_tool(
            "statutes_get_uscode_title",
            {"title_number": "42", "chapter": "7", "section": "540b"},
        )

        assert result.content
        data = json.loads(result.content[0].text)
        assert data["count"] == USC_TITLE_RESULT_COUNT

        body = json.loads(route.calls.last.request.content)
        assert body["query"] == "collection:USCODE AND title:42 AND 7 AND 540b"
        assert body["sorts"] == [{"field": "title", "sortOrder": "ASC"}]


@pytest.mark.asyncio
async def test_get_public_laws_by_congress(client: Client[Any], api_key: str) -> None:
    """The public laws tool scopes the query to the PLAW collection.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake GovInfo API key.

    """
    async with client, respx.mock:
        route = respx.post(f"{SEARCH_URL}").mock(
            return_value=httpx.Response(
                200, json={"count": 2, "results": [{"packageId": "PLAW-118publ45"}]}
            )
        )
        result = await client.call_tool(
            "statutes_get_public_laws_by_congress",
            {"congress": 118, "law_type": "public", "law_number": "118publ58"},
        )

        assert result.content
        data = json.loads(result.content[0].text)
        assert data["count"] == PUBLIC_LAWS_RESULT_COUNT

        body = json.loads(route.calls.last.request.content)
        assert body["query"] == (
            "collection:PLAW AND congress:118 "
            "AND (docClass:public OR title:public) AND 118publ58"
        )
        assert body["sorts"] == [{"field": "publishdate", "sortOrder": "DESC"}]


@pytest.mark.asyncio
async def test_get_public_laws_invalid_law_type(
    client: Client[Any], api_key: str
) -> None:
    """An invalid law type is rejected before any API call.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake GovInfo API key.

    """
    async with client, respx.mock:
        route = respx.post(f"{SEARCH_URL}").mock(
            return_value=httpx.Response(200, json={})
        )
        with pytest.raises(ToolError):
            await client.call_tool(
                "statutes_get_public_laws_by_congress",
                {"congress": 118, "law_type": "administrative"},
            )
        assert not route.called


@pytest.mark.asyncio
async def test_get_statutes_at_large(client: Client[Any], api_key: str) -> None:
    """The Statutes at Large tool scopes the query to the STATUTE collection.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake GovInfo API key.

    """
    async with client, respx.mock:
        route = respx.post(f"{SEARCH_URL}").mock(
            return_value=httpx.Response(
                200, json={"count": 5, "results": [{"packageId": "STATUTE-117"}]}
            )
        )
        result = await client.call_tool(
            "statutes_get_statutes_at_large",
            {"volume": "135", "congress": 117},
        )

        assert result.content
        data = json.loads(result.content[0].text)
        assert data["count"] == STATUTES_AT_LARGE_RESULT_COUNT

        body = json.loads(route.calls.last.request.content)
        assert body["query"] == "collection:STATUTE AND 135 AND congress:117"


@pytest.mark.asyncio
async def test_get_statute_content_summary(client: Client[Any], api_key: str) -> None:
    """The content tool fetches a package summary by default.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake GovInfo API key.

    """
    async with client, respx.mock:
        route = respx.get(f"{GOVINFO_BASE_URL}/packages/PLAW-117publ58/summary").mock(
            return_value=httpx.Response(
                200, json={"packageId": "PLAW-117publ58", "title": "Public Law 117-58"}
            )
        )
        result = await client.call_tool(
            "statutes_get_statute_content",
            {"package_id": "PLAW-117publ58"},
        )

        assert result.content
        data = json.loads(result.content[0].text)
        assert data["packageId"] == "PLAW-117publ58"
        assert route.called
        assert route.calls.last.request.headers["X-Api-Key"] == api_key


@pytest.mark.asyncio
async def test_get_statute_content_granule(client: Client[Any], api_key: str) -> None:
    """A granule ID targets the granule summary endpoint.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake GovInfo API key.

    """
    async with client, respx.mock:
        route = respx.get(
            f"{GOVINFO_BASE_URL}/packages/PLAW-117publ58/granules/BILLS-117s1-is/summary"
        ).mock(return_value=httpx.Response(200, json={"granuleId": "BILLS-117s1-is"}))
        result = await client.call_tool(
            "statutes_get_statute_content",
            {"package_id": "PLAW-117publ58", "granule_id": "BILLS-117s1-is"},
        )

        assert result.content
        data = json.loads(result.content[0].text)
        assert data["granuleId"] == "BILLS-117s1-is"
        assert route.called


@pytest.mark.asyncio
async def test_get_statute_content_download_link(
    client: Client[Any], api_key: str
) -> None:
    """Content requests resolve the matching download URL.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake GovInfo API key.

    """
    xml_url = f"{GOVINFO_BASE_URL}/content/pkg/PLAW-117publ58/xml"
    async with client, respx.mock:
        respx.get(f"{GOVINFO_BASE_URL}/packages/PLAW-117publ58/summary").mock(
            return_value=httpx.Response(
                200,
                json={
                    "packageId": "PLAW-117publ58",
                    "download": {
                        "xmlLink": xml_url,
                        "pdfLink": "https://example.gov/x.pdf",
                    },
                },
            )
        )
        result = await client.call_tool(
            "statutes_get_statute_content",
            {"package_id": "PLAW-117publ58", "content_type": "xml"},
        )

        assert result.content
        data = json.loads(result.content[0].text)
        assert data["requested_content_url"] == xml_url
        assert data["content_type"] == "xml"


@pytest.mark.asyncio
async def test_get_statute_content_missing_link(
    client: Client[Any], api_key: str
) -> None:
    """When no download link exists, no content URL is added.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake GovInfo API key.

    """
    async with client, respx.mock:
        respx.get(f"{GOVINFO_BASE_URL}/packages/PLAW-1/summary").mock(
            return_value=httpx.Response(200, json={"packageId": "PLAW-1"})
        )
        result = await client.call_tool(
            "statutes_get_statute_content",
            {"package_id": "PLAW-1", "content_type": "pdf"},
        )

        assert result.content
        data = json.loads(result.content[0].text)
        assert "requested_content_url" not in data


@pytest.mark.asyncio
async def test_get_statute_content_invalid_type(
    client: Client[Any], api_key: str
) -> None:
    """An invalid content type is rejected before any API call.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake GovInfo API key.

    """
    async with client, respx.mock:
        route = respx.get(f"{GOVINFO_BASE_URL}/packages/PLAW-1/summary").mock(
            return_value=httpx.Response(200, json={})
        )
        with pytest.raises(ToolError):
            await client.call_tool(
                "statutes_get_statute_content",
                {"package_id": "PLAW-1", "content_type": "html"},
            )
        assert not route.called


@pytest.mark.asyncio
async def test_govinfo_search_http_status_error(
    client: Client[Any], api_key: str
) -> None:
    """HTTP errors from the search API surface to the client as ToolError.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake GovInfo API key.

    """
    async with client, respx.mock:
        respx.post(f"{SEARCH_URL}").mock(
            return_value=httpx.Response(500, json={"error": "boom"})
        )
        with pytest.raises(ToolError):
            await client.call_tool("statutes_search_statutes", {"query": "test"})


@pytest.mark.asyncio
async def test_govinfo_search_connection_error(
    client: Client[Any], api_key: str
) -> None:
    """Connection failures from the search API surface as ToolError.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake GovInfo API key.

    """
    async with client, respx.mock:
        respx.post(f"{SEARCH_URL}").mock(side_effect=httpx.ConnectError("refused"))
        with pytest.raises(ToolError):
            await client.call_tool("statutes_search_statutes", {"query": "test"})


@pytest.mark.asyncio
async def test_govinfo_content_connection_error(
    client: Client[Any], api_key: str
) -> None:
    """Connection failures from the content API surface as ToolError.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake GovInfo API key.

    """
    async with client, respx.mock:
        respx.get(f"{GOVINFO_BASE_URL}/packages/PLAW-1/summary").mock(
            side_effect=httpx.ConnectError("refused")
        )
        with pytest.raises(ToolError):
            await client.call_tool(
                "statutes_get_statute_content", {"package_id": "PLAW-1"}
            )


@pytest.mark.asyncio
async def test_search_statutes_all_filters(client: Client[Any], api_key: str) -> None:
    """Every optional filter is appended to the search query in order.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake GovInfo API key.

    """
    async with client, respx.mock:
        route = respx.post(f"{SEARCH_URL}").mock(
            return_value=httpx.Response(200, json={"count": 0, "results": []})
        )
        await client.call_tool(
            "statutes_search_statutes",
            {
                "query": "maritime law",
                "collection": "USCODE",
                "congress": 118,
                "title_number": "46",
                "section": "30101",
                "start_date": "2020-01-01",
                "end_date": "2024-12-31",
            },
        )

        body = json.loads(route.calls.last.request.content)
        assert body["query"] == (
            "collection:USCODE AND (maritime law) AND congress:118"
            " AND title:46 AND 30101"
            " AND publishdate:range(2020-01-01,2024-12-31)"
        )


@pytest.mark.asyncio
async def test_get_uscode_title_edition_filter(
    client: Client[Any], api_key: str
) -> None:
    """An edition date appends a publishdate filter to the query.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake GovInfo API key.

    """
    async with client, respx.mock:
        route = respx.post(f"{SEARCH_URL}").mock(
            return_value=httpx.Response(200, json={"count": 0, "results": []})
        )
        await client.call_tool(
            "statutes_get_uscode_title",
            {"title_number": "46", "edition": "2023-08-11"},
        )

        body = json.loads(route.calls.last.request.content)
        assert (
            body["query"] == "collection:USCODE AND title:46 AND publishdate:2023-08-11"
        )


@pytest.mark.asyncio
async def test_get_public_laws_private_law_with_dates(
    client: Client[Any], api_key: str
) -> None:
    """Private law type, law number, and date filters compose the query.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake GovInfo API key.

    """
    async with client, respx.mock:
        route = respx.post(f"{SEARCH_URL}").mock(
            return_value=httpx.Response(200, json={"count": 0, "results": []})
        )
        await client.call_tool(
            "statutes_get_public_laws_by_congress",
            {
                "congress": 118,
                "law_type": "private",
                "law_number": "118priv14",
                "start_date": "2023-01-01",
                "end_date": "2024-06-30",
            },
        )

        body = json.loads(route.calls.last.request.content)
        assert body["query"] == (
            "collection:PLAW AND congress:118"
            " AND (docClass:private OR title:private) AND 118priv14"
            " AND publishdate:range(2023-01-01,2024-06-30)"
        )


@pytest.mark.asyncio
async def test_get_statutes_at_large_page_filter(
    client: Client[Any], api_key: str
) -> None:
    """A page filter is appended to the volume query.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake GovInfo API key.

    """
    async with client, respx.mock:
        route = respx.post(f"{SEARCH_URL}").mock(
            return_value=httpx.Response(200, json={"count": 0, "results": []})
        )
        await client.call_tool(
            "statutes_get_statutes_at_large",
            {"volume": "135", "page": "281", "congress": 117},
        )

        body = json.loads(route.calls.last.request.content)
        assert body["query"] == "collection:STATUTE AND 135 AND 281 AND congress:117"


@pytest.mark.asyncio
async def test_govinfo_content_http_status_error(
    client: Client[Any], api_key: str
) -> None:
    """HTTP errors from the content API surface to the client as ToolError.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake GovInfo API key.

    """
    async with client, respx.mock:
        respx.get(f"{GOVINFO_BASE_URL}/packages/PLAW-404/summary").mock(
            return_value=httpx.Response(404, json={"error": "Not found"})
        )
        with pytest.raises(ToolError):
            await client.call_tool(
                "statutes_get_statute_content", {"package_id": "PLAW-404"}
            )
