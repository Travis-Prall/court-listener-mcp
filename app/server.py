#!/usr/bin/env python3
"""CourtListener MCP Server - FastMCP Implementation."""

import argparse
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import sys
from typing import Any, Literal

from fastmcp import FastMCP
import httpx
from loguru import logger
import psutil

from app import __version__
from app.config import config
from app.tools import citation_server, get_server, search_server


@dataclass
class AppContext:
    """Application context containing shared resources.

    This context is created during server startup and made available
    to all tools via ctx.request_context.lifespan_context.

    Attributes:
        http_client: Shared httpx async client for making API requests.

    """

    http_client: httpx.AsyncClient


@asynccontextmanager
async def app_lifespan(server: FastMCP[Any]) -> AsyncIterator[AppContext]:
    """Manage application lifecycle and shared resources.

    This context manager initializes shared resources (like the HTTP client)
    on startup and ensures proper cleanup on shutdown.

    Args:
        server: The FastMCP server instance.

    Yields:
        AppContext containing shared resources for tools to use.

    """
    logger.info("Initializing shared HTTP client")
    client = httpx.AsyncClient(
        timeout=config.courtlistener_timeout,
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    )
    try:
        yield AppContext(http_client=client)
    finally:
        logger.info("Closing shared HTTP client")
        await client.aclose()

# Valid transport types
TransportType = Literal["stdio", "http", "sse"]
VALID_TRANSPORTS: list[str] = ["stdio", "http", "sse"]

# Configure logging
log_path = Path(__file__).parent / "logs" / "server.log"
log_path.parent.mkdir(exist_ok=True)
logger.add(log_path, rotation="1 MB", retention="1 week")


def get_version() -> str:
    """Get the package version.

    Returns:
        The version string from package metadata.

    """
    return __version__


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


# Create main server instance with lifespan for shared resources
mcp: FastMCP[Any] = FastMCP(
    name="CourtListener MCP Server",
    instructions="Model Context Protocol server providing LLMs with access to the CourtListener legal database. "
    "This server enables searching for legal opinions, cases, audio recordings, dockets, and people in the legal system. "
    "It also provides citation lookup, parsing, and validation tools using both the CourtListener API and citeurl library. "
    "Available tools include: search operations for opinions/cases/audio/dockets/people, get operations for specific records by ID, "
    "and comprehensive citation tools for parsing, validating, and looking up legal citations.",
    lifespan=app_lifespan,
)


@mcp.tool()
def status() -> dict[str, Any]:
    """Check the status of the CourtListener MCP server.

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

    # Build server info based on transport
    server_info: dict[str, Any] = {
        "tools_available": ["search", "get", "citation"],
        "transport": config.mcp_transport,
        "api_base": "https://www.courtlistener.com/api/rest/v4/",
    }

    # Add network info for HTTP/SSE transports
    if config.mcp_transport in ("http", "sse"):
        server_info["host"] = config.host
        server_info["port"] = config.mcp_port
        server_info["path"] = config.mcp_path

    return {
        "status": "healthy",
        "service": "CourtListener MCP Server",
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
        "server": server_info,
    }


async def setup() -> None:
    """Set up the server by importing subservers."""
    logger.info("Setting up CourtListener MCP server")

    # Import search tools with prefix
    await mcp.import_server(search_server, "search")
    logger.info("Imported search server tools")

    # Import get tools with prefix
    await mcp.import_server(get_server, "get")
    logger.info("Imported get server tools")

    # Import citation tools with prefix
    await mcp.import_server(citation_server, "citation")
    logger.info("Imported citation server tools")

    logger.info("Server setup complete")


# Flag to track if setup has been run
_setup_complete = False


async def ensure_setup_async() -> None:
    """Ensure setup has been run (async version).

    This function can be called from async code to ensure the server
    tools have been imported. It's safe to call multiple times.
    """
    global _setup_complete
    if not _setup_complete:
        await setup()
        _setup_complete = True


def ensure_setup() -> None:
    """Ensure setup has been run (synchronous wrapper for tests).

    This function can be called from synchronous code to ensure the server
    tools have been imported. It's safe to call multiple times.

    Note: This should only be used in test fixtures, not in the main server code.
    The main server should use ensure_setup_async() instead to avoid creating
    multiple event loops.
    """
    global _setup_complete
    if not _setup_complete:
        asyncio.run(setup())
        _setup_complete = True


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments namespace.

    """
    parser = argparse.ArgumentParser(
        description="CourtListener MCP Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Transport options:
  stdio  - Standard I/O transport (default). Best for CLI tools and Claude Desktop.
  http   - Streamable HTTP transport. Network accessible, supports multiple clients.
  sse    - Server-Sent Events transport (legacy). For backward compatibility.

Examples:
  %(prog)s                          # Run with stdio (default)
  %(prog)s --transport http         # Run HTTP server on default port
  %(prog)s -t http -p 9000          # Run HTTP server on port 9000
  %(prog)s -t sse --host 127.0.0.1  # Run SSE server on localhost only

Environment variables:
  MCP_TRANSPORT  - Set default transport (stdio, http, sse)
  MCP_PORT       - Set default port for HTTP/SSE transports
  MCP_PATH       - Set URL path for HTTP/SSE transports (default: /mcp/)
  HOST           - Set host to bind to (default: 0.0.0.0)
        """,
    )
    parser.add_argument(
        "-t",
        "--transport",
        choices=VALID_TRANSPORTS,
        default=None,
        help="Transport protocol (default: from MCP_TRANSPORT env or 'stdio')",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=None,
        help="Port for HTTP/SSE transports (default: from MCP_PORT env or 8000)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="Host to bind to for HTTP/SSE (default: from HOST env or 0.0.0.0)",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="URL path for HTTP/SSE transports (default: from MCP_PATH env or /mcp/)",
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default=None,
        help="Log level (default: from COURTLISTENER_LOG_LEVEL env or 'info')",
    )
    return parser.parse_args()


async def run_server(
    transport: TransportType,
    host: str,
    port: int,
    path: str,
    log_level: str,
) -> None:
    """Run the MCP server with the specified transport.

    Args:
        transport: Transport protocol to use (stdio, http, sse).
        host: Host to bind to (for http/sse).
        port: Port to listen on (for http/sse).
        path: URL path (for http/sse).
        log_level: Logging level.

    """
    if transport == "stdio":
        logger.info("Starting CourtListener MCP server with stdio transport")
        await mcp.run_async(transport="stdio")
    elif transport == "http":
        logger.info("Starting CourtListener MCP server with HTTP transport")
        logger.info(f"Listening on http://{host}:{port}{path}")
        await mcp.run_async(
            transport="http",
            host=host,
            port=port,
            path=path,
            log_level=log_level,
        )
    elif transport == "sse":
        logger.info("Starting CourtListener MCP server with SSE transport (legacy)")
        logger.info(f"Listening on http://{host}:{port}{path}")
        await mcp.run_async(
            transport="sse",
            host=host,
            port=port,
            path=path,
            log_level=log_level,
        )
    else:
        raise ValueError(f"Invalid transport: {transport}. Must be one of {VALID_TRANSPORTS}")


def _is_broken_pipe_error(exc: BaseException) -> bool:
    """Check if an exception is or contains a BrokenPipeError.

    This handles both direct BrokenPipeError and ExceptionGroups containing them.
    """
    if isinstance(exc, BrokenPipeError):
        return True
    if isinstance(exc, ExceptionGroup):
        return any(_is_broken_pipe_error(e) for e in exc.exceptions)
    return False


async def main() -> None:
    """Run the CourtListener MCP server."""
    # Set up tools before parsing args (in case of errors during setup)
    await ensure_setup_async()

    args = parse_args()

    # CLI args override environment/config values
    transport: TransportType = args.transport or config.mcp_transport  # type: ignore[assignment]
    host = args.host or config.host
    port = args.port or config.mcp_port
    path = args.path or config.mcp_path
    log_level = args.log_level or config.courtlistener_log_level.lower()

    # Validate transport
    if transport not in VALID_TRANSPORTS:
        logger.error(f"Invalid transport: {transport}. Must be one of {VALID_TRANSPORTS}")
        sys.exit(1)

    logger.info(f"Server configuration: transport={transport}, log_level={log_level}")
    if transport in ("http", "sse"):
        logger.info(f"Network configuration: host={host}, port={port}, path={path}")

    try:
        await run_server(transport, host, port, path, log_level)
    except BaseException as e:
        # Handle BrokenPipeError gracefully - this is expected when client disconnects
        if _is_broken_pipe_error(e):
            logger.info("Client disconnected (broken pipe)")
            return
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    logger.info("Starting CourtListener MCP server")
    asyncio.run(main())
