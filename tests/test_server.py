"""Tests for the CourtListener MCP server."""

# Pytest assertions are the idiomatic test mechanism in this file.
# ruff: file-ignore[assert, unused-function-argument]

import asyncio
import json
from typing import Any

from fastmcp import Client
from fastmcp.exceptions import ToolError
import httpx
from loguru import logger
import pytest
import respx

from app.server import (
    DISABLED_TOOL_GROUPS,
    disable_tools_with_missing_api_keys,
    get_version,
    mcp,
)
from app.tools.common import API_BASE_URL, SEARCH_URL

# Shared test constants
MAX_PAGE_SIZE = 20
MIN_DESCRIPTION_LENGTH = 10
CONCURRENT_REQUEST_COUNT = 3
SEARCH_RESPONSE = {
    "count": 1,
    "results": [
        {
            "caseName": "Miranda v. Arizona",
            "court": "scotus",
            "dateFiled": "2023-06-15",
        }
    ],
}
COURT_RESPONSE = {
    "id": "scotus",
    "full_name": "Supreme Court of the United States",
    "jurisdiction": "F",
}
PEOPLE_RESPONSE = {
    "count": 1,
    "results": [{"id": 1, "name_first": "John", "name_last": "Roberts"}],
}


@pytest.fixture
def client() -> Client[Any]:
    """Create a test client connected to the real server.

    Returns
    -------
    Client
        A FastMCP test client connected to the server instance.

    """
    return Client(mcp)


@pytest.mark.asyncio
async def test_status_tool(client: Client[Any]) -> None:
    """Test the status tool returns expected server information.

    Parameters
    ----------
    client : Client
        The FastMCP test client fixture.

    """
    async with client:
        result = await client.call_tool("status", {})

        # Check response structure - result.content is a list of ContentBlocks
        assert result.content
        response = result.content[0].text  # type: ignore[attr-defined]

        # Parse JSON response
        data = json.loads(response)

        # Verify expected fields
        assert data["status"] == "healthy"
        assert data["service"] == "CourtListener MCP Server"
        assert data["version"] == "0.2.0"
        assert "timestamp" in data
        assert "environment" in data
        assert "system" in data
        assert "server" in data

        # Verify environment section
        assert "runtime" in data["environment"]
        assert "docker" in data["environment"]
        assert "python_version" in data["environment"]

        # Verify system section
        assert "process_uptime" in data["system"]
        assert "memory_mb" in data["system"]
        assert "cpu_percent" in data["system"]

        # Verify server section - all groups enabled because the conftest
        # autouse fixture re-enables key-gated groups before every test
        assert data["server"]["tools_available"] == [
            "search",
            "get",
            "citation",
            "statutes",
            "regulations",
        ]
        assert data["server"]["tools_disabled"] == []
        assert data["server"]["transport"] == "http"
        assert (
            data["server"]["api_base"] == "https://www.courtlistener.com/api/rest/v4/"
        )

        logger.info(f"Status tool test passed: {data}")


@pytest.mark.asyncio
async def test_health_endpoint_over_http() -> None:
    """Test the /health custom route via the ASGI app.

    The FastMCP HTTP deployment guide recommends an unauthenticated
    ``GET /health`` custom route for load balancers and container
    orchestrators. This test exercises it through ``mcp.http_app()``.

    """
    app = mcp.http_app(path="/mcp/")
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as http_client:
        response = await http_client.get("/health")

    assert response.status_code == httpx.codes.OK
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "CourtListener MCP Server"
    assert data["version"] == get_version()
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_imported_search_tools_available(client: Client[Any]) -> None:
    """Test that search tools were properly imported with prefix.

    Parameters
    ----------
    client : Client
        The FastMCP test client fixture.

    """
    async with client:
        # List all available tools
        tools = await client.list_tools()
        tool_names = [tool.name for tool in tools]

        # Check search tools are present with prefix
        expected_search_tools = [
            "search_opinions",
            "search_dockets",
            "search_audio",
            "search_people",
        ]

        for tool_name in expected_search_tools:
            assert tool_name in tool_names, f"Expected tool {tool_name} not found"

        logger.info(
            f"Found {len(expected_search_tools)} search tools with correct prefixes"
        )


@pytest.mark.asyncio
async def test_imported_get_tools_available(client: Client[Any]) -> None:
    """Test that get tools were properly imported with prefix.

    Parameters
    ----------
    client : Client
        The FastMCP test client fixture.

    """
    async with client:
        # List all available tools
        tools = await client.list_tools()
        tool_names = [tool.name for tool in tools]

        # Check get tools are present with prefix
        expected_get_tools = [
            "get_opinion",
            "get_docket",
            "get_audio",
            "get_cluster",
            "get_person",
            "get_court",
        ]

        for tool_name in expected_get_tools:
            assert tool_name in tool_names, f"Expected tool {tool_name} not found"

        logger.info(f"Found {len(expected_get_tools)} get tools with correct prefixes")


@pytest.mark.asyncio
async def test_search_opinions_tool(client: Client[Any], api_key: str) -> None:
    """Test the search opinions tool with a mocked API response.

    Parameters
    ----------
    client : Client
        The FastMCP test client fixture.

    api_key : str
        Fake API key fixture used by the tool modules.

    """
    async with client, respx.mock:
        respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        # Search for Supreme Court opinions
        result = await client.call_tool(
            "search_opinions", {"q": "miranda", "court": "scotus", "limit": 5}
        )

        assert result.content
        response = result.content[0].text  # type: ignore[attr-defined]

        # Parse JSON response
        data = json.loads(response)

        # Verify response structure
        assert "count" in data
        assert "results" in data
        assert isinstance(data["results"], list)

        # Check we got results
        if data["count"] > 0:
            assert len(data["results"]) > 0
            assert len(data["results"]) <= MAX_PAGE_SIZE  # Default page size

            # Verify result structure
            first_result = data["results"][0]
            assert "caseName" in first_result
            assert "court" in first_result

        logger.info(f"Search opinions returned {data['count']} total results")


@pytest.mark.asyncio
async def test_get_court_tool(client: Client[Any], api_key: str) -> None:
    """Test the get court tool with a mocked courts endpoint.

    Parameters
    ----------
    client : Client
        The FastMCP test client fixture.

    api_key : str
        Fake API key fixture used by the tool modules.

    """
    async with client, respx.mock:
        respx.get(f"{API_BASE_URL}/courts/scotus/").mock(
            return_value=httpx.Response(200, json=COURT_RESPONSE)
        )
        # Get info for Supreme Court
        result = await client.call_tool("get_court", {"court_id": "scotus"})

        assert result.content
        response = result.content[0].text  # type: ignore[attr-defined]

        # Parse JSON response
        data = json.loads(response)

        # Verify court data
        assert "id" in data
        assert data["id"] == "scotus"
        assert "full_name" in data
        assert "Supreme Court" in data["full_name"]

        logger.info(f"Retrieved court info: {data.get('full_name', 'Unknown')}")


@pytest.mark.asyncio
async def test_search_with_date_filters(client: Client[Any], api_key: str) -> None:
    """Test search with date range filters using a mocked API response.

    Parameters
    ----------
    client : Client
        The FastMCP test client fixture.

    api_key : str
        Fake API key fixture used by the tool modules.

    """
    async with client, respx.mock:
        route = respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        # Search for recent opinions
        result = await client.call_tool(
            "search_opinions",
            {
                "q": "constitutional",
                "filed_after": "2023-01-01",
                "filed_before": "2023-12-31",
                "limit": 10,
            },
        )

        assert result.content
        response = result.content[0].text  # type: ignore[attr-defined]

        data = json.loads(response)

        assert "count" in data
        assert "results" in data

        # Verify the date filters reached the API as query parameters
        params = route.calls.last.request.url.params
        assert params["filed_after"] == "2023-01-01"
        assert params["filed_before"] == "2023-12-31"

        # Verify returned results fall inside the mocked date range
        for opinion in data["results"]:
            if "dateFiled" in opinion:
                # Check date is in expected range
                assert opinion["dateFiled"] >= "2023-01-01"
                assert opinion["dateFiled"] <= "2023-12-31"

        logger.info(f"Date filtered search returned {len(data['results'])} results")


@pytest.mark.asyncio
async def test_error_handling(client: Client[Any]) -> None:
    """Test error handling for invalid requests using a mocked 404.

    Parameters
    ----------
    client : Client
        The FastMCP test client fixture.

    """
    async with client, respx.mock:
        # A 404 from the API must surface as a ToolError
        respx.get(f"{API_BASE_URL}/opinions/invalid-id-99999999/").mock(
            return_value=httpx.Response(404, json={"detail": "Not found"})
        )
        # Try to get a non-existent opinion - should raise ToolError
        with pytest.raises(ToolError):
            await client.call_tool("get_opinion", {"opinion_id": "invalid-id-99999999"})

        logger.info("Error handling test passed - exception was raised as expected")


@pytest.mark.asyncio
async def test_tool_descriptions(client: Client[Any]) -> None:
    """Test that all tools have proper descriptions.

    Parameters
    ----------
    client : Client
        The FastMCP test client fixture.

    """
    async with client:
        tools = await client.list_tools()

        for tool in tools:
            # Check tool has a name
            assert tool.name

            # Check tool has a description
            assert tool.description, f"Tool {tool.name} missing description"

            # Check description is meaningful (not empty or too short)
            assert len(tool.description) > MIN_DESCRIPTION_LENGTH, (
                f"Tool {tool.name} has too short description"
            )

            # Check input schema exists
            assert tool.input_schema is not None, (
                f"Tool {tool.name} missing input schema"
            )

        logger.info(f"All {len(tools)} tools have proper descriptions and schemas")


@pytest.mark.asyncio
async def test_search_people_tool(client: Client[Any], api_key: str) -> None:
    """Test searching for judges/people with a mocked API response.

    Parameters
    ----------
    client : Client
        The FastMCP test client fixture.

    api_key : str
        Fake API key fixture used by the tool modules.

    """
    async with client, respx.mock:
        respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(200, json=PEOPLE_RESPONSE)
        )
        result = await client.call_tool(
            "search_people", {"q": "Roberts", "position_type": "jud", "limit": 5}
        )

        assert result.content
        response = result.content[0].text  # type: ignore[attr-defined]

        data = json.loads(response)

        assert "count" in data
        assert "results" in data

        person = data["results"][0]
        # Check for any name-related field (API might have different field names)
        name_fields = [
            "name_first",
            "name_last",
            "name",
            "name_full",
            "absolute_url",
        ]
        assert any(field in person for field in name_fields), (
            f"No name field found in person: {list(person.keys())}"
        )

        logger.info(f"People search found {data['count']} judges named Roberts")


@pytest.mark.asyncio
async def test_concurrent_requests(client: Client[Any], api_key: str) -> None:
    """Test that the server handles concurrent requests properly.

    Parameters
    ----------
    client : Client
        The FastMCP test client fixture.

    api_key : str
        Fake API key fixture used by the tool modules.

    """
    async with client, respx.mock:
        respx.get(SEARCH_URL).mock(
            return_value=httpx.Response(200, json=SEARCH_RESPONSE)
        )
        # Make multiple concurrent requests
        tasks = [
            client.call_tool("status", {}),
            client.call_tool("search_opinions", {"q": "first amendment", "limit": 5}),
            client.call_tool("search_dockets", {"q": "patent", "limit": 5}),
        ]

        results = await asyncio.gather(*tasks)

        # Verify all requests completed successfully
        assert len(results) == CONCURRENT_REQUEST_COUNT

        for result in results:
            assert result.content
            assert result.content[0].text  # type: ignore[attr-defined]

            # Parse and verify JSON
            data = json.loads(result.content[0].text)  # type: ignore[attr-defined]
            assert isinstance(data, dict)
            assert "error" not in data or data.get("error") is None

        logger.info("Concurrent requests handled successfully")


@pytest.mark.asyncio
async def test_missing_govinfo_key_disables_statute_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing GOVINFO_API_KEY disables the statutes tool group.

    The group disappears from list_tools, cannot be called, and the
    status tool reports it under tools_disabled.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        The pytest monkeypatch fixture.

    """
    monkeypatch.setenv("COURT_LISTENER_API_KEY", "present")
    monkeypatch.delenv("GOVINFO_API_KEY", raising=False)
    disabled = disable_tools_with_missing_api_keys()
    try:
        assert disabled == ["statutes"]
        assert DISABLED_TOOL_GROUPS == ["statutes"]

        async with Client(mcp) as client:
            names = {tool.name for tool in await client.list_tools()}
            assert not any(name.startswith("statutes") for name in names)
            # Other groups remain available
            assert "search_opinions" in names

            # Calling a disabled tool behaves as if it does not exist
            with pytest.raises(ToolError):
                await client.call_tool(
                    "statutes_search_statutes", {"query": "civil rights"}
                )

            # The status tool reflects the disabled group
            result = await client.call_tool("status", {})
            assert result.content
            data = json.loads(result.content[0].text)  # type: ignore[attr-defined]
            assert data["server"]["tools_available"] == [
                "search",
                "get",
                "citation",
                "regulations",
            ]
            assert data["server"]["tools_disabled"] == ["statutes"]
    finally:
        mcp.enable(tags={"requires-govinfo-key"})
        if "statutes" in DISABLED_TOOL_GROUPS:
            DISABLED_TOOL_GROUPS.remove("statutes")


@pytest.mark.asyncio
async def test_missing_courtlistener_key_disables_courtlistener_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing COURT_LISTENER_API_KEY disables search/get/citation tools.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        The pytest monkeypatch fixture.

    """
    monkeypatch.setenv("GOVINFO_API_KEY", "present")
    monkeypatch.delenv("COURT_LISTENER_API_KEY", raising=False)
    disabled = disable_tools_with_missing_api_keys()
    try:
        assert disabled == ["search", "get", "citation"]
        assert DISABLED_TOOL_GROUPS == ["search", "get", "citation"]

        async with Client(mcp) as client:
            names = {tool.name for tool in await client.list_tools()}
            assert not any(name.startswith(("search_", "get_")) for name in names)
            # The statutes group remains available
            assert any(name.startswith("statutes") for name in names)
    finally:
        mcp.enable(tags={"requires-courtlistener-key"})
        for group in ("search", "get", "citation"):
            if group in DISABLED_TOOL_GROUPS:
                DISABLED_TOOL_GROUPS.remove(group)
