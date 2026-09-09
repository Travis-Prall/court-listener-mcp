"""Offline unit tests for the citation lookup helper functions."""

# Pytest assertions are the idiomatic test mechanism in this file.
# ruff: file-ignore[assert, unused-function-argument, unused-lambda-argument, import-private-name]

from types import SimpleNamespace
from typing import Any

from fastmcp import Client
from fastmcp.exceptions import ToolError
import httpx
import pytest
import respx

from app.server import mcp
from app.tools.citation import (
    _citeurl_citation_analysis,
    _combined_citation_info,
    _courtlistener_citation_data,
    _lookup_citations_batch,
    _parse_with_citator,
    _verify_with_citator,
)
from app.tools.common import CITATION_LOOKUP_URL

COURT_LISTENER_DATA: list[int] = [1, 2]


@pytest.fixture
def client() -> Client[Any]:
    """Create a test client connected to the composed MCP server.

    Returns:
        Client: A FastMCP test client connected to the server.

    """
    return Client(mcp)


@pytest.mark.asyncio
async def test_courtlistener_citation_data_success(api_key: str) -> None:
    """The helper returns the parsed API payload on success."""
    with respx.mock:
        respx.post(CITATION_LOOKUP_URL).mock(
            return_value=httpx.Response(200, json={"results": []})
        )
        result = await _courtlistener_citation_data("410 U.S. 113")
        assert result["success"] is True


@pytest.mark.asyncio
async def test_courtlistener_citation_data_http_error(api_key: str) -> None:
    """The helper reports non-200 responses as failures."""
    with respx.mock:
        respx.post(CITATION_LOOKUP_URL).mock(
            return_value=httpx.Response(500, text="boom")
        )
        result = await _courtlistener_citation_data("410 U.S. 113")
        assert result["success"] is False
        assert "HTTP 500" in result["error"]


@pytest.mark.asyncio
async def test_courtlistener_citation_data_connect_error(api_key: str) -> None:
    """The helper reports request errors as failures."""
    with respx.mock:
        respx.post(CITATION_LOOKUP_URL).mock(side_effect=httpx.ConnectError("boom"))
        result = await _courtlistener_citation_data("410 U.S. 113")
        assert result["success"] is False
        assert "CourtListener API error" in result["error"]


@pytest.mark.asyncio
async def test_courtlistener_citation_data_requires_key(no_api_key: None) -> None:
    """The helper reports a missing API key as a failure."""
    result = await _courtlistener_citation_data("410 U.S. 113")
    assert result["success"] is False
    assert "COURT_LISTENER_API_KEY" in result["error"]


def test_combined_citation_info_has_both_sources() -> None:
    """Successful analyses from both sources produce a combined summary."""
    result = _combined_citation_info({
        "citeurl_analysis": {
            "success": True,
            "URL": "https://cite.example/410-us-113",
            "canonical_name": "Miranda v. Arizona",
            "tokens": {"volume": "410"},
        },
        "courtlistener_data": {"success": True, "data": COURT_LISTENER_DATA},
    })
    assert result["has_both_sources"] is True
    assert result["courtlistener_matches"] == len(COURT_LISTENER_DATA)
    assert result["canonical_citation"] == "Miranda v. Arizona"


def test_combined_citation_info_partial_sources() -> None:
    """Partial analyses list only the available sources."""
    citeurl_only = _combined_citation_info({
        "citeurl_analysis": {"success": True},
        "courtlistener_data": {},
    })
    assert citeurl_only == {
        "has_both_sources": False,
        "available_sources": ["citeurl"],
    }
    neither = _combined_citation_info({
        "citeurl_analysis": {},
        "courtlistener_data": {},
    })
    assert neither["available_sources"] == []


def test_combined_citation_info_non_dict_entries() -> None:
    """Non-dict analysis entries are ignored safely."""
    result = _combined_citation_info({
        "citeurl_analysis": "not-a-dict",
        "courtlistener_data": None,
    })
    assert result["has_both_sources"] is False
    assert result["available_sources"] == []


def test_citeurl_citation_analysis_success() -> None:
    """The citeurl analysis reports success for recognized citations."""
    result = _citeurl_citation_analysis("410 U.S. 113")
    assert result["success"] is True
    assert result["text"] == "410 U.S. 113"


def test_citeurl_citation_analysis_unrecognized() -> None:
    """The citeurl analysis reports failure for unrecognized text."""
    result = _citeurl_citation_analysis("plainly not a citation sentence")
    assert result["success"] is False


def test_citeurl_citation_analysis_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """The citeurl analysis reports parsing exceptions as failures."""

    def raiser(*args: object, **kwargs: object) -> None:
        raise RuntimeError("citeurl exploded")

    monkeypatch.setattr("app.tools.citation.citeurl_cite", raiser)
    result = _citeurl_citation_analysis("410 U.S. 113")
    assert result["success"] is False
    assert "citeurl parsing error" in result["error"]


@pytest.mark.asyncio
async def test_lookup_citations_batch_requires_key(no_api_key: None) -> None:
    """The batch helper raises ValueError without an API key."""
    with pytest.raises(ValueError, match="COURT_LISTENER_API_KEY"):
        await _lookup_citations_batch(["410 U.S. 113"], None)


def test_parse_with_citator_returns_components(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_parse_with_citator extracts known attributes from the cite object."""

    class FakeCite:
        text = "410 U.S. 113"
        volume = "410"
        reporter = "U.S."
        page = "113"
        year = "1966"

    monkeypatch.setattr(
        "app.tools.citation.citeurl_cite", lambda *args, **kwargs: FakeCite()
    )
    result = _parse_with_citator("410 U.S. 113")
    assert result["volume"] == "410"
    assert result["reporter"] == "U.S."
    assert result["page"] == "113"
    assert result["year"] == "1966"


def test_parse_with_citator_handles_exceptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_parse_with_citator returns None when citeurl raises."""

    def raiser(*args: object, **kwargs: object) -> None:
        raise RuntimeError("citeurl exploded")

    monkeypatch.setattr("app.tools.citation.citeurl_cite", raiser)
    assert _parse_with_citator("410 U.S. 113") is None


def test_verify_with_citator_broad_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Citations matching only in broad mode are labeled accordingly."""
    fake_cite_obj = SimpleNamespace(
        text="410 U.S. 113",
        tokens={"volume": "410"},
        template="U.S. Reporter template",
    )

    def fake_cite(text: str, broad: bool = True, citator: object = None) -> object:
        return fake_cite_obj if broad else None

    monkeypatch.setattr("app.tools.citation.citeurl_cite", fake_cite)
    result = _verify_with_citator("410 U.S. 113", "410 U.S. 113")
    assert result["valid"] is True
    assert result["matching_mode"] == "broad"


def test_combined_citation_info_courtlistener_only() -> None:
    """CourtListener-only success lists only that source."""
    result = _combined_citation_info({
        "citeurl_analysis": {},
        "courtlistener_data": {"success": True, "data": [1]},
    })
    assert result == {
        "has_both_sources": False,
        "available_sources": ["courtlistener"],
    }


@pytest.mark.asyncio
async def test_extract_citations_from_text_tool_error(
    client: Client[Any], api_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Extraction errors are logged and re-raised as ToolError."""

    def raiser(*args: object, **kwargs: object) -> None:
        raise RuntimeError("extraction exploded")

    monkeypatch.setattr("app.tools.citation.list_cites", raiser)
    async with client:
        with pytest.raises(ToolError):
            await client.call_tool(
                "citation_extract_citations_from_text", {"text": "410 U.S. 113"}
            )
