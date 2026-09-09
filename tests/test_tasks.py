"""Tests for MCP background task execution (SEP-2663).

The server registers the FastMCP tasks extension and marks long-running
tools with ``task=True``. These tests prove that task-capable clients
can drive those tools through the background-task flow, with all HTTP
traffic intercepted by respx.
"""

# Pytest assertions are the idiomatic test mechanism in this file.
# ruff: file-ignore[assert, unused-function-argument]

import json
from typing import Any

from fastmcp import Client
from fastmcp.exceptions import ToolError
from fastmcp_tasks import call_tool_task
import httpx
import pytest
import respx

from app.server import mcp
from app.tools.common import CITATION_LOOKUP_URL

# Mirrors the citation-lookup API response shape used by the mocked
# citation tests.
CITATION_LOOKUP_RESPONSE: dict[str, Any] = {
    "results": [
        {
            "citation": "410 U.S. 113",
            "matched_opinions": [{"caseName": "Miranda v. Arizona", "id": 1}],
        }
    ]
}


@pytest.fixture
def client() -> Client[Any]:
    """Create a task-capable test client connected to the server.

    Returns:
        Client: A FastMCP test client connected to the server instance.

    """
    return Client(mcp, mode="auto")


@pytest.mark.asyncio
async def test_batch_lookup_runs_as_background_task(
    client: Client[Any], api_key: str
) -> None:
    """A task=True tool executes in the background and returns a handle.

    call_tool_task starts citation_batch_lookup_citations as a background
    task, the task completes, and the result matches a synchronous call.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake CourtListener API key.

    """
    async with client, respx.mock:
        respx.post(CITATION_LOOKUP_URL).mock(
            return_value=httpx.Response(200, json=CITATION_LOOKUP_RESPONSE)
        )
        task = await call_tool_task(
            client,
            "citation_batch_lookup_citations",
            {"citations": ["410 U.S. 113"]},
        )
        assert task.task_id

        status = await task.wait(timeout=30.0)
        assert status.status == "completed"

        result = await task.result()
        assert result.content
        data = json.loads(result.content[0].text)
        assert data["results"][0]["citation"] == "410 U.S. 113"


@pytest.mark.asyncio
async def test_task_tool_also_callable_synchronously(
    client: Client[Any], api_key: str
) -> None:
    """Task-capable tools still work for ordinary synchronous calls.

    mode="optional" execution means clients without the tasks capability
    (or callers not opting in) get normal synchronous execution.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake CourtListener API key.

    """
    async with client, respx.mock:
        respx.post(CITATION_LOOKUP_URL).mock(
            return_value=httpx.Response(200, json=CITATION_LOOKUP_RESPONSE)
        )
        result = await client.call_tool(
            "citation_batch_lookup_citations", {"citations": ["410 U.S. 113"]}
        )
        assert result.content
        data = json.loads(result.content[0].text)
        assert data["results"][0]["citation"] == "410 U.S. 113"


@pytest.mark.asyncio
async def test_non_task_tool_rejects_call_tool_task(
    client: Client[Any], api_key: str
) -> None:
    """call_tool_task on a task-forbidden tool raises ToolError.

    Args:
        client: FastMCP test client fixture.
        api_key: Fixture installing a fake CourtListener API key.

    """
    async with client:
        with pytest.raises(ToolError):
            await call_tool_task(client, "citation_parse_citation", {})
