"""pytest configuration for CourtListener MCP tests."""

from pathlib import Path
from typing import Any

from _pytest.config import Config
from fastmcp import Client
from loguru import logger
import pytest

from app.server import ensure_setup, mcp

# Configure test logging
test_log_path = Path(__file__).parent / "test_logs" / "test.log"
test_log_path.parent.mkdir(exist_ok=True)
logger.add(test_log_path, rotation="10 MB", retention="1 week")

# Ensure server tools are set up before any tests run
ensure_setup()


@pytest.fixture
def client() -> Client[Any]:
    """Create a test client connected to the MCP server.

    Returns:
        A FastMCP test client connected to the server instance.

    """
    return Client(mcp)


def pytest_configure(config: Config) -> None:
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
