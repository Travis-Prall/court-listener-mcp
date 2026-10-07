"""Live-API integration tests for the CourtListener-backed tools.

These tests exercise the real ``www.courtlistener.com`` REST API using the
``COURT_LISTENER_API_KEY`` from the environment (loaded from ``.env``), and
are skipped automatically when no key is configured so the suite stays
runnable in CI or on machines without credentials. They cover every
CourtListener tool: the ``status`` tool, the ``search_*`` group, the
``get_*`` group, and the ``citation_*`` group.

The public search API throttles bursts of requests, so calls are spaced out
and retried with backoff on HTTP 429. Run them explicitly with:

    uv run pytest tests/test_courtlistener_integration.py -v
"""

# Pytest assertions are the idiomatic test mechanism in this file.
# ruff: file-ignore[assert]

import asyncio
import json
import os
import time
from typing import Any

from fastmcp import Client
import pytest

from app.server import get_version, mcp

COURT_LISTENER_API_KEY = os.getenv("COURT_LISTENER_API_KEY")

pytestmark = pytest.mark.skipif(
    not COURT_LISTENER_API_KEY,
    reason="COURT_LISTENER_API_KEY not set; live CourtListener tests skipped",
)

# Brown v. Board of Education, 347 U.S. 483 - a stable, well-known citation.
CITATION = "347 U.S. 483"
SEARCH_QUERY = "miranda warning"
DOCKET_QUERY = "apple"
RECAP_QUERY = "motion to dismiss"
AUDIO_QUERY = "oral argument"
PEOPLE_QUERY = "john roberts"

# CourtListener allows authenticated users ~5 requests/minute (rolling window),
# so requests are spaced well apart and 429s retried with backoff.
REQUEST_SPACING_SECONDS = 15.0
BACKOFF_BASE_SECONDS = 15.0
MAX_429_RETRIES = 5

# Cache of record IDs harvested from live searches, reused across tests.
_IDS: dict[str, str] = {}
# Monotonic timestamp of the last live request, used to space requests out.
_RATE: dict[str, float] = {"last_call": 0.0}


@pytest.fixture
def client() -> Client[Any]:
    """Create a test client connected to the composed MCP server.

    Returns:
        Client: A FastMCP test client connected to the server instance.

    """
    return Client(mcp)


async def _call(client: Client[Any], name: str, args: dict[str, Any]) -> Any:
    """Call a tool, retrying with backoff when the upstream API rate-limits.

    Args:
        client: Connected FastMCP test client.
        name: Tool name to invoke.
        args: Tool arguments.

    Returns:
        Any: The tool call result.

    Raises:
        AssertionError: If the request stays rate-limited after all retries.

    """
    for attempt in range(MAX_429_RETRIES):
        try:
            return await client.call_tool(name, args)
        except Exception as exc:
            message = str(exc)
            throttled = "429" in message or "Rate limited" in message
            if throttled and attempt < MAX_429_RETRIES - 1:
                await asyncio.sleep(BACKOFF_BASE_SECONDS * (attempt + 1))
                continue
            raise
    raise AssertionError(f"unreachable: rate-limit retries exhausted for {name}")


async def _data(client: Client[Any], name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Call a tool and return its parsed JSON object payload.

    Requests are spaced apart to respect upstream throttling, then retried on
    rate limits by :func:`_call`.

    Args:
        client: Connected FastMCP test client.
        name: Tool name to invoke.
        args: Tool arguments.

    Returns:
        dict[str, Any]: The parsed JSON response body.

    """
    wait = REQUEST_SPACING_SECONDS - (time.monotonic() - _RATE["last_call"])
    await asyncio.sleep(max(0.0, wait))
    result = await _call(client, name, args)
    _RATE["last_call"] = time.monotonic()
    assert result.content, f"{name} returned no content"
    return json.loads(result.content[0].text)


async def _record_id(client: Client[Any], kind: str) -> str:
    """Return a live record ID of the given kind, harvested once and cached.

    Opinion, cluster, and docket IDs are harvested together from a live opinion
    search; audio and person IDs come from their respective searches. Results
    are cached in the module-level ``_IDS`` map so later tests reuse them.

    Args:
        client: Connected FastMCP test client.
        kind: One of 'opinion', 'cluster', 'docket', 'audio', 'person'.

    Returns:
        str: A validated live record ID of the requested kind.

    Raises:
        ValueError: If an unknown record kind is requested.

    """
    if kind in _IDS:
        return _IDS[kind]
    if kind in {"opinion", "cluster", "docket"}:
        data = await _data(client, "search_opinions", {"q": SEARCH_QUERY, "limit": 1})
        hit = data["results"][0]
        _IDS["opinion"] = str(hit["opinions"][0]["id"])
        _IDS["cluster"] = str(hit["cluster_id"])
        _IDS["docket"] = str(hit["docket_id"])
    elif kind == "audio":
        data = await _data(client, "search_audio", {"q": AUDIO_QUERY, "limit": 1})
        _IDS["audio"] = str(data["results"][0]["id"])
    elif kind == "person":
        data = await _data(client, "search_people", {"q": PEOPLE_QUERY, "limit": 1})
        _IDS["person"] = str(data["results"][0]["id"])
    else:  # pragma: no cover - guards against typos in test code
        raise ValueError(f"unknown record kind: {kind}")
    return _IDS[kind]


async def test_status_live(client: Client[Any]) -> None:
    """The status tool reports a healthy, HTTP-transport server.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        data = await _data(client, "status", {})
    assert data["status"] == "healthy"
    assert data["service"] == "CourtListener ++ MCP Server"
    assert data["version"] == get_version()
    assert data["timestamp"]
    assert data["server"]["transport"] == "http"
    assert isinstance(data["server"]["tools_available"], list)
    assert data["server"]["api_base"].startswith("https://www.courtlistener.com")


async def test_search_opinions_live(client: Client[Any]) -> None:
    """A live opinion search returns real opinion-cluster results.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        data = await _data(client, "search_opinions", {"q": SEARCH_QUERY, "limit": 2})
    assert data["count"]
    assert data["results"]
    first = data["results"][0]
    assert first["caseName"]
    assert "cluster_id" in first
    assert "docket_id" in first
    assert first["opinions"]
    _IDS["opinion"] = str(first["opinions"][0]["id"])
    _IDS["cluster"] = str(first["cluster_id"])
    _IDS["docket"] = str(first["docket_id"])


async def test_search_dockets_live(client: Client[Any]) -> None:
    """A live docket search returns real federal dockets.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        data = await _data(client, "search_dockets", {"q": DOCKET_QUERY, "limit": 2})
    assert data["count"]
    assert data["results"]
    assert "docket_id" in data["results"][0]


async def test_search_dockets_with_documents_live(client: Client[Any]) -> None:
    """A live RECAP docket search returns dockets with filing documents.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        data = await _data(
            client, "search_dockets_with_documents", {"q": DOCKET_QUERY, "limit": 2}
        )
    assert data["count"]
    assert data["results"]
    assert "docket_id" in data["results"][0]


async def test_search_recap_documents_live(client: Client[Any]) -> None:
    """A live RECAP document search returns filing documents with IDs.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        data = await _data(
            client, "search_recap_documents", {"q": RECAP_QUERY, "limit": 2}
        )
    assert data["count"]
    assert data["results"]
    assert "id" in data["results"][0]


async def test_search_audio_live(client: Client[Any]) -> None:
    """A live oral-argument audio search returns recordings with IDs.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        data = await _data(client, "search_audio", {"q": AUDIO_QUERY, "limit": 2})
    assert data["count"]
    assert data["results"]
    assert "id" in data["results"][0]
    _IDS["audio"] = str(data["results"][0]["id"])


async def test_search_people_live(client: Client[Any]) -> None:
    """A live judge/person search returns legal professionals with IDs.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        data = await _data(client, "search_people", {"q": PEOPLE_QUERY, "limit": 2})
    assert data["count"]
    assert data["results"]
    assert "id" in data["results"][0]
    _IDS["person"] = str(data["results"][0]["id"])


async def test_get_court_live(client: Client[Any]) -> None:
    """Fetching the Supreme Court record by its slug returns that court.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        data = await _data(client, "get_court", {"court_id": "scotus"})
    assert data["id"] == "scotus"
    assert data["full_name"]


async def test_get_opinion_live(client: Client[Any]) -> None:
    """Fetching an opinion by ID returns the record with the same ID.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        opinion_id = await _record_id(client, "opinion")
        data = await _data(client, "get_opinion", {"opinion_id": opinion_id})
    assert str(data["id"]) == opinion_id


async def test_get_cluster_live(client: Client[Any]) -> None:
    """Fetching an opinion cluster by ID returns the record with its case name.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        cluster_id = await _record_id(client, "cluster")
        data = await _data(client, "get_cluster", {"cluster_id": cluster_id})
    assert str(data["id"]) == cluster_id
    assert data["case_name"]


async def test_get_docket_live(client: Client[Any]) -> None:
    """Fetching a docket by ID returns the record with the same ID.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        docket_id = await _record_id(client, "docket")
        data = await _data(client, "get_docket", {"docket_id": docket_id})
    assert str(data["id"]) == docket_id


async def test_get_audio_live(client: Client[Any]) -> None:
    """Fetching an audio recording by ID returns the record with the same ID.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        audio_id = await _record_id(client, "audio")
        data = await _data(client, "get_audio", {"audio_id": audio_id})
    assert str(data["id"]) == audio_id


async def test_get_person_live(client: Client[Any]) -> None:
    """Fetching a person by ID returns the record with the same ID.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        person_id = await _record_id(client, "person")
        data = await _data(client, "get_person", {"person_id": person_id})
    assert str(data["id"]) == person_id


async def test_citation_lookup_citation_live(client: Client[Any]) -> None:
    """A live citation lookup resolves the citation to an opinion cluster.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        data = await _data(client, "citation_lookup_citation", {"citation": CITATION})
    assert data["results"]
    assert data["results"][0]["citation"] == CITATION
    assert data["results"][0]["clusters"]


async def test_citation_get_citations_live(client: Client[Any]) -> None:
    """Looking up citations from a text block returns matching cases.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        data = await _data(client, "citation_get_citations", {"citation": CITATION})
    assert data["results"]


async def test_citation_batch_lookup_live(client: Client[Any]) -> None:
    """A batch citation lookup returns per-citation results.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        data = await _data(client, "citation_batch_lookup", {"citations": [CITATION]})
    assert data["results"]


async def test_citation_batch_lookup_citations_live(client: Client[Any]) -> None:
    """The CiteURL batch lookup returns per-citation results.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        data = await _data(
            client, "citation_batch_lookup_citations", {"citations": [CITATION]}
        )
    assert data["results"]


async def test_citation_get_citation_details_live(client: Client[Any]) -> None:
    """Detailed lookup by citation ID returns the citation record.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        data = await _data(
            client, "citation_get_citation_details", {"citation_id": CITATION}
        )
    assert data["results"]
    assert data["results"][0]["citation"] == CITATION


async def test_citation_enhanced_citation_lookup_live(client: Client[Any]) -> None:
    """The enhanced lookup combines CiteURL parsing with CourtListener data.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        data = await _data(
            client, "citation_enhanced_citation_lookup", {"citation": CITATION}
        )
    assert data["citation"] == CITATION
    assert data["citeurl_analysis"]["success"] is True
    assert data["courtlistener_data"]["success"] is True
    assert data["combined_info"]["has_both_sources"] is True


async def test_citation_parse_citation_live(client: Client[Any]) -> None:
    """Offline parsing decomposes a citation into its structural components.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        data = await _data(client, "citation_parse_citation", {"citation": CITATION})
    assert data["success"] is True
    assert data["parser_used"]
    assert data["original"] == CITATION


async def test_citation_parse_citation_with_citeurl_live(client: Client[Any]) -> None:
    """CiteURL parsing returns structured token and template data.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        data = await _data(
            client, "citation_parse_citation_with_citeurl", {"citation": CITATION}
        )
    assert data["success"] is True
    assert data["citation"] == CITATION
    assert data["parsed"]["text"]


async def test_citation_validate_citation_live(client: Client[Any]) -> None:
    """Offline validation accepts a well-formed U.S. reporter citation.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        data = await _data(client, "citation_validate_citation", {"citation": CITATION})
    assert data["valid"] is True
    assert data["citation"] == CITATION


async def test_citation_verify_citation_format_live(client: Client[Any]) -> None:
    """Format verification recognises a valid reporter citation.

    Args:
        client: FastMCP test client fixture.

    """
    async with client:
        data = await _data(
            client, "citation_verify_citation_format", {"citation": CITATION}
        )
    assert data["valid"] is True
    assert data["citation"] == CITATION


async def test_citation_extract_citations_from_text_live(client: Client[Any]) -> None:
    """Citation extraction finds each citation in a block of prose.

    Args:
        client: FastMCP test client fixture.

    """
    text = f"See {CITATION} (1954) and 410 U.S. 113 (1973)."
    async with client:
        data = await _data(
            client, "citation_extract_citations_from_text", {"text": text}
        )
    assert data["total_citations"]
    assert data["citations"]
    assert data["text_length"] == len(text)
