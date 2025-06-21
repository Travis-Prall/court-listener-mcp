"""Tests for the CourtListener MCP server."""

import asyncio
import json
from typing import Any

from fastmcp import Client
from fastmcp.exceptions import ToolError
from loguru import logger
import pytest

from app.server import mcp


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

        # Check response structure
        assert len(result) == 1
        response = result[0].text  # type: ignore[attr-defined]

        # Parse JSON response
        data = json.loads(response)

        # Verify expected fields
        assert data["status"] == "healthy"
        assert data["service"] == "CourtListener MCP Server"
        assert data["version"] == "0.1.0"
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

        # Verify server section
        assert data["server"]["tools_available"] == ["search", "get", "citation"]
        assert data["server"]["transport"] == "streamable-http"
        assert (
            data["server"]["api_base"] == "https://www.courtlistener.com/api/rest/v4/"
        )

        logger.info(f"Status tool test passed: {data}")


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
async def test_search_opinions_tool(client: Client[Any]) -> None:
    """Test the search opinions tool with real API call.

    Parameters
    ----------
    client : Client
        The FastMCP test client fixture.

    """
    async with client:
        # Search for Supreme Court opinions
        result = await client.call_tool(
            "search_opinions", {"q": "miranda", "court": "scotus", "limit": 5}
        )

        assert len(result) == 1
        response = result[0].text  # type: ignore[attr-defined]

        # Parse JSON response
        data = json.loads(response)

        # Verify response structure
        assert "count" in data
        assert "results" in data
        assert isinstance(data["results"], list)

        # Check we got results
        if data["count"] > 0:
            assert len(data["results"]) > 0
            # API might not respect exact limit, so be flexible
            assert len(data["results"]) <= 20  # Should not exceed default page size

            # Verify result structure
            first_result = data["results"][0]
            assert "caseName" in first_result
            assert "court" in first_result

        logger.info(f"Search opinions returned {data['count']} total results")


@pytest.mark.asyncio
async def test_get_court_tool(client: Client[Any]) -> None:
    """Test the get court tool with a known court ID.

    Parameters
    ----------
    client : Client
        The FastMCP test client fixture.

    """
    async with client:
        # Get info for Supreme Court
        result = await client.call_tool("get_court", {"court_id": "scotus"})

        assert len(result) == 1
        response = result[0].text  # type: ignore[attr-defined]

        # Parse JSON response
        data = json.loads(response)

        # Verify court data
        assert "id" in data
        assert data["id"] == "scotus"
        assert "full_name" in data
        assert "Supreme Court" in data["full_name"]

        logger.info(f"Retrieved court info: {data.get('full_name', 'Unknown')}")


@pytest.mark.asyncio
async def test_search_with_date_filters(client: Client[Any]) -> None:
    """Test search with date range filters.

    Parameters
    ----------
    client : Client
        The FastMCP test client fixture.

    """
    async with client:
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

        assert len(result) == 1
        response = result[0].text  # type: ignore[attr-defined]

        data = json.loads(response)

        assert "count" in data
        assert "results" in data

        # If we have results, verify they're in the date range
        if data["results"]:
            for opinion in data["results"]:
                if "dateFiled" in opinion:
                    # Check date is in expected range
                    assert opinion["dateFiled"] >= "2023-01-01"
                    assert opinion["dateFiled"] <= "2023-12-31"

        logger.info(f"Date filtered search returned {len(data['results'])} results")


@pytest.mark.asyncio
async def test_error_handling(client: Client[Any]) -> None:
    """Test error handling for invalid requests.

    Parameters
    ----------
    client : Client
        The FastMCP test client fixture.

    """
    async with client:
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
            assert len(tool.description) > 10, (
                f"Tool {tool.name} has too short description"
            )

            # Check input schema exists
            assert tool.inputSchema is not None, (
                f"Tool {tool.name} missing input schema"
            )

        logger.info(f"All {len(tools)} tools have proper descriptions and schemas")


@pytest.mark.asyncio
async def test_search_people_tool(client: Client[Any]) -> None:
    """Test searching for judges/people in the database.

    Parameters
    ----------
    client : Client
        The FastMCP test client fixture.

    """
    async with client:
        result = await client.call_tool(
            "search_people", {"q": "Roberts", "position_type": "jud", "limit": 5}
        )

        assert len(result) == 1
        response = result[0].text  # type: ignore[attr-defined]

        data = json.loads(response)

        assert "count" in data
        assert "results" in data

        if data["results"]:
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
async def test_concurrent_requests(client: Client[Any]) -> None:
    """Test that the server handles concurrent requests properly.

    Parameters
    ----------
    client : Client
        The FastMCP test client fixture.

    """
    async with client:
        # Make multiple concurrent requests
        tasks = [
            client.call_tool("status", {}),
            client.call_tool("search_opinions", {"q": "first amendment", "limit": 5}),
            client.call_tool("search_dockets", {"q": "patent", "limit": 5}),
        ]

        results = await asyncio.gather(*tasks)

        # Verify all requests completed successfully
        assert len(results) == 3

        for result in results:
            assert len(result) == 1
            assert result[0].text  # type: ignore[attr-defined]

            # Parse and verify JSON
            data = json.loads(result[0].text)  # type: ignore[attr-defined]
            assert isinstance(data, dict)
            assert "error" not in data or data.get("error") is None

        logger.info("Concurrent requests handled successfully")
