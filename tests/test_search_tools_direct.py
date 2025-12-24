#!/usr/bin/env python3
"""Test script to validate CourtListener MCP server tools."""

from typing import Any

from dotenv import load_dotenv
from fastmcp import Client
import httpx
import pytest

from app.tools.search import search_server

# Load environment variables
load_dotenv()


@pytest.fixture
def search_client() -> Client[Any]:
    """Create a test client connected to the search server.

    Returns:
        Client: A FastMCP test client connected to the search server.

    """
    return Client(search_server)


# Test if CourtListener API allows public access
@pytest.mark.asyncio
async def test_public_api_access() -> None:
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
                pytest.fail(
                    "❌ API requires authentication - need valid COURT_LISTENER_API_KEY"
                )
            elif response.status_code == 200:
                print("✅ Public API access available")
            else:
                pytest.fail(f"⚠️  API returned status {response.status_code}")
    except Exception as e:
        pytest.fail(f"❌ API test failed: {e}")


@pytest.mark.asyncio
async def test_search_opinions(search_client: Client[Any]) -> None:
    """Test the search opinions functionality directly."""
    print("🔍 Testing search_opinions...")

    async with search_client:
        result = await search_client.call_tool(
            "opinions", {"q": "Miranda", "court": "scotus", "limit": 5}
        )
        assert result.content
        print("✅ search_opinions PASSED")


@pytest.mark.asyncio
async def test_search_dockets(search_client: Client[Any]) -> None:
    """Test the search dockets functionality directly."""
    print("🔍 Testing search_dockets...")

    async with search_client:
        result = await search_client.call_tool(
            "dockets", {"q": "patent", "court": "cafc", "limit": 5}
        )
        assert result.content
        print("✅ search_dockets PASSED")


@pytest.mark.asyncio
async def test_search_dockets_with_documents(search_client: Client[Any]) -> None:
    """Test the search dockets with documents functionality."""
    print("🔍 Testing search_dockets_with_documents...")

    async with search_client:
        result = await search_client.call_tool(
            "dockets_with_documents", {"q": "copyright", "limit": 3}
        )
        assert result.content
        print("✅ search_dockets_with_documents PASSED")


@pytest.mark.asyncio
async def test_search_recap_documents(search_client: Client[Any]) -> None:
    """Test the search RECAP documents functionality."""
    print("🔍 Testing search_recap_documents...")

    async with search_client:
        result = await search_client.call_tool(
            "recap_documents", {"q": "motion", "court": "nysd", "limit": 5}
        )
        assert result.content
        print("✅ search_recap_documents PASSED")


@pytest.mark.asyncio
async def test_search_audio(search_client: Client[Any]) -> None:
    """Test the search audio functionality."""
    print("🔍 Testing search_audio...")

    async with search_client:
        result = await search_client.call_tool(
            "audio", {"q": "argument", "court": "scotus", "limit": 5}
        )
        assert result.content
        print("✅ search_audio PASSED")


@pytest.mark.asyncio
async def test_search_people(search_client: Client[Any]) -> None:
    """Test the search people functionality."""
    print("🔍 Testing search_people...")

    async with search_client:
        result = await search_client.call_tool(
            "people", {"q": "Roberts", "position_type": "jud", "limit": 5}
        )
        assert result.content
        print("✅ search_people PASSED")
