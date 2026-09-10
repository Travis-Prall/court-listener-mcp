"""Regression tests for container build and runtime hardening.

These tests parse the Dockerfile, docker-compose.yml, and .dockerignore to
guard the guarantees applied by the docker-image-skill hardening pass:
digest-pinned base images, non-root execution, no shell utilities in the
runtime image, no secrets in the build, and Compose-level defense in depth
(capability drops, read-only root filesystem, no-new-privileges, tmpfs,
resource limits, log rotation). They require neither Docker nor network.
"""

# Pytest assertions are the idiomatic test mechanism in this file.
# ruff: file-ignore[assert]

from __future__ import annotations

from pathlib import Path
import re

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE_PATH = REPO_ROOT / "Dockerfile"
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"
DOCKERIGNORE_PATH = REPO_ROOT / ".dockerignore"

_SECRET_ENV_NAMES = (
    "COURT_LISTENER_API_KEY",
    "GOVINFO_API_KEY",
    "REGULATIONS_API_KEY",
)

# The Dockerfile has exactly two stages (builder + runtime), both pinned.
_PINNED_STAGE_COUNT = 2


@pytest.fixture
def dockerfile() -> str:
    """Return the Dockerfile content.

    Returns:
        Raw text of the repository Dockerfile.

    """
    return DOCKERFILE_PATH.read_text(encoding="utf-8")


@pytest.fixture
def compose() -> str:
    """Return the docker-compose.yml content.

    Returns:
        Raw text of the repository docker-compose.yml.

    """
    return COMPOSE_PATH.read_text(encoding="utf-8")


@pytest.fixture
def dockerignore() -> str:
    """Return the .dockerignore content.

    Returns:
        Raw text of the repository .dockerignore.

    """
    return DOCKERIGNORE_PATH.read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    """Strip comment suffixes so comments do not shadow real usage.

    Args:
        text: Raw file text (Dockerfile or YAML).

    Returns:
        Text with everything after the first ``#`` on each line removed.

    """
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def _runtime_stage(dockerfile: str) -> str:
    """Extract the final (runtime) stage of a multi-stage Dockerfile.

    Args:
        dockerfile: Full Dockerfile text.

    Returns:
        The text of the last ``FROM ... AS runtime`` stage.

    """
    stages = re.split(r"(?m)^FROM ", dockerfile)
    return stages[-1]


# ---------------------------------------------------------------------------
# Image-build guarantees (Dockerfile)
# ---------------------------------------------------------------------------


def test_base_images_pinned_to_digest(dockerfile: str) -> None:
    """Both stages must pin python:3.14-slim to an immutable manifest digest."""
    pins = re.findall(r"FROM python:3\.14-slim@sha256:[0-9a-f]{64}", dockerfile)
    assert len(pins) == _PINNED_STAGE_COUNT, (
        "builder and runtime stages must both pin digests"
    )


def test_uv_image_pinned_to_version_and_digest(dockerfile: str) -> None:
    """The uv helper image must be pinned by version tag and digest."""
    assert re.search(
        r"ghcr\.io/astral-sh/uv:\d+\.\d+\.\d+@sha256:[0-9a-f]{64}", dockerfile
    ), "uv image must be pinned with a version tag and digest"


def test_official_syntax_frontend_only(dockerfile: str) -> None:
    """Only the official docker/dockerfile frontend may be used."""
    directives = re.findall(r"(?m)^#\s*syntax=(\S+)", dockerfile)
    assert directives, "Dockerfile must declare the official syntax frontend"
    for directive in directives:
        assert directive.startswith("docker/dockerfile"), (
            f"untrusted BuildKit frontend: {directive}"
        )


def test_runtime_runs_as_fixed_non_root_uid(dockerfile: str) -> None:
    """The runtime stage must switch to a fixed numeric non-root user."""
    runtime = _runtime_stage(dockerfile)
    assert re.search(r"(?m)^USER 10001:10001$", runtime), (
        "runtime stage must set USER 10001:10001"
    )


def test_no_curl_or_wget_installed(dockerfile: str) -> None:
    """curl/wget must not be installed (healthcheck uses Python stdlib)."""
    body = _strip_comments(dockerfile)
    assert not re.search(r"\b(curl|wget)\b", body), (
        "image must not install curl/wget; the healthcheck uses the stdlib"
    )


def test_runtime_stage_has_no_build_toolchain(dockerfile: str) -> None:
    """The runtime stage must not install packages or compilers."""
    runtime = _runtime_stage(dockerfile)
    assert "apt-get" not in runtime, "runtime stage must not run apt-get"
    assert "build-essential" not in runtime
    assert "pip install" not in runtime, "runtime stage must not install with pip"


def test_healthcheck_uses_python_stdlib(dockerfile: str) -> None:
    """A HEALTHCHECK must exist and use urllib, not external binaries."""
    assert re.search(r"(?m)^HEALTHCHECK", dockerfile)
    assert "urllib.request.urlopen" in dockerfile


def test_no_secrets_in_build(dockerfile: str) -> None:
    """API keys must never appear in the Dockerfile."""
    for name in _SECRET_ENV_NAMES:
        assert name not in dockerfile, f"{name} must not be baked into the image"


# ---------------------------------------------------------------------------
# Runtime guarantees (docker-compose.yml)
# ---------------------------------------------------------------------------


def test_compose_blocks_privilege_escalation(compose: str) -> None:
    """Privilege escalation via setuid binaries must be blocked."""
    assert "no-new-privileges:true" in compose


def test_compose_drops_all_capabilities(compose: str) -> None:
    """All Linux capabilities must be dropped."""
    assert "cap_drop:" in compose
    assert re.search(r"(?m)^\s+- ALL\b", compose)


def test_compose_runs_with_read_only_root_filesystem(compose: str) -> None:
    """The root filesystem must be read-only with tmpfs scratch space."""
    assert "read_only: true" in compose
    assert re.search(r"(?m)^\s+- /tmp:", compose)
    assert re.search(r"(?m)^\s+- /src/app/logs:", compose), (
        "app log directory must be tmpfs-backed under read_only"
    )


def test_compose_declares_resource_limits(compose: str) -> None:
    """CPU, memory and PID limits must be declared."""
    assert re.search(r"memory: \d+M", compose)
    assert r"cpus: " in compose
    assert re.search(r"pids: \d+", compose)


def test_compose_configures_log_rotation(compose: str) -> None:
    """json-file log rotation must be configured."""
    assert r"max-size: " in compose
    assert r"max-file: " in compose


def test_compose_healthcheck_matches_image(compose: str) -> None:
    """The Compose healthcheck must match the image (no curl inside it)."""
    body = _strip_comments(compose)
    assert "curl" not in body
    assert "urllib.request.urlopen" in compose


# ---------------------------------------------------------------------------
# Build-context hygiene (.dockerignore)
# ---------------------------------------------------------------------------


def test_dockerignore_excludes_secrets(dockerignore: str) -> None:
    """Environment files and key material must be excluded from the context."""
    for pattern in (".env", ".env.*", "*.key", "*.pem"):
        assert pattern in dockerignore, f".dockerignore must exclude {pattern}"


def test_dockerignore_excludes_vcs_and_local_tooling(dockerignore: str) -> None:
    """VCS metadata and local tooling must be excluded from the context."""
    for pattern in (".git/", ".venv/", "tests/", ".devcontainer/"):
        assert pattern in dockerignore, f".dockerignore must exclude {pattern}"
