"""pytest configuration for CourtListener MCP tests."""

# Pytest assertions are the idiomatic test mechanism in this file.
# ruff: file-ignore[assert]

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger
import pytest

from app.config import config, is_debug_enabled, is_development

if TYPE_CHECKING:
    from _pytest.config import Config


def test_is_development(monkeypatch: pytest.MonkeyPatch) -> None:
    """is_development reflects the configured environment."""
    monkeypatch.setattr(config, "environment", "development")
    assert is_development() is True
    monkeypatch.setattr(config, "environment", "production")
    assert is_development() is False


def test_is_debug_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """is_debug_enabled honors the debug flag and DEBUG log level."""
    monkeypatch.setattr(config, "courtlistener_debug", False)
    monkeypatch.setattr(config, "courtlistener_log_level", "INFO")
    assert is_debug_enabled() is False

    monkeypatch.setattr(config, "courtlistener_debug", True)
    assert is_debug_enabled() is True

    monkeypatch.setattr(config, "courtlistener_debug", False)
    monkeypatch.setattr(config, "courtlistener_log_level", "DEBUG")
    assert is_debug_enabled() is True


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
