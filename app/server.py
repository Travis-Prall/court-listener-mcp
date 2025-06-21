#!/usr/bin/env python3
"""CourtListener MCP Server - FastMCP Implementation."""

import asyncio
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from loguru import logger

from app.config import config
from app.tools import citation_server, get_server, search_server

# Configure logging
log_path = Path(__file__).parent / "logs" / "server.log"
log_path.parent.mkdir(exist_ok=True)
logger.add(log_path, rotation="1 MB", retention="1 week")

# Create main server instance
mcp: FastMCP[Any] = FastMCP(
    name="CourtListener MCP Server",
    instructions="Model Context Protocol server providing LLMs with access to the CourtListener legal database. "
    "This server enables searching for legal opinions, cases, audio recordings, dockets, and people in the legal system. "
    "It also provides citation lookup, parsing, and validation tools using both the CourtListener API and citeurl library. "
    "Available tools include: search operations for opinions/cases/audio/dockets/people, get operations for specific records by ID, "
    "and comprehensive citation tools for parsing, validating, and looking up legal citations.",
)


@mcp.tool()
def status() -> dict[str, Any]:
    """Check the status of the CourtListener MCP server.

    Returns:
        Dictionary containing server status information including status,
        service name, version, and description.

    """
    logger.info("Status check requested")
    return {
        "status": "online",
        "service": "CourtListener MCP Server",
        "version": "0.1.0",
        "description": "MCP server for accessing CourtListener legal database",
    }


async def setup() -> None:
    """Set up the server by importing subservers."""
    logger.info("Setting up CourtListener MCP server")

    # Import search tools with prefix
    await mcp.import_server("search", search_server)
    logger.info("Imported search server tools")

    # Import get tools with prefix
    await mcp.import_server("get", get_server)
    logger.info("Imported get server tools")

    # Import citation tools with prefix
    await mcp.import_server("citation", citation_server)
    logger.info("Imported citation server tools")

    logger.info("Server setup complete")


# Run setup when module is imported
asyncio.run(setup())


def main() -> None:
    """Run the CourtListener MCP server with streamable-http transport."""
    logger.info("Starting CourtListener MCP server with streamable-http transport")
    logger.info(
        f"Server configuration: host={config.host}, port={config.mcp_port}, log_level={config.courtlistener_log_level}"
    )

    try:
        mcp.run(
            transport="streamable-http",
            host=config.host,
            port=config.mcp_port,
            path="/mcp/",
            log_level=config.courtlistener_log_level.lower(),
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise e


if __name__ == "__main__":
    logger.info("Starting CourtListener MCP server")
    main()
