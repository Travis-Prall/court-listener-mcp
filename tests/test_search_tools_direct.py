#!/usr/bin/env python3
"""Test script to validate CourtListener MCP server tools."""

# Pytest assertions are the idiomatic test mechanism in this file.
# ruff: file-ignore[assert, unused-function-argument]

import json
from typing import Any

from dotenv import load_dotenv
from fastmcp import Client
import httpx
from loguru import logger
import pytest
import respx

from app.tools.common import SEARCH_URL
from app.tools.search import search_server

# Load environment variables
load_dotenv()

PUBLIC_SEARCH_URL = "https://www.courtlistener.com/api/rest/v4/search/"
UNAUTHORIZED_STATUS = 401
OK_STATUS = 200

MOCK_SEARCH_RESPONSE = {
    "count": 1,
    "results": [
        {
            "caseName": "Miranda v. Arizona",
            "court": "scotus",
            "dateFiled": "2023-06-15",
        }
    ],
}


@pytest.fixture
def search_client() -> Client[Any]:
    """Create a test client connected to the search server.

    Returns:
        Client: A FastMCP test client connected to the search server.

    """
    return Client(search_server)


# Test if CourtListener API allows public access
@pytest.mark.asyncio
async def test_public_api_access() -> None:
    """Test if CourtListener API allows public access."""
    logger.info("Testing public API access...")

    async with httpx.AsyncClient() as client:
        # Try a simple search without API key
        response = await client.get(
            PUBLIC_SEARCH_URL,
            params={"q": "test", "type": "o", "hit": 1},
            timeout=10.0,
        )

    if response.status_code == UNAUTHORIZED_STATUS:
        pytest.fail("API requires authentication - need valid COURT_LISTENER_API_KEY")
    if response.status_code == OK_STATUS:
        logger.info("Public API access available")
    else:
        logger.warning(f"API returned status {response.status_code}")
        pytest.fail(f"API returned status {response.status_code}")


def _ok(payload: dict[str, Any]) -> httpx.Response:
    """Build a successful (200) search API response carrying ``payload``.

    Returns:
        httpx.Response: A 200 JSON response carrying the payload.

    """
    return httpx.Response(200, json=payload)


@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        ("opinions", {"q": "Miranda", "court": "scotus", "limit": 5}),
        ("dockets", {"q": "patent", "court": "cafc", "limit": 5}),
        ("dockets_with_documents", {"q": "copyright", "limit": 3}),
        ("recap_documents", {"q": "motion", "court": "nysd", "limit": 5}),
        ("audio", {"q": "argument", "court": "scotus", "limit": 5}),
        ("people", {"q": "Roberts", "position_type": "jud", "limit": 5}),
    ],
)
@pytest.mark.asyncio
async def test_search_tools_return_mocked_results(
    search_client: Client[Any],
    api_key: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> None:
    """Search tools return the mocked API payload without live traffic.

    Parameters
    ----------
    search_client : Client
        The search-server client fixture.

    api_key : str
        Fake API key fixture used by the tool modules.

    tool_name : str
        The unprefixed search tool name.

    arguments : dict
        Tool arguments.

    """
    async with search_client, respx.mock:
        respx.get(SEARCH_URL).mock(return_value=_ok(MOCK_SEARCH_RESPONSE))
        result = await search_client.call_tool(tool_name, arguments)

        assert result.content
        data = json.loads(result.content[0].text)
        assert data["count"] == 1
        assert data["results"][0]["caseName"] == "Miranda v. Arizona"
        logger.success(f"{tool_name} PASSED")
