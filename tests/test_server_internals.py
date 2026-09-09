"""Tests for server internals: version, docker detection, main(), __main__."""

# Pytest assertions are the idiomatic test mechanism in this file.
# ruff: file-ignore[assert, unused-function-argument, unused-async]

import runpy

import pytest

from app.config import config
import app.server as server_module
from app.server import get_version, is_docker, main


def test_get_version_matches_pyproject() -> None:
    """get_version returns the version declared in pyproject.toml."""
    assert get_version() == "0.2.0"


def test_get_version_handles_read_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """get_version falls back to 'unknown' when pyproject cannot be parsed."""

    def raise_load(*args: object, **kwargs: object) -> None:
        raise OSError("cannot read pyproject.toml")

    monkeypatch.setattr(server_module.tomllib, "load", raise_load)
    assert get_version() == "unknown"


def test_is_docker_returns_bool() -> None:
    """is_docker always returns a boolean."""
    assert isinstance(is_docker(), bool)


async def test_main_uses_configured_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """main() runs HTTP (streamable) with the configured host, port, and level."""
    captured: dict[str, object] = {}

    async def fake_run_async(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(config, "host", "127.0.0.1")
    monkeypatch.setattr(config, "mcp_port", 8786)
    monkeypatch.setattr(config, "courtlistener_log_level", "DEBUG")
    monkeypatch.setattr(server_module.mcp, "run_async", fake_run_async)
    await main()
    assert captured == {
        "transport": "http",
        "host": "127.0.0.1",
        "port": 8786,
        "path": "/mcp/",
        "log_level": "debug",
    }


async def test_main_reraises_startup_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """main() logs and re-raises errors from the server runtime."""

    async def failing_run_async(**kwargs: object) -> None:
        raise RuntimeError("startup failed")

    monkeypatch.setattr(server_module.mcp, "run_async", failing_run_async)
    with pytest.raises(RuntimeError, match="startup failed"):
        await main()


def test_dunder_main_invokes_entrypoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """'python -m app' invokes app.server.main through asyncio.run."""
    calls: list[str] = []

    async def noop() -> None:
        calls.append("main-ran")

    monkeypatch.setattr(server_module, "main", noop)
    module_globals = runpy.run_module("app.__main__", run_name="__main__")
    assert calls == ["main-ran"]
    assert module_globals["__name__"] == "__main__"
