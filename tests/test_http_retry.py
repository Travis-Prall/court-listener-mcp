"""Unit tests for the shared HTTP retry helper.

These tests intercept HTTP traffic with respx (the project's HTTP fake)
and verify that ``app.tools.common.request_with_retry`` retries transient
upstream failures - transport errors and the 429/5xx statuses in
``RETRYABLE_STATUS_CODES`` - while returning non-retryable responses
immediately. Backoff delays are zeroed by an autouse conftest fixture, so
the suite runs instantly.
"""

# Pytest assertions are the idiomatic test mechanism in this file.
# ruff: file-ignore[assert, import-private-name]

from typing import TYPE_CHECKING, Any

import httpx
import pytest
import respx

from app.tools.common import (
    RETRY_MAX_ATTEMPTS,
    RETRYABLE_STATUS_CODES,
    _retry_delay,
    request_with_retry,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

URL = "https://example.test/resource"
OK_PAYLOAD: dict[str, Any] = {"ok": True}

# Total request counts after a given number of transient-failure retries.
CALLS_AFTER_ONE_RETRY = 2
CALLS_AFTER_TWO_RETRIES = 3


def _ok() -> httpx.Response:
    """Build a successful JSON response.

    Returns:
        httpx.Response: A 200 response carrying ``OK_PAYLOAD``.

    """
    return httpx.Response(200, json=OK_PAYLOAD)


@pytest.fixture(autouse=True)
def respx_router() -> Iterator[None]:
    """Start the respx router for every test in this module.

    Starting the router lets each test register its routes with the
    module-level ``respx.get``/``respx.post`` shortcuts and have them
    intercepted, matching how the rest of the suite uses ``respx.mock``.

    Yields:
        None: Control while the respx router is active.

    """
    with respx.mock:
        yield


def test_retry_delay_doubles_with_each_attempt() -> None:
    """The exponential backoff doubles per attempt from the base delay."""
    assert _retry_delay(1, backoff_seconds=1.0) == pytest.approx(1.0)
    assert _retry_delay(2, backoff_seconds=1.0) == pytest.approx(2.0)
    assert _retry_delay(3, backoff_seconds=1.0) == pytest.approx(4.0)


def test_retry_delay_honors_numeric_retry_after() -> None:
    """A numeric Retry-After header overrides the computed backoff."""
    response = httpx.Response(429, headers={"Retry-After": "3"})
    assert _retry_delay(1, response, backoff_seconds=1.0) == pytest.approx(3.0)


def test_retry_delay_is_capped() -> None:
    """The backoff delay never exceeds the configured maximum."""
    assert _retry_delay(10, backoff_seconds=1.0, max_delay=8.0) == pytest.approx(8.0)


def test_retry_delay_ignores_non_numeric_retry_after() -> None:
    """An HTTP-date Retry-After falls back to exponential backoff."""
    response = httpx.Response(
        503, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}
    )
    assert _retry_delay(2, response, backoff_seconds=1.0) == pytest.approx(2.0)


@pytest.mark.asyncio
async def test_retries_retryable_status_then_succeeds() -> None:
    """A 502 followed by a 503 then a success returns the last response."""
    route = respx.get(URL).mock(
        side_effect=[
            httpx.Response(httpx.codes.BAD_GATEWAY),
            httpx.Response(httpx.codes.SERVICE_UNAVAILABLE),
            _ok(),
        ]
    )

    response = await request_with_retry("GET", URL, error_label="Test")

    assert response.status_code == httpx.codes.OK
    assert response.json() == OK_PAYLOAD
    assert route.call_count == CALLS_AFTER_TWO_RETRIES


@pytest.mark.asyncio
@pytest.mark.parametrize("status", sorted(RETRYABLE_STATUS_CODES))
async def test_every_retryable_status_is_retried(status: int) -> None:
    """Each documented retryable status triggers a retry.

    Args:
        status: The retryable HTTP status under test.

    """
    route = respx.get(URL).mock(side_effect=[httpx.Response(status), _ok()])

    response = await request_with_retry("GET", URL, error_label="Test")

    assert response.status_code == httpx.codes.OK
    assert route.call_count == CALLS_AFTER_ONE_RETRY


@pytest.mark.asyncio
async def test_gives_up_after_max_attempts() -> None:
    """Persistent retryable failures return the final response."""
    route = respx.get(URL).mock(return_value=httpx.Response(httpx.codes.BAD_GATEWAY))

    response = await request_with_retry("GET", URL, error_label="Test")

    assert response.status_code == httpx.codes.BAD_GATEWAY
    assert route.call_count == RETRY_MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_non_retryable_status_is_not_retried() -> None:
    """A 404 is returned immediately without any retry."""
    route = respx.get(URL).mock(return_value=httpx.Response(httpx.codes.NOT_FOUND))

    response = await request_with_retry("GET", URL, error_label="Test")

    assert response.status_code == httpx.codes.NOT_FOUND
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_retries_transport_error_then_succeeds() -> None:
    """A dropped connection is retried and the success is returned."""
    route = respx.get(URL).mock(side_effect=[httpx.ConnectError("refused"), _ok()])

    response = await request_with_retry("GET", URL, error_label="Test")

    assert response.status_code == httpx.codes.OK
    assert route.call_count == CALLS_AFTER_ONE_RETRY


@pytest.mark.asyncio
async def test_transport_error_exhausts_attempts() -> None:
    """Persistent transport errors are re-raised after every attempt."""
    route = respx.get(URL).mock(side_effect=httpx.ReadTimeout("timed out"))

    with pytest.raises(httpx.TransportError):
        await request_with_retry("GET", URL, error_label="Test")

    assert route.call_count == RETRY_MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_post_body_is_forwarded() -> None:
    """POST requests forward their form-encoded body."""
    route = respx.post(URL).mock(return_value=_ok())

    response = await request_with_retry(
        "POST", URL, data={"text": "123"}, error_label="Test"
    )

    assert response.status_code == httpx.codes.OK
    assert route.calls.last.request.content == b"text=123"
