"""Mocked-API tests for the CourtListener get tools and shared helpers.

All HTTP traffic is intercepted with respx, so these tests exercise the real
tool code without contacting the live CourtListener API.
"""

# Pytest assertions are the idiomatic test mechanism in this file.
# ruff: file-ignore[assert, unused-function-argument]

import json
from typing import Any

from fastmcp import Client
from fastmcp.exceptions import ToolError
import httpx
import pytest
import respx

from app.server import mcp
from app.tools.common import API_BASE_URL, auth_headers, log_error, log_info


@pytest.fixture
def client() -> Client[Any]:
    """Create a test client connected to the composed MCP server.

    Returns:
        Client: A FastMCP test client connected to the server instance.

    """
    return Client(mcp)


@pytest.mark.asyncio
async def test_get_opinion_public_access_without_key(
    client: Client[Any], no_api_key: None
) -> None:
    """Opinions are public and work without an API key.

    Args:
        client: FastMCP test client fixture.
        no_api_key: Fixture forcing the API key to None.

    """
    async with client, respx.mock:
        route = respx.get(f"{API_BASE_URL}/opinions/999/").mock(
            return_value=httpx.Response(200, json={"id": "999"})
        )
        result = await client.call_tool("get_opinion", {"opinion_id": "999"})

        assert result.content
        data = json.loads(result.content[0].text)
        assert data["id"] == "999"
        assert route.called
        assert not route.calls.last.request.headers.get("Authorization")


@pytest.mark.asyncio
async def test_get_docket_requires_api_key(
    client: Client[Any], no_api_key: None
) -> None:
    """Dockets require an API key; a missing key raises ToolError.

    Args:
        client: FastMCP test client fixture.
        no_api_key: Fixture forcing the API key to None.

    """
    async with client, respx.mock:
        with pytest.raises(ToolError):
            await client.call_tool("get_docket", {"docket_id": "123"})


@pytest.mark.asyncio
async def test_get_docket_with_api_key(client: Client[Any], api_key: str) -> None:
    """A docket fetch sends token auth and returns the record.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake API key.

    """
    async with client, respx.mock:
        route = respx.get(f"{API_BASE_URL}/dockets/123/").mock(
            return_value=httpx.Response(
                200, json={"id": "123", "case_name": "Test v. Case"}
            )
        )
        result = await client.call_tool("get_docket", {"docket_id": "123"})

        assert result.content
        data = json.loads(result.content[0].text)
        assert data["id"] == "123"
        request = route.calls.last.request
        assert request.headers["Authorization"] == f"Token {api_key}"


@pytest.mark.parametrize(
    ("tool_name", "endpoint", "record_id"),
    [
        ("get_audio", "audio", "55"),
        ("get_cluster", "clusters", "66"),
        ("get_person", "people", "77"),
    ],
)
@pytest.mark.asyncio
async def test_get_record_tools(
    client: Client[Any],
    api_key: str,
    tool_name: str,
    endpoint: str,
    record_id: str,
) -> None:
    """Every keyed get tool forwards its ID to the correct endpoint.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake API key.
        tool_name: Prefixed MCP tool name to call.
        endpoint: CourtListener API endpoint segment.
        record_id: The record ID to retrieve.

    """
    async with client, respx.mock:
        respx.get(f"{API_BASE_URL}/{endpoint}/{record_id}/").mock(
            return_value=httpx.Response(200, json={"id": record_id})
        )
        result = await client.call_tool(
            tool_name, {f"{tool_name.removeprefix('get_')}_id": record_id}
        )

        assert result.content
        data = json.loads(result.content[0].text)
        assert data["id"] == record_id


@pytest.mark.asyncio
async def test_get_record_http_status_error(client: Client[Any], api_key: str) -> None:
    """HTTP errors from the API surface to the client as ToolError.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake API key.

    """
    async with client, respx.mock:
        respx.get(f"{API_BASE_URL}/dockets/404/").mock(
            return_value=httpx.Response(404, json={"detail": "Not found"})
        )
        with pytest.raises(ToolError):
            await client.call_tool("get_docket", {"docket_id": "404"})


@pytest.mark.asyncio
async def test_get_record_generic_error(client: Client[Any], api_key: str) -> None:
    """Unexpected request errors are logged and re-raised.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake API key.

    """
    async with client, respx.mock:
        respx.get(f"{API_BASE_URL}/dockets/123/").mock(
            side_effect=httpx.ConnectError("connection failed")
        )
        with pytest.raises(ToolError):
            await client.call_tool("get_docket", {"docket_id": "123"})


def test_auth_headers_with_key(api_key: str) -> None:
    """auth_headers includes the token when a key is configured.

    Args:
        api_key: Fixture installing a fake API key.

    """
    assert auth_headers() == {"Authorization": f"Token {api_key}"}


def test_auth_headers_without_key(no_api_key: None) -> None:
    """auth_headers returns no Authorization header without a key.

    Args:
        no_api_key: Fixture forcing the API key to None.

    """
    assert auth_headers() == {}


@pytest.mark.asyncio
async def test_log_helpers_fall_back_to_logger() -> None:
    """log_info and log_error fall back to loguru when ctx is None."""
    await log_info(None, "info message without context")
    await log_error(None, "error message without context")
