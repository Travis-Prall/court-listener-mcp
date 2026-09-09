"""Shared fixtures for CourtListener MCP server tests.

These fixtures patch the API key bindings in every tool module so that
key-required behavior is deterministic in tests regardless of whether the
developer has a real ``COURT_LISTENER_API_KEY`` configured in their
environment.
"""

import pytest

from app.server import API_KEY_TOOL_GROUPS, DISABLED_TOOL_GROUPS, mcp

# Every tool module imports API_KEY at import time, so each module-level
# binding must be patched for key-required branches to be deterministic.
KEYED_MODULES: tuple[str, ...] = (
    "app.tools.common",
    "app.tools.get",
    "app.tools.search",
    "app.tools.citation",
    "app.tools.govinfo",
    "app.tools.regulations",
)

FAKE_API_KEY = "test-api-key-12345"


@pytest.fixture
def api_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """Install a fake CourtListener API key in every tool module.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        str: The fake API key installed across all tool modules.

    """
    for module_name in KEYED_MODULES:
        monkeypatch.setattr(f"{module_name}.API_KEY", FAKE_API_KEY)
    return FAKE_API_KEY


@pytest.fixture
def no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the CourtListener API key to None in every tool module.

    Args:
        monkeypatch: Pytest monkeypatch fixture.

    """
    for module_name in KEYED_MODULES:
        monkeypatch.setattr(f"{module_name}.API_KEY", None)


@pytest.fixture(autouse=True)
def ensure_keyed_tool_groups_enabled() -> None:
    """Keep API-key-gated tool groups enabled during each test.

    The server disables tool groups at import time when the host
    environment lacks API keys. Tests patch keys per test, so the
    groups are re-enabled and the disabled-group registry cleared
    before every test to keep the suite deterministic on machines
    without configured keys.
    """
    DISABLED_TOOL_GROUPS.clear()
    for _, tag, _ in API_KEY_TOOL_GROUPS:
        mcp.enable(tags={tag})
