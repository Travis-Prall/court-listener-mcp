#!/usr/bin/env python3
"""Simple test to check CourtListener API access requirements."""

import httpx
import pytest


@pytest.mark.asyncio
async def test_api_access() -> None:
    """Test if CourtListener API requires authentication."""
    print("🔍 Testing CourtListener API access...")

    try:
        async with httpx.AsyncClient() as client:
            # Test without authentication
            response = await client.get(
                "https://www.courtlistener.com/api/rest/v4/search/",
                params={"q": "Miranda", "type": "o", "hit": 1},
                timeout=30.0,
            )

            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:200]}...")

            if response.status_code == 401:
                print("❌ API requires authentication")
                assert False, "API requires authentication"
            elif response.status_code == 200:
                print("✅ API allows public access")
                assert True
            else:
                print(f"⚠️  Unexpected status: {response.status_code}")
                assert False, f"Unexpected status: {response.status_code}"

    except Exception as e:
        print(f"❌ Error: {e}")
        pytest.fail(f"Error: {e}")
