#!/usr/bin/env python3
"""Simple test to check CourtListener API access requirements."""

import asyncio

import httpx


async def test_api_access():
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
                return False
            if response.status_code == 200:
                print("✅ API allows public access")
                return True
            print(f"⚠️  Unexpected status: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    asyncio.run(test_api_access())
