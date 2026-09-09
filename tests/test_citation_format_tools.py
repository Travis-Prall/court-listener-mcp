"""Offline tests for the citation parsing and format verification tools.

These tools are pure citeurl operations (no network access), so they run
entirely offline.
"""

# Pytest assertions are the idiomatic test mechanism in this file.
# ruff: file-ignore[assert, unused-function-argument, import-private-name]

import json
from typing import Any

from fastmcp import Client
from fastmcp.exceptions import ToolError
import pytest

from app.server import mcp
from app.tools.citation import (
    _parse_with_fallback,
    _verify_with_basic_patterns,
    get_citator,
)


@pytest.fixture
def client() -> Client[Any]:
    """Create a test client connected to the composed MCP server.

    Returns:
        Client: A FastMCP test client connected to the server.

    """
    return Client(mcp)


def test_get_citator_is_singleton() -> None:
    """get_citator caches a single Citator with custom templates."""
    first = get_citator()
    second = get_citator()
    assert first is second
    assert len(first.templates) > 0


@pytest.mark.asyncio
async def test_parse_citation_with_citeurl_parser(
    client: Client[Any], api_key: str
) -> None:
    """parse_citation uses citeurl for standard citations."""
    async with client:
        result = await client.call_tool(
            "citation_parse_citation", {"citation": "410 U.S. 113"}
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is True
        assert data["parser_used"] == "citeurl"
        assert data["original"] == "410 U.S. 113"


@pytest.mark.asyncio
async def test_parse_citation_fallback_parser(
    client: Client[Any], api_key: str
) -> None:
    """parse_citation succeeds with the fallback regex when citeurl fails."""
    async with client:
        result = await client.call_tool(
            "citation_parse_citation", {"citation": "999 Fake Reporter 42 (2020)"}
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is True
        if data["parser_used"] == "fallback regex":
            assert data["volume"] == "999"
            assert data["page"] == "42"
            assert data["year"] == "2020"


@pytest.mark.asyncio
async def test_parse_citation_unparseable(client: Client[Any], api_key: str) -> None:
    """parse_citation reports failure for unparseable input."""
    async with client:
        result = await client.call_tool(
            "citation_parse_citation", {"citation": "completely unparseable words"}
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is False
        assert data["error"] == "Could not parse citation"


@pytest.mark.asyncio
async def test_validate_citation_valid(client: Client[Any], api_key: str) -> None:
    """validate_citation accepts a standard citation."""
    async with client:
        result = await client.call_tool(
            "citation_validate_citation", {"citation": "410 U.S. 113"}
        )
        data = json.loads(result.content[0].text)
        assert data["valid"] is True
        assert "parsed" in data


@pytest.mark.asyncio
async def test_validate_citation_invalid(client: Client[Any], api_key: str) -> None:
    """validate_citation rejects non-citations."""
    async with client:
        result = await client.call_tool(
            "citation_validate_citation",
            {"citation": "completely unparseable words"},
        )
        data = json.loads(result.content[0].text)
        assert data["valid"] is False


@pytest.mark.asyncio
async def test_verify_citation_format_rejects_empty(
    client: Client[Any], api_key: str
) -> None:
    """verify_citation_format rejects whitespace-only citations."""
    async with client:
        result = await client.call_tool(
            "citation_verify_citation_format", {"citation": "   "}
        )
        data = json.loads(result.content[0].text)
        assert data["valid"] is False
        assert "Citation is empty" in data["issues"]


@pytest.mark.asyncio
async def test_verify_citation_format_valid(client: Client[Any], api_key: str) -> None:
    """verify_citation_format recognizes a standard citation."""
    async with client:
        result = await client.call_tool(
            "citation_verify_citation_format", {"citation": " 410 U.S. 113 "}
        )
        data = json.loads(result.content[0].text)
        assert data["valid"] is True
        assert data["matching_mode"] in {"strict", "broad"}
        assert data["citation"] == " 410 U.S. 113 "


@pytest.mark.asyncio
async def test_verify_citation_format_unrecognized(
    client: Client[Any], api_key: str
) -> None:
    """verify_citation_format reports issues for unrecognized text."""
    async with client:
        result = await client.call_tool(
            "citation_verify_citation_format", {"citation": "the quick brown fox"}
        )
        data = json.loads(result.content[0].text)
        assert data["valid"] is False
        assert data["issues"]


@pytest.mark.asyncio
async def test_verify_citation_format_fallback(
    client: Client[Any], api_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """verify_citation_format falls back to regex when citeurl explodes."""

    def raiser(citation: str, citation_stripped: str) -> dict[str, Any]:
        raise RuntimeError("citeurl verification exploded")

    monkeypatch.setattr("app.tools.citation._verify_with_citator", raiser)
    async with client:
        result = await client.call_tool(
            "citation_verify_citation_format", {"citation": "410 U.S. 113"}
        )
        data = json.loads(result.content[0].text)
        assert data["valid"] is True
        assert data["template"] == "Basic regex fallback"
        assert data["format"] == "U.S. Reporter"


def test_verify_with_basic_patterns_matches() -> None:
    """The regex fallback validates U.S. reporter citations."""
    result = _verify_with_basic_patterns("410 U.S. 113", error=RuntimeError("x"))
    assert result["valid"] is True
    assert result["format"] == "U.S. Reporter"
    assert result["matching_mode"] == "fallback"


def test_verify_with_basic_patterns_no_match() -> None:
    """The regex fallback reports unmatched citations as invalid."""
    result = _verify_with_basic_patterns("nothing matches", error=RuntimeError("x"))
    assert result["valid"] is False
    assert any("citeurl parsing also failed" in issue for issue in result["issues"])


def test_parse_with_fallback_matches() -> None:
    """The fallback regex extracts volume, page, and year."""
    result = _parse_with_fallback("999 Fake Reporter 42 (2020)")
    assert result is not None
    assert result["volume"] == "999"
    assert result["page"] == "42"
    assert result["year"] == "2020"


def test_parse_with_fallback_rejects_non_citations() -> None:
    """The fallback regex returns None for non-citations."""
    assert _parse_with_fallback("no citation in here") is None


@pytest.mark.asyncio
async def test_parse_citation_with_citeurl_success(
    client: Client[Any], api_key: str
) -> None:
    """parse_citation_with_citeurl parses a statutory citation."""
    async with client:
        result = await client.call_tool(
            "citation_parse_citation_with_citeurl", {"citation": "42 USC \u00a7 1988"}
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is True
        assert "tokens" in data["parsed"]


@pytest.mark.asyncio
async def test_parse_citation_with_citeurl_unrecognized(
    client: Client[Any], api_key: str
) -> None:
    """parse_citation_with_citeurl reports unrecognized citations."""
    async with client:
        result = await client.call_tool(
            "citation_parse_citation_with_citeurl",
            {"citation": "completely unparseable words"},
        )
        data = json.loads(result.content[0].text)
        assert data["success"] is False
        assert "suggestion" in data


@pytest.mark.asyncio
async def test_parse_citation_with_citeurl_error(
    client: Client[Any], api_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """parse_citation_with_citeurl re-raises citeurl errors."""

    def raiser(*args: object, **kwargs: object) -> None:
        raise RuntimeError("citeurl exploded")

    monkeypatch.setattr("app.tools.citation.citeurl_cite", raiser)
    async with client:
        with pytest.raises(ToolError):
            await client.call_tool(
                "citation_parse_citation_with_citeurl", {"citation": "410 U.S. 113"}
            )


@pytest.mark.asyncio
async def test_extract_citations_from_text(client: Client[Any], api_key: str) -> None:
    """extract_citations_from_text finds citations in prose."""
    text = (
        "See Miranda v. Arizona, 410 U.S. 113 (1966), and the fee statute, "
        "42 USC \u00a7 1988(b)."
    )
    async with client:
        result = await client.call_tool(
            "citation_extract_citations_from_text", {"text": text}
        )
        data = json.loads(result.content[0].text)
        assert data["total_citations"] > 0
        assert data["text_length"] == len(text)


@pytest.mark.asyncio
async def test_extract_citations_from_text_without_matches(
    client: Client[Any], api_key: str
) -> None:
    """extract_citations_from_text returns zero citations for plain text."""
    async with client:
        result = await client.call_tool(
            "citation_extract_citations_from_text",
            {"text": "no citations here at all"},
        )
        data = json.loads(result.content[0].text)
        assert data["total_citations"] == 0
        assert data["citations"] == []
