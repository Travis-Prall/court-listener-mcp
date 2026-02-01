"""Test the enhanced citation tools."""

from typing import Any

from fastmcp import Client
import pytest


@pytest.mark.asyncio
async def test_parse_citation(client: Client[Any]) -> None:
    """Test the parse_citation_with_citeurl function."""
    async with client:
        result = await client.call_tool(
            "citation_parse_citation_with_citeurl", {"citation": "410 U.S. 113"}
        )

        assert not result.is_error
        response = result.data
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

        assert not result.is_error
        response = result.data
        assert response["total_citations"] > 0
        assert len(response["citations"]) > 0
