#!/usr/bin/env python3
"""Test CourtListener API access requirements against the live API.

CourtListener no longer serves anonymous search responses -- requests without
a token return HTTP 401. This test therefore authenticates with
``COURT_LISTENER_API_KEY`` (loaded from ``.env``) and is skipped automatically
when no key is configured, matching the other live-API tests.
"""

# Pytest assertions are the idiomatic test mechanism in this file.
# ruff: file-ignore[assert]

import os

import httpx
from loguru import logger
import pytest

from app.tools.common import SEARCH_URL, auth_headers

COURT_LISTENER_API_KEY = os.getenv("COURT_LISTENER_API_KEY")
OK_STATUS = 200
RATE_LIMITED_STATUS = 429

pytestmark = pytest.mark.skipif(
    not COURT_LISTENER_API_KEY,
    reason="COURT_LISTENER_API_KEY not set; live API access test skipped",
)


@pytest.mark.asyncio
async def test_api_access() -> None:
    """Test that the CourtListener API answers authenticated search requests."""
    logger.info("Testing CourtListener API access...")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            SEARCH_URL,
            params={"q": "Miranda", "type": "o", "hit": 1},
            headers=auth_headers(),
            timeout=30.0,
        )

    logger.info(f"Status: {response.status_code}")
    logger.info(f"Response: {response.text[:200]}...")

    if response.status_code == RATE_LIMITED_STATUS:
        pytest.skip("CourtListener rate limit hit (429); re-run to check access")

    assert response.status_code == OK_STATUS, (
        f"Expected HTTP {OK_STATUS} from the authenticated search API, "
        f"got {response.status_code}"
    )
