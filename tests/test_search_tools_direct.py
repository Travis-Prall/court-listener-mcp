#!/usr/bin/env python3
"""Test script to validate CourtListener MCP server tools."""

import asyncio

from dotenv import load_dotenv
import httpx

# Load environment variables
load_dotenv()


# Test if CourtListener API allows public access
async def test_public_api_access():
    """Test if CourtListener API allows public access."""
    print("🔑 Testing public API access...")

    try:
        async with httpx.AsyncClient() as client:
            # Try a simple search without API key
            response = await client.get(
                "https://www.courtlistener.com/api/rest/v4/search/",
                params={"q": "test", "type": "o", "hit": 1},
                timeout=10.0,
            )
            if response.status_code == 401:
                print(
                    "❌ API requires authentication - need valid COURT_LISTENER_API_KEY"
                )
                return False
            if response.status_code == 200:
                print("✅ Public API access available")
                return True
            print(f"⚠️  API returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API test failed: {e}")
        return False


async def test_search_opinions():
    """Test the search opinions functionality directly."""
    print("🔍 Testing search_opinions...")

    from app.tools.search import search_server

    # Get the actual function from the tool
    opinions_tool = None
    for tool in search_server.get_tools():
        if tool.name == "opinions":
            opinions_tool = tool
            break

    if not opinions_tool:
        print("❌ search_opinions tool not found")
        return False

    try:
        result = await opinions_tool.handler(q="Miranda", court="scotus", limit=5)
        print(f"✅ search_opinions PASSED - Found {result.get('count', 0)} results")
        return True
    except ValueError as e:
        if "COURT_LISTENER_API_KEY" in str(e):
            print(f"❌ search_opinions FAILED - Missing API key: {e}")
            return False
        print(f"❌ search_opinions FAILED - ValueError: {e}")
        return False
    except Exception as e:
        print(f"❌ search_opinions FAILED - Error: {e}")
        return False


async def test_search_dockets():
    """Test the search dockets functionality directly."""
    print("🔍 Testing search_dockets...")

    from app.tools.search import dockets

    try:
        result = await dockets(q="patent", court="cafc", limit=5)
        print(f"✅ search_dockets PASSED - Found {result.get('count', 0)} results")
        return True
    except Exception as e:
        print(f"❌ search_dockets FAILED - Error: {e}")
        return False


async def test_search_dockets_with_documents():
    """Test the search dockets with documents functionality."""
    print("🔍 Testing search_dockets_with_documents...")

    from app.tools.search import dockets_with_documents

    try:
        result = await dockets_with_documents(q="copyright", limit=3)
        print(
            f"✅ search_dockets_with_documents PASSED - Found {result.get('count', 0)} results"
        )
        return True
    except Exception as e:
        print(f"❌ search_dockets_with_documents FAILED - Error: {e}")
        return False


async def test_search_recap_documents():
    """Test the search RECAP documents functionality."""
    print("🔍 Testing search_recap_documents...")

    from app.tools.search import recap_documents

    try:
        result = await recap_documents(q="motion", court="nysd", limit=5)
        print(
            f"✅ search_recap_documents PASSED - Found {result.get('count', 0)} results"
        )
        return True
    except Exception as e:
        print(f"❌ search_recap_documents FAILED - Error: {e}")
        return False


async def test_search_audio():
    """Test the search audio functionality."""
    print("🔍 Testing search_audio...")

    from app.tools.search import audio

    try:
        result = await audio(q="argument", court="scotus", limit=5)
        print(f"✅ search_audio PASSED - Found {result.get('count', 0)} results")
        return True
    except Exception as e:
        print(f"❌ search_audio FAILED - Error: {e}")
        return False


async def test_search_people():
    """Test the search people functionality."""
    print("🔍 Testing search_people...")

    from app.tools.search import people

    try:
        result = await people(q="Roberts", position_type="jud", limit=5)
        print(f"✅ search_people PASSED - Found {result.get('count', 0)} results")
        return True
    except Exception as e:
        print(f"❌ search_people FAILED - Error: {e}")
        return False


async def main():
    """Run all search tool tests."""
    print("🚀 Starting CourtListener MCP Server Tool Tests")
    print("=" * 60)

    # Test search tools in order
    test_results = []

    test_results.append(await test_search_opinions())
    test_results.append(await test_search_dockets())
    test_results.append(await test_search_dockets_with_documents())
    test_results.append(await test_search_recap_documents())
    test_results.append(await test_search_audio())
    test_results.append(await test_search_people())

    print("=" * 60)
    passed = sum(test_results)
    total = len(test_results)
    print(f"📊 Results: {passed}/{total} tests passed")

    if passed != total:
        print("⚠️  Some tests failed - need to investigate and fix issues")
        return False
    print("🎉 All search tools tests passed!")
    return True


if __name__ == "__main__":
    asyncio.run(main())
