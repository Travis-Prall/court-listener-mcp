"""Live-API integration tests for the GovInfo statute tools.

These tests exercise the real api.govinfo.gov endpoints with the
``GOVINFO_API_KEY`` from the environment (loaded from ``.env``), and are
skipped automatically when no key is configured so the suite stays
runnable in CI or on machines without credentials. They use small page
sizes to stay well within GovInfo API rate limits.

Run them explicitly with:

    uv run pytest tests/test_govinfo_integration.py -v
"""

# Pytest assertions are the idiomatic test mechanism in this file.
# ruff: file-ignore[assert]

import json
import os
from typing import Any

from fastmcp import Client
import pytest

from app.server import mcp
from app.tools.govinfo import STATUTE_COLLECTIONS

GOVINFO_API_KEY = os.getenv("GOVINFO_API_KEY")

# Expected total number of statute collections returned by the tool
EXPECTED_TOTAL_COLLECTIONS = 4

pytestmark = pytest.mark.skipif(
    not GOVINFO_API_KEY,
    reason="GOVINFO_API_KEY not set; live GovInfo integration tests skipped",
)


@pytest.fixture
def client() -> Client[Any]:
    """Create a test client connected to the composed MCP server.

    Returns:
        Client: A FastMCP test client connected to the server instance.

    """
    return Client(mcp)


async def test_list_statute_collections_live(client: Client[Any]) -> None:
    """The collection listing tool returns all four statute collections.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        result = await client.call_tool("statutes_list_statute_collections", {})
        assert result.content
        data = json.loads(result.content[0].text)
        assert data["total_collections"] == EXPECTED_TOTAL_COLLECTIONS
        codes = [coll["code"] for coll in data["statute_collections"]]
        assert set(codes) == set(STATUTE_COLLECTIONS.keys())


async def test_search_statutes_live(client: Client[Any]) -> None:
    """A live statute search returns real statute-collection results.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        result = await client.call_tool(
            "statutes_search_statutes",
            {"query": "civil rights", "collection": "STATUTE", "page_size": 5},
        )
        assert result.content
        data = json.loads(result.content[0].text)
        assert data["count"] > 0
        assert isinstance(data["results"], list)
        for hit in data["results"]:
            assert hit["collectionCode"] in STATUTE_COLLECTIONS


async def test_search_statutes_uscode_title_filter_live(
    client: Client[Any],
) -> None:
    """A live USCODE search with the title filter returns title results.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        result = await client.call_tool(
            "statutes_search_statutes",
            {
                "query": "social security benefits",
                "collection": "USCODE",
                "title_number": "42",
                "page_size": 5,
            },
        )
        assert result.content
        data = json.loads(result.content[0].text)
        assert data["count"] > 0
        for hit in data["results"]:
            assert hit["collectionCode"] == "USCODE"


async def test_search_statutes_plaw_filters_live(client: Client[Any]) -> None:
    """A live PLAW search with congress and date-range filters works.

    The date range uses the publishdate:range(start,end) syntax that the
    live GovInfo API accepts.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        result = await client.call_tool(
            "statutes_search_statutes",
            {
                "query": "act",
                "collection": "PLAW",
                "congress": 117,
                "start_date": "2021-01-01",
                "end_date": "2021-12-31",
                "page_size": 5,
            },
        )
        assert result.content
        data = json.loads(result.content[0].text)
        assert data["count"] > 0
        for hit in data["results"]:
            assert hit["collectionCode"] == "PLAW"


async def test_get_uscode_title_live(client: Client[Any]) -> None:
    """A live USC title search returns sections from that title.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        result = await client.call_tool(
            "statutes_get_uscode_title",
            {"title_number": "42", "chapter": "7", "page_size": 5},
        )
        assert result.content
        data = json.loads(result.content[0].text)
        assert data["count"] > 0
        assert data["results"]
        for hit in data["results"]:
            assert hit["collectionCode"] == "USCODE"
            assert hit["packageId"].startswith("USCODE")


async def test_get_public_laws_by_congress_live(client: Client[Any]) -> None:
    """A live public-laws search returns laws from the requested Congress.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        result = await client.call_tool(
            "statutes_get_public_laws_by_congress",
            {"congress": 118, "law_type": "public", "page_size": 5},
        )
        assert result.content
        data = json.loads(result.content[0].text)
        assert data["count"] > 0
        for hit in data["results"]:
            assert hit["collectionCode"] == "PLAW"


async def test_get_statutes_at_large_live(client: Client[Any]) -> None:
    """A live Statutes at Large volume search returns results.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        result = await client.call_tool(
            "statutes_get_statutes_at_large",
            {"volume": "135", "page_size": 5},
        )
        assert result.content
        data = json.loads(result.content[0].text)
        assert data["count"] > 0
        for hit in data["results"]:
            assert hit["collectionCode"] == "STATUTE"


async def test_get_statute_content_summary_live(client: Client[Any]) -> None:
    """A live package summary returns real GovInfo package metadata.

    PLAW-117publ58 is Public Law 117-58 (the Infrastructure Investment and
    Jobs Act), a stable well-known package.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        result = await client.call_tool(
            "statutes_get_statute_content",
            {"package_id": "PLAW-117publ58"},
        )
        assert result.content
        data = json.loads(result.content[0].text)
        assert data["packageId"] == "PLAW-117publ58"


async def test_get_statute_content_download_link_live(
    client: Client[Any],
) -> None:
    """A live content request resolves the text download URL when present.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        result = await client.call_tool(
            "statutes_get_statute_content",
            {"package_id": "USCODE-2024-title42"},
        )
        assert result.content
        summary = json.loads(result.content[0].text)
        txt_link = summary.get("download", {}).get("txtLink")
        if not txt_link:
            pytest.skip("No txtLink available for USCODE-2024-title42")

        link_result = await client.call_tool(
            "statutes_get_statute_content",
            {"package_id": "USCODE-2024-title42", "content_type": "text"},
        )
        assert link_result.content
        link_data = json.loads(link_result.content[0].text)
        assert link_data["requested_content_url"] == txt_link
        assert link_data["content_type"] == "text"


async def test_statute_search_to_content_flow_live(client: Client[Any]) -> None:
    """The realistic flow: search, take a package ID, fetch its summary.

    This verifies tools compose correctly against live data, mirroring how
    an LLM agent would chain statute tools.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        search = await client.call_tool(
            "statutes_get_uscode_title",
            {"title_number": "42", "section": "1206", "page_size": 3},
        )
        assert search.content
        search_data = json.loads(search.content[0].text)
        assert search_data["count"] > 0

        package_id = search_data["results"][0]["packageId"]
        content = await client.call_tool(
            "statutes_get_statute_content",
            {"package_id": package_id},
        )
        assert content.content
        content_data = json.loads(content.content[0].text)
        assert content_data["packageId"] == package_id
