"""Live-API integration tests for the Regulations.gov tools.

These tests exercise the real api.regulations.gov endpoints with the
``REGULATIONS_API_KEY`` from the environment (loaded from ``.env``),
and are skipped automatically when no key is configured so the suite
stays runnable in CI or on machines without credentials. They use the
API-minimum page size of 5 to stay well within Regulations.gov rate
limits.

Run them explicitly with:

    uv run pytest tests/test_regulations_integration.py -v
"""

# Pytest assertions are the idiomatic test mechanism in this file.
# ruff: file-ignore[assert]

import json
import os
from typing import Any

from fastmcp import Client
import pytest

from app.server import mcp

REGULATIONS_API_KEY = os.getenv("REGULATIONS_API_KEY")

# Agent flow search query - a stable, high-volume federal rulemaking term
SEARCH_QUERY = "clean water act"
# API-minimum page size (Regulations.gov rejects page sizes below 5)
LIVE_PAGE_SIZE = 5

pytestmark = pytest.mark.skipif(
    not REGULATIONS_API_KEY,
    reason="REGULATIONS_API_KEY not set; live tests skipped",
)


@pytest.fixture
def client() -> Client[Any]:
    """Create a test client connected to the composed MCP server.

    Returns:
        Client: A FastMCP test client connected to the server instance.

    """
    return Client(mcp)


async def test_search_documents_live(client: Client[Any]) -> None:
    """A document search returns real rulemaking documents.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        result = await client.call_tool(
            "regulations_search_documents",
            {"query": SEARCH_QUERY, "page_size": LIVE_PAGE_SIZE},
        )
        assert result.content
        data = json.loads(result.content[0].text)
        assert data["data"], "Expected at least one document result"
        assert all("id" in item for item in data["data"])
        assert all("attributes" in item for item in data["data"])


async def test_get_document_from_search_live(client: Client[Any]) -> None:
    """A document found via search is retrievable by ID (agent flow).

    Searches for a document, then fetches the first result's full
    record - mirroring how an LLM agent chains the two tools.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        search_result = await client.call_tool(
            "regulations_search_documents",
            {"query": SEARCH_QUERY, "page_size": LIVE_PAGE_SIZE},
        )
        assert search_result.content
        search_data = json.loads(search_result.content[0].text)
        assert search_data["data"], "Expected search results"

        document_id = search_data["data"][0]["id"]
        detail_result = await client.call_tool(
            "regulations_get_document", {"document_id": document_id}
        )
        assert detail_result.content
        detail_data = json.loads(detail_result.content[0].text)
        assert detail_data["data"]["id"] == document_id


async def test_get_document_with_attachments_live(
    client: Client[Any],
) -> None:
    """Attachment includes are accepted by the live API.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        search_result = await client.call_tool(
            "regulations_search_documents",
            {"query": SEARCH_QUERY, "page_size": LIVE_PAGE_SIZE},
        )
        assert search_result.content
        search_data = json.loads(search_result.content[0].text)
        assert search_data["data"], "Expected search results"

        document_id = search_data["data"][0]["id"]
        detail_result = await client.call_tool(
            "regulations_get_document",
            {"document_id": document_id, "include_attachments": True},
        )
        assert detail_result.content
        detail_data = json.loads(detail_result.content[0].text)
        assert detail_data["data"]["id"] == document_id
