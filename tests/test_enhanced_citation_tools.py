"""Test the enhanced citation tools."""

import json
from typing import Any

from fastmcp import Client
import pytest

# Import the actual server instance after setup has run
from app.server import mcp


@pytest.fixture
def client() -> Client[Any]:
    """Create a test client connected to the real server.

    Returns:
        Client: A FastMCP test client connected to the server instance.

    """
    return Client(mcp)


@pytest.mark.asyncio
async def test_parse_citation(client: Client[Any]) -> None:
    """Test the parse_citation_with_citeurl function."""
    async with client:
        result = await client.call_tool(
            "citation_parse_citation_with_citeurl", {"citation": "410 U.S. 113"}
        )

        assert len(result) == 1
        response = json.loads(result[0].text)
        assert response["success"] is True
        assert "parsed" in response


@pytest.mark.asyncio
async def test_extract_citations(client: Client[Any]) -> None:
    """Test the extract_citations_from_text function."""
    async with client:
        text = """
        Federal law provides that courts should award prevailing civil rights
        plaintiffs reasonable attorneys fees, 42 USC § 1988(b), and, by discretion,
        expert fees, id. at (c). See Riverside v. Rivera, 477 U.S. 561 (1986).
        """

        result = await client.call_tool(
            "citation_extract_citations_from_text", {"text": text}
        )

        assert len(result) == 1
        response = json.loads(result[0].text)
        assert response["total_citations"] > 0
        assert len(response["citations"]) > 0
