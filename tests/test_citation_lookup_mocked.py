"""Mocked-API tests for the CourtListener citation lookup tools.

All HTTP traffic is intercepted with respx, so these tests exercise the real
tool code without contacting the live CourtListener API.
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
from app.tools.common import CITATION_LOOKUP_URL

CITATION_LOOKUP_RESPONSE: dict[str, Any] = {
    "results": [
        {
            "citation": "410 U.S. 113",
            "matched_opinions": [{"caseName": "Miranda v. Arizona", "id": 1}],
        }
    ]
}


@pytest.fixture
def client() -> Client[Any]:
    """Create a test client connected to the composed MCP server.

    Returns:
        Client: A FastMCP test client connected to the server.

    """
    return Client(mcp)


def _ok() -> httpx.Response:
    """Build a successful (200) citation-lookup API response.

    Returns:
        httpx.Response: A 200 JSON response with lookup results.

    """
    return httpx.Response(200, json=CITATION_LOOKUP_RESPONSE)


@pytest.mark.asyncio
async def test_lookup_citation_with_key(client: Client[Any], api_key: str) -> None:
    """Citation lookup POSTs form data with token auth."""
    async with client, respx.mock:
        route = respx.post(CITATION_LOOKUP_URL).mock(return_value=_ok())
        result = await client.call_tool(
            "citation_lookup_citation", {"citation": "410 U.S. 113"}
        )

        assert result.content
        data = json.loads(result.content[0].text)
        assert data["results"][0]["citation"] == "410 U.S. 113"
        request = route.calls.last.request
        assert "410+U.S.+113" in request.content.decode()
        assert request.headers["Authorization"] == f"Token {api_key}"


@pytest.mark.asyncio
async def test_lookup_citation_requires_key(
    client: Client[Any], no_api_key: None
) -> None:
    """Citation lookup requires an API key."""
    async with client, respx.mock:
        with pytest.raises(ToolError):
            await client.call_tool(
                "citation_lookup_citation", {"citation": "410 U.S. 113"}
            )


@pytest.mark.asyncio
async def test_get_citations_splits_on_semicolons(
    client: Client[Any], api_key: str
) -> None:
    """get_citations splits on semicolons and space-joins the batch."""
    async with client, respx.mock:
        route = respx.post(CITATION_LOOKUP_URL).mock(return_value=_ok())
        result = await client.call_tool(
            "citation_get_citations", {"citation": "410 U.S. 113; 123 F.3d 456"}
        )

        assert result.content
        body = route.calls.last.request.content.decode()
        assert "410+U.S.+113+123+F.3d+456" in body


@pytest.mark.asyncio
async def test_batch_lookup_citations_with_key(
    client: Client[Any], api_key: str
) -> None:
    """Batch citation lookup returns the API response."""
    async with client, respx.mock:
        respx.post(CITATION_LOOKUP_URL).mock(return_value=_ok())
        result = await client.call_tool(
            "citation_batch_lookup_citations",
            {"citations": ["410 U.S. 113", "123 F.3d 456"]},
        )

        assert result.content
        data = json.loads(result.content[0].text)
        assert data["results"]


@pytest.mark.asyncio
async def test_get_citation_details_with_key(client: Client[Any], api_key: str) -> None:
    """Citation details reuse the batch lookup endpoint."""
    async with client, respx.mock:
        respx.post(CITATION_LOOKUP_URL).mock(return_value=_ok())
        result = await client.call_tool(
            "citation_get_citation_details", {"citation_id": "410 U.S. 113"}
        )

        assert result.content


@pytest.mark.asyncio
async def test_batch_lookup_success(client: Client[Any], api_key: str) -> None:
    """batch_lookup sends a single-item batch successfully."""
    async with client, respx.mock:
        respx.post(CITATION_LOOKUP_URL).mock(return_value=_ok())
        result = await client.call_tool(
            "citation_batch_lookup", {"citations": ["410 U.S. 113"]}
        )

        assert result.content


@pytest.mark.asyncio
async def test_batch_lookup_rejects_empty_list(
    client: Client[Any], api_key: str
) -> None:
    """batch_lookup rejects empty citation lists."""
    async with client, respx.mock:
        with pytest.raises(ToolError):
            await client.call_tool("citation_batch_lookup", {"citations": []})


@pytest.mark.asyncio
async def test_batch_lookup_rejects_oversized_batches(
    client: Client[Any], api_key: str
) -> None:
    """batch_lookup rejects batches larger than the configured maximum."""
    async with client, respx.mock:
        with pytest.raises(ToolError):
            await client.call_tool(
                "citation_batch_lookup", {"citations": ["410 U.S. 113"] * 101}
            )


@pytest.mark.asyncio
async def test_citation_http_status_error(client: Client[Any], api_key: str) -> None:
    """HTTP errors from the citation API surface as ToolError."""
    async with client, respx.mock:
        respx.post(CITATION_LOOKUP_URL).mock(
            return_value=httpx.Response(500, json={"detail": "boom"})
        )
        with pytest.raises(ToolError):
            await client.call_tool(
                "citation_lookup_citation", {"citation": "410 U.S. 113"}
            )


@pytest.mark.asyncio
async def test_citation_generic_error(client: Client[Any], api_key: str) -> None:
    """Unexpected citation request errors are logged and re-raised."""
    async with client, respx.mock:
        respx.post(CITATION_LOOKUP_URL).mock(
            side_effect=httpx.ConnectError("connection failed")
        )
        with pytest.raises(ToolError):
            await client.call_tool(
                "citation_lookup_citation", {"citation": "410 U.S. 113"}
            )


@pytest.mark.asyncio
async def test_enhanced_lookup_combines_sources(
    client: Client[Any], api_key: str
) -> None:
    """Enhanced lookup merges citeurl and CourtListener data."""
    async with client, respx.mock:
        respx.post(CITATION_LOOKUP_URL).mock(return_value=_ok())
        result = await client.call_tool(
            "citation_enhanced_citation_lookup", {"citation": "410 U.S. 113"}
        )

        assert result.content
        data = json.loads(result.content[0].text)
        assert data["citeurl_analysis"]["success"] is True
        assert data["courtlistener_data"]["success"] is True
        assert data["combined_info"]["has_both_sources"] is True


@pytest.mark.asyncio
async def test_enhanced_lookup_without_courtlistener(
    client: Client[Any], api_key: str
) -> None:
    """Enhanced lookup skips CourtListener when asked to."""
    async with client, respx.mock:
        result = await client.call_tool(
            "citation_enhanced_citation_lookup",
            {"citation": "410 U.S. 113", "include_courtlistener": False},
        )

        assert result.content
        data = json.loads(result.content[0].text)
        assert data["courtlistener_data"] == {}
        assert data["combined_info"]["available_sources"] == ["citeurl"]


@pytest.mark.asyncio
async def test_enhanced_lookup_reports_missing_key(
    client: Client[Any], no_api_key: None
) -> None:
    """Enhanced lookup reports a missing key in its CourtListener data."""
    async with client, respx.mock:
        result = await client.call_tool(
            "citation_enhanced_citation_lookup", {"citation": "410 U.S. 113"}
        )

        assert result.content
        data = json.loads(result.content[0].text)
        assert data["courtlistener_data"]["success"] is False
        assert "COURT_LISTENER_API_KEY" in data["courtlistener_data"]["error"]


@pytest.mark.asyncio
async def test_get_citation_details_requires_key(
    client: Client[Any], no_api_key: None
) -> None:
    """Citation details without a key raise ToolError from the batch helper."""
    async with client, respx.mock:
        with pytest.raises(ToolError):
            await client.call_tool(
                "citation_get_citation_details", {"citation_id": "410 U.S. 113"}
            )
