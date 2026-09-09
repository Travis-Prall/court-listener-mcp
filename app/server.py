#!/usr/bin/env python3
"""CourtListener ++ MCP Server - FastMCP Implementation."""

import asyncio
from datetime import UTC, datetime
import os
from pathlib import Path
import sys
import tomllib
from typing import TYPE_CHECKING, Any

from fastmcp import FastMCP
from fastmcp_tasks import TasksExtension
from loguru import logger
import psutil
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from starlette.requests import Request

from app.config import config
from app.tools import (
    citation_server,
    get_server,
    govinfo_server,
    regulations_server,
    search_server,
)

# Configure logging
log_path = Path(__file__).parent / "logs" / "server.log"
log_path.parent.mkdir(exist_ok=True)
logger.add(log_path, rotation="1 MB", retention="1 week")


def get_version() -> str:
    """Get the version from pyproject.toml.

    Returns:
        The version string from pyproject.toml or 'unknown' if not found.

    """
    try:
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        with pyproject_path.open("rb") as f:
            data = tomllib.load(f)
        return data.get("project", {}).get("version", "unknown")
    except Exception:
        return "unknown"


def is_docker() -> bool:
    """Check if running inside a Docker container.

    Returns:
        True if running inside Docker, False otherwise.

    """
    return Path("/.dockerenv").exists() or (
        Path("/proc/1/cgroup").exists()
        and any(
            "docker" in line for line in Path("/proc/1/cgroup").open(encoding="utf-8")
        )
    )


# Create main server instance
mcp: FastMCP[Any] = FastMCP(
    name="CourtListener ++ MCP Server",
    instructions=(
        "Model Context Protocol server providing LLMs with access to the "
        "CourtListener legal database and United States statutes via the "
        "official GovInfo API. This server enables searching for legal "
        "opinions, cases, audio recordings, dockets, and people in the legal "
        "system. It also provides citation lookup, parsing, and validation "
        "tools using both the CourtListener API and citeurl library, plus "
        "statute search and lookup tools covering the United States Code, "
        "Statutes at Large, Public and Private Laws, and Statutes "
        "Compilations through the GovInfo API (requires GOVINFO_API_KEY), "
        "and Regulations.gov tools for searching federal rulemaking "
        "documents (requires REGULATIONS_API_KEY). "
        "Available tools include: search operations for opinions/cases/audio/"
        "dockets/people, get operations for specific records by ID, "
        "comprehensive citation tools for parsing, validating, and looking "
        "up legal citations, GovInfo statute tools for searching and "
        "retrieving enacted federal laws, and Regulations.gov tools for "
        "searching federal rulemaking documents."
    ),
)

# Register the MCP background tasks extension (SEP-2663). Long-running
# tools marked with task=True (e.g. citation batch lookups, statute
# content downloads) can then execute in the background for clients
# that opt in to the tasks capability. Uses the in-memory backend by
# default; configure FASTMCP_DOCKET_URL for a Redis-backed deployment.
mcp.add_extension(TasksExtension())

# All tool groups exposed by this server, in a stable reporting order.
ALL_TOOL_GROUPS: tuple[str, ...] = (
    "search",
    "get",
    "citation",
    "statutes",
    "regulations",
)

# API key env vars mapped to the tool groups they gate. Each entry is
# (environment variable, tool tag, tuple of tool-group names). Tools are
# tagged at creation (e.g. ``@govinfo_server.tool(tags={"requires-..."}))``;
# add future key-gated groups (e.g. Regulations.gov) here and tag their
# tools to include them in the startup check automatically.
API_KEY_TOOL_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "COURT_LISTENER_API_KEY",
        "requires-courtlistener-key",
        ("search", "get", "citation"),
    ),
    ("GOVINFO_API_KEY", "requires-govinfo-key", ("statutes",)),
    ("REGULATIONS_API_KEY", "requires-regulations-key", ("regulations",)),
)

# Names of tool groups disabled at startup due to missing API keys.
# Reported by the status tool and used by tests.
DISABLED_TOOL_GROUPS: list[str] = []


@mcp.tool()
def status() -> dict[str, Any]:
    """Check the status of the CourtListener ++ MCP server.

    Returns:
        A dictionary containing server status, system metrics, and service information.

    """
    logger.info("Status check requested")

    # Get system info using psutil
    process = psutil.Process()
    process_start = datetime.fromtimestamp(process.create_time(), tz=UTC)
    uptime_seconds = (datetime.now(UTC) - process_start).total_seconds()

    # Format uptime as human readable
    hours, remainder = divmod(int(uptime_seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    # Docker and environment info
    docker_info = is_docker()
    environment = "docker" if docker_info else "native"

    return {
        "status": "healthy",
        "service": "CourtListener ++ MCP Server",
        "version": get_version(),
        "timestamp": datetime.now(UTC).isoformat(),
        "environment": {
            "runtime": environment,
            "docker": docker_info,
            "python_version": sys.version.split()[0],
        },
        "system": {
            "process_uptime": uptime,
            "memory_mb": round(process.memory_info().rss / 1024 / 1024, 1),
            "cpu_percent": round(process.cpu_percent(interval=0.1), 1),
        },
        "server": {
            "tools_available": [
                group for group in ALL_TOOL_GROUPS if group not in DISABLED_TOOL_GROUPS
            ],
            "tools_disabled": list(DISABLED_TOOL_GROUPS),
            "transport": "http",
            "api_base": "https://www.courtlistener.com/api/rest/v4/",
            "host": config.host,
            "port": config.mcp_port,
        },
    }


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Return a lightweight liveness probe for load balancers and containers.

    Custom routes are unauthenticated by design, so this endpoint reports
    only coarse status data and no tool, key, or environment details. Use
    it for Docker ``HEALTHCHECK``, Kubernetes probes, and uptime monitoring
    (see the FastMCP HTTP deployment guide).

    Args:
        request: The incoming Starlette request.

    Returns:
        JSONResponse: A JSON body with ``status``, ``service``, ``version``,
        and ``timestamp`` fields.

    """
    client_host = request.client.host if request.client else "unknown"
    logger.debug(f"Health check requested from {client_host}")
    # Drain (and discard) any request body so the probe connection is
    # cleanly handled before the response is sent.
    await request.body()
    return JSONResponse({
        "status": "healthy",
        "service": "CourtListener ++ MCP Server",
        "version": get_version(),
        "timestamp": datetime.now(UTC).isoformat(),
    })


def disable_tools_with_missing_api_keys() -> list[str]:
    """Disable tool groups whose required API key is not configured.

    Iterates :data:`API_KEY_TOOL_GROUPS`, disables every tool tagged with
    the group's ``requires-*-key`` tag when the key is absent from the
    environment, and logs a warning for each disabled group. Disabled
    tools are hidden from clients (they disappear from ``list_tools``)
    and cannot be called. Set the missing key and restart the server to
    re-enable the group.

    Returns:
        list[str]: Names of the tool groups disabled by this call.

    """
    disabled: list[str] = []
    for env_var, tag, groups in API_KEY_TOOL_GROUPS:
        if os.getenv(env_var):
            continue
        mcp.disable(tags={tag})
        for group in groups:
            if group not in DISABLED_TOOL_GROUPS:
                DISABLED_TOOL_GROUPS.append(group)
        disabled.extend(groups)
        logger.warning(
            f"{env_var} not set - disabled {', '.join(groups)} tools "
            f"(tag '{tag}'). Set {env_var} and restart to enable them."
        )
    return disabled


def setup() -> None:
    """Set up the server by mounting subservers."""
    logger.info("Setting up CourtListener ++ MCP server")

    # Mount search tools under the "search" namespace
    mcp.mount(search_server, namespace="search")
    logger.info("Mounted search server tools")

    # Mount get tools under the "get" namespace
    mcp.mount(get_server, namespace="get")
    logger.info("Mounted get server tools")

    # Mount citation tools under the "citation" namespace
    mcp.mount(citation_server, namespace="citation")
    logger.info("Mounted citation server tools")

    # Mount GovInfo statute tools under the "statutes" namespace
    mcp.mount(govinfo_server, namespace="statutes")
    logger.info("Mounted GovInfo statutes server tools")

    # Mount Regulations.gov tools under the "regulations" namespace
    mcp.mount(regulations_server, namespace="regulations")
    logger.info("Mounted Regulations.gov server tools")

    # Hide tool groups whose API keys are missing so clients never see
    # tools that would fail on every call.
    disable_tools_with_missing_api_keys()

    logger.info("Server setup complete")


# Run setup when module is imported
setup()


async def main() -> None:
    """Run the CourtListener ++ MCP server with HTTP (streamable) transport."""
    logger.info("Starting CourtListener ++ MCP server with HTTP (streamable) transport")
    logger.info(
        f"Server configuration: host={config.host}, port={config.mcp_port}, "
        f"log_level={config.courtlistener_log_level}"
    )

    try:
        await mcp.run_async(
            transport="http",
            host=config.host,
            port=config.mcp_port,
            path="/mcp/",
            log_level=config.courtlistener_log_level.lower(),
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise e


if __name__ == "__main__":
    logger.info("Starting CourtListener ++ MCP server")
    asyncio.run(main())
