"""Mocked-API tests for the CourtListener search tools.

All HTTP traffic is intercepted with respx, so these tests exercise the real
tool code without contacting the live CourtListener API.
"""

# Pytest assertions are the idiomatic test mechanism in this file.
# ruff: file-ignore[assert, unused-function-argument, import-private-name]

import json
from typing import Any

from fastmcp import Client
from fastmcp.exceptions import ToolError
import httpx
import pytest
import respx

from app.server import mcp
from app.tools.common import SEARCH_URL
from app.tools.search import _build_search_params

SEARCH_RESPONSE: dict[str, Any] = {
    "count": 1,
    "results": [
        {
            "caseName": "Miranda v. Arizona",
            "court": "scotus",
            "dateFiled": "2023-06-15",
        }
    ],
}

PEOPLE_RESPONSE: dict[str, Any] = {
    "count": 1,
    "results": [{"id": 1, "name_first": "John", "name_last": "Roberts"}],
}


@pytest.fixture
def client() -> Client[Any]:
    """Create a test client connected to the composed MCP server.

    Returns:
        Client: A FastMCP test client connected to the server.

    """
    return Client(mcp)


def _ok(payload: dict[str, Any]) -> httpx.Response:
    """Build a successful (200) search API response carrying ``payload``.

    Returns:
        httpx.Response: A 200 JSON response carrying the payload.

    """
    return httpx.Response(200, json=payload)


@pytest.mark.parametrize(
    ("tool_name", "arguments", "search_type"),
    [
        ("search_dockets", {"q": "patent", "court": "cafc", "limit": 5}, "d"),
        (
            "search_recap_documents",
            {"q": "motion", "court": "nysd", "limit": 5},
            "rd",
        ),
        ("search_people", {"q": "Roberts", "position_type": "jud", "limit": 5}, "p"),
    ],
)
@pytest.mark.asyncio
async def test_keyed_search_tools_send_correct_type(
    client: Client[Any],
    api_key: str,
    tool_name: str,
    arguments: dict[str, Any],
    search_type: str,
) -> None:
    """Keyed search tools forward their search type to the API."""
    async with client, respx.mock:
        route = respx.get(SEARCH_URL).mock(return_value=_ok(SEARCH_RESPONSE))
        result = await client.call_tool(tool_name, arguments)

        assert result.content
        params = route.calls.last.request.url.params
        assert params["type"] == search_type
        assert params["q"] == arguments["q"]


@pytest.mark.parametrize(
    ("tool_name", "arguments", "search_type"),
    [
        ("search_opinions", {"q": "miranda", "court": "scotus", "limit": 5}, "o"),
        ("search_dockets_with_documents", {"q": "copyright", "limit": 3}, "d"),
        ("search_audio", {"q": "argument", "court": "scotus", "limit": 5}, "oa"),
    ],
)
@pytest.mark.asyncio
async def test_public_search_tools_work_without_key(
    client: Client[Any],
    no_api_key: None,
    tool_name: str,
    arguments: dict[str, Any],
    search_type: str,
) -> None:
    """Public search tools work anonymously without an auth header."""
    async with client, respx.mock:
        route = respx.get(SEARCH_URL).mock(return_value=_ok(SEARCH_RESPONSE))
        result = await client.call_tool(tool_name, arguments)

        assert result.content
        params = route.calls.last.request.url.params
        assert params["type"] == search_type
        assert not route.calls.last.request.headers.get("Authorization")


@pytest.mark.asyncio
async def test_search_opinions_maps_limit_to_hit(
    client: Client[Any], api_key: str
) -> None:
    """The limit argument is sent as the V4 'hit' query parameter."""
    async with client, respx.mock:
        route = respx.get(SEARCH_URL).mock(return_value=_ok(SEARCH_RESPONSE))
        result = await client.call_tool(
            "search_opinions", {"q": "miranda", "court": "scotus", "limit": 5}
        )

        assert result.content
        data = json.loads(result.content[0].text)
        assert data["count"] == 1
        assert route.calls.last.request.url.params["hit"] == "5"


@pytest.mark.asyncio
async def test_search_people_with_key(client: Client[Any], api_key: str) -> None:
    """People searches use the 'p' search type and forward filters."""
    async with client, respx.mock:
        route = respx.get(SEARCH_URL).mock(return_value=_ok(PEOPLE_RESPONSE))
        result = await client.call_tool(
            "search_people", {"q": "Roberts", "position_type": "jud", "limit": 5}
        )

        assert result.content
        params = route.calls.last.request.url.params
        assert params["type"] == "p"
        assert params["position_type"] == "jud"


@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("search_dockets", {"q": "patent", "limit": 5}),
        ("search_recap_documents", {"q": "motion", "limit": 5}),
        ("search_people", {"q": "Roberts", "limit": 5}),
    ],
)
@pytest.mark.asyncio
async def test_key_required_search_tools_raise_without_key(
    client: Client[Any],
    no_api_key: None,
    tool_name: str,
    arguments: dict[str, Any],
) -> None:
    """Key-required search tools raise ToolError without an API key."""
    async with client, respx.mock:
        with pytest.raises(ToolError):
            await client.call_tool(tool_name, arguments)


@pytest.mark.asyncio
async def test_search_http_status_error(client: Client[Any], api_key: str) -> None:
    """HTTP errors from the search API surface as ToolError."""
    async with client, respx.mock:
        respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(500, json={"detail": "boom"})
        )
        with pytest.raises(ToolError):
            await client.call_tool("search_opinions", {"q": "x", "limit": 1})


@pytest.mark.asyncio
async def test_search_generic_error(client: Client[Any], api_key: str) -> None:
    """Unexpected search request errors are logged and re-raised."""
    async with client, respx.mock:
        respx.get(SEARCH_URL).mock(side_effect=httpx.ConnectError("connection failed"))
        with pytest.raises(ToolError):
            await client.call_tool("search_opinions", {"q": "x", "limit": 1})


def test_build_search_params_skips_empty_filters() -> None:
    """Empty filter values are omitted from the request parameters."""
    params = _build_search_params(
        "miranda", "score desc", "o", {"court": "scotus", "case_name": ""}, 5
    )
    assert params == {
        "q": "miranda",
        "order_by": "score desc",
        "type": "o",
        "court": "scotus",
        "hit": "5",
    }


def test_build_search_params_zero_limit() -> None:
    """A zero limit omits the 'hit' parameter."""
    params = _build_search_params("q", "score desc", "o", {}, 0)
    assert "hit" not in params
    assert params == {"q": "q", "order_by": "score desc", "type": "o"}
