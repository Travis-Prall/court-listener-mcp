#!/usr/bin/env python3
"""Simple test to check CourtListener API access requirements."""

import httpx
from loguru import logger
import pytest

PUBLIC_SEARCH_URL = "https://www.courtlistener.com/api/rest/v4/search/"
UNAUTHORIZED_STATUS = 401
OK_STATUS = 200


@pytest.mark.asyncio
async def test_api_access() -> None:
    """Test if CourtListener API requires authentication."""
    logger.info("Testing CourtListener API access...")

    async with httpx.AsyncClient() as client:
        # Test without authentication
        response = await client.get(
            PUBLIC_SEARCH_URL,
            params={"q": "Miranda", "type": "o", "hit": 1},
            timeout=30.0,
        )

    logger.info(f"Status: {response.status_code}")
    logger.info(f"Response: {response.text[:200]}...")

    if response.status_code == UNAUTHORIZED_STATUS:
        logger.error("API requires authentication")
        pytest.fail("API requires authentication")
    if response.status_code == OK_STATUS:
        logger.info("API allows public access")
    else:
        logger.warning(f"Unexpected status: {response.status_code}")
        pytest.fail(f"Unexpected status: {response.status_code}")
