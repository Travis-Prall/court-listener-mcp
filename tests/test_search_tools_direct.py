#!/usr/bin/env python3
"""Test script to validate CourtListener MCP server tools."""

# Pytest assertions are the idiomatic test mechanism in this file.
# ruff: file-ignore[assert, unused-function-argument]

import json
import os
from typing import Any

from dotenv import load_dotenv
from fastmcp import Client
import httpx
from loguru import logger
import pytest
import respx

from app.tools.common import SEARCH_URL, auth_headers
from app.tools.search import search_server

# Load environment variables
load_dotenv()

COURT_LISTENER_API_KEY = os.getenv("COURT_LISTENER_API_KEY")
PUBLIC_SEARCH_URL = "https://www.courtlistener.com/api/rest/v4/search/"
OK_STATUS = 200
RATE_LIMITED_STATUS = 429

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


# Test that the CourtListener API answers authenticated requests
@pytest.mark.asyncio
async def test_authenticated_api_access() -> None:
    """Test that the CourtListener API answers authenticated requests.

    Anonymous search returns HTTP 401, so the token from
    ``COURT_LISTENER_API_KEY`` is sent; the test is skipped when no key is
    configured.
    """
    if not COURT_LISTENER_API_KEY:
        pytest.skip("COURT_LISTENER_API_KEY not set; live API access test skipped")

    logger.info("Testing authenticated API access...")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            PUBLIC_SEARCH_URL,
            params={"q": "test", "type": "o", "hit": 1},
            headers=auth_headers(),
            timeout=10.0,
        )

    logger.info(f"API returned status {response.status_code}")

    if response.status_code == RATE_LIMITED_STATUS:
        pytest.skip("CourtListener rate limit hit (429); re-run to check access")

    assert response.status_code == OK_STATUS, (
        f"Expected HTTP {OK_STATUS} from the authenticated search API, "
        f"got {response.status_code}"
    )


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
