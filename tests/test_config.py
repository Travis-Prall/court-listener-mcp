"""pytest configuration for CourtListener MCP tests."""

import asyncio
from pathlib import Path

from _pytest.config import Config
from loguru import logger
import pytest

# Configure test logging
test_log_path = Path(__file__).parent / "test_logs" / "test.log"
test_log_path.parent.mkdir(exist_ok=True)
logger.add(test_log_path, rotation="10 MB", retention="1 week")


@pytest.fixture(scope="session")
def event_loop() -> asyncio.AbstractEventLoop:
    """Create an instance of the default event loop for the test session.

    Yields
    ------
    asyncio.AbstractEventLoop
        The event loop instance for the test session.

    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


def pytest_configure(config: Config) -> None:
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
