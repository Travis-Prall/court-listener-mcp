"""Tests for the server enhancements: middleware, ASGI app, config, metadata.

Covers the FastMCP 4 deployment improvements added to the CourtListener ++
MCP server: the observability middleware stack, the exported ASGI
application, the CORS decision logic, the new HTTP deployment configuration
knobs, and the protocol-level tool metadata (titles and annotations).
"""

# Pytest assertions are the idiomatic test mechanism in this file.
# ruff: file-ignore[assert]

from typing import Any

from fastmcp import Client
import pytest
from starlette.middleware.cors import CORSMiddleware
from starlette.testclient import TestClient

from app.config import Config, config
import app.server as server_module
from app.server import app, mcp

# Total number of tools the server advertises when every API-key-gated
# group is enabled (the test suite re-enables them via conftest).
EXPECTED_TOOL_COUNT = 30
HTTP_OK_STATUS = 200


def test_observability_middleware_registered_in_order() -> None:
    """Error handling, timing, and logging middleware are registered in order."""
    names = [type(middleware).__name__ for middleware in mcp.middleware]
    assert "ErrorHandlingMiddleware" in names
    assert "TimingMiddleware" in names
    assert "LoggingMiddleware" in names

    # Declaration order: error handling first, logging last (reverse on the
    # way out), so logging observes the final behavior of the pipeline.
    assert (
        names.index("ErrorHandlingMiddleware")
        < names.index("TimingMiddleware")
        < names.index("LoggingMiddleware")
    )


def test_asgi_app_exposes_mcp_and_health_routes() -> None:
    """The exported ASGI app serves /mcp/ and the /health probe."""
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/mcp/" in paths
    assert "/health" in paths


def test_health_route_returns_healthy_over_http() -> None:
    """The /health custom route answers 200 with a coarse status body."""
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == HTTP_OK_STATUS
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "CourtListener ++ MCP Server"
    assert "version" in body
    assert "timestamp" in body


def test_cors_middleware_absent_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No CORS middleware is built when no browser origins are configured."""
    monkeypatch.setattr(config, "cors_allow_origins", [])
    assert server_module._cors_middleware() == []


def test_cors_middleware_present_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configured browser origins produce a single CORSMiddleware entry."""
    monkeypatch.setattr(config, "cors_allow_origins", ["https://example.com"])
    middleware = server_module._cors_middleware()

    assert len(middleware) == 1
    assert middleware[0].cls is CORSMiddleware
    assert middleware[0].kwargs["allow_origins"] == ["https://example.com"]
    # The session-id header must be exposed so browsers can read it.
    assert "mcp-session-id" in middleware[0].kwargs["expose_headers"]


@pytest.mark.parametrize(
    ("field_name", "expected_default"),
    [
        ("mcp_path", "/mcp/"),
        ("cors_allow_origins", []),
    ],
)
def test_http_deployment_config_defaults(
    field_name: str, expected_default: Any
) -> None:
    """The project-specific HTTP deployment knobs default safely (CORS off)."""
    assert Config.model_fields[field_name].default == expected_default


async def test_all_tools_advertise_titles_and_annotations() -> None:
    """Every tool exposes a title and a complete set of read-only hints."""
    async with Client(mcp) as client:
        tools = await client.list_tools()

    assert len(tools) == EXPECTED_TOOL_COUNT

    for tool in tools:
        assert tool.title, f"{tool.name} is missing a title"
        annotations = tool.annotations
        assert annotations is not None, f"{tool.name} is missing annotations"
        assert annotations.read_only_hint is True
        assert annotations.destructive_hint is False
        assert annotations.idempotent_hint is True
        assert annotations.open_world_hint is True


async def test_search_opinions_tool_metadata() -> None:
    """A representative tool exposes the expected title and annotation hints."""
    async with Client(mcp) as client:
        tools = await client.list_tools()

    opinions = next(tool for tool in tools if tool.name == "search_opinions")
    assert opinions.title == "Search Court Opinions"
    assert opinions.annotations is not None
    assert opinions.annotations.read_only_hint is True
