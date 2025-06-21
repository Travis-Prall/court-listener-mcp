#!/usr/bin/env python3
"""Entry point for running the CourtListener MCP Server.

This allows the server to be run with:
    python -m app
    uv run python -m app
"""

from app.server import main

if __name__ == "__main__":
    main()
