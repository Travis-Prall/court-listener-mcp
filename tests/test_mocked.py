"""Mocked unit tests for CourtListener MCP server.

These tests use respx to mock HTTP responses, avoiding real API calls.
This enables testing error paths and edge cases reliably.
"""

from typing import Any

from fastmcp import Client
from fastmcp.exceptions import ToolError
import httpx
import pytest
import respx


# Sample mock responses
MOCK_OPINIONS_RESPONSE = {
    "count": 2,
    "next": None,
    "previous": None,
    "results": [
        {
            "id": 123456,
            "caseName": "Smith v. Jones",
            "court": "scotus",
            "dateFiled": "2023-06-15",
            "citation": ["123 U.S. 456"],
            "absolute_url": "/opinion/123456/smith-v-jones/",
        },
        {
            "id": 789012,
            "caseName": "Doe v. Roe",
            "court": "scotus",
            "dateFiled": "2023-05-20",
            "citation": ["124 U.S. 789"],
            "absolute_url": "/opinion/789012/doe-v-roe/",
        },
    ],
}

MOCK_DOCKETS_RESPONSE = {
    "count": 1,
    "next": None,
    "previous": None,
    "results": [
        {
            "id": 111222,
            "case_name": "Patent Corp v. Tech Inc",
            "court": "cafc",
            "date_filed": "2023-07-01",
            "docket_number": "23-1234",
        },
    ],
}

MOCK_COURT_RESPONSE = {
    "id": "scotus",
    "full_name": "Supreme Court of the United States",
    "short_name": "SCOTUS",
    "url": "https://www.supremecourt.gov/",
    "in_use": True,
}

MOCK_OPINION_RESPONSE = {
    "id": 123456,
    "absolute_url": "/opinion/123456/smith-v-jones/",
    "cluster": "https://www.courtlistener.com/api/rest/v4/clusters/123/",
    "author": None,
    "plain_text": "This is the opinion text...",
    "html": "<p>This is the opinion text...</p>",
}

MOCK_CITATION_LOOKUP_RESPONSE = [
    {
        "id": 123456,
        "case_name": "Miranda v. Arizona",
        "absolute_url": "/opinion/123456/miranda-v-arizona/",
        "citation": "384 U.S. 436",
    }
]


class TestMockedSearchTools:
    """Tests for search tools with mocked HTTP responses."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_opinions_success(self, client: Client[Any]) -> None:
        """Test successful opinion search with mocked response."""
        respx.get("https://www.courtlistener.com/api/rest/v4/search/").mock(
            return_value=httpx.Response(200, json=MOCK_OPINIONS_RESPONSE)
        )

        async with client:
            result = await client.call_tool(
                "search_opinions", {"q": "miranda", "court": "scotus", "limit": 5}
            )

            assert not result.is_error
            data = result.data
            assert data["count"] == 2
            assert len(data["results"]) == 2
            assert data["results"][0]["caseName"] == "Smith v. Jones"

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_dockets_success(self, client: Client[Any]) -> None:
        """Test successful docket search with mocked response."""
        respx.get("https://www.courtlistener.com/api/rest/v4/search/").mock(
            return_value=httpx.Response(200, json=MOCK_DOCKETS_RESPONSE)
        )

        async with client:
            result = await client.call_tool(
                "search_dockets", {"q": "patent", "limit": 10}
            )

            assert not result.is_error
            data = result.data
            assert data["count"] == 1
            assert data["results"][0]["case_name"] == "Patent Corp v. Tech Inc"

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_empty_results(self, client: Client[Any]) -> None:
        """Test search returning no results."""
        empty_response: dict[str, Any] = {"count": 0, "next": None, "previous": None, "results": []}
        respx.get("https://www.courtlistener.com/api/rest/v4/search/").mock(
            return_value=httpx.Response(200, json=empty_response)
        )

        async with client:
            result = await client.call_tool(
                "search_opinions", {"q": "xyznonexistent123", "limit": 5}
            )

            assert not result.is_error
            data = result.data
            assert data["count"] == 0
            assert len(data["results"]) == 0


class TestMockedGetTools:
    """Tests for get tools with mocked HTTP responses."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_court_success(self, client: Client[Any]) -> None:
        """Test successful court retrieval with mocked response."""
        respx.get("https://www.courtlistener.com/api/rest/v4/courts/scotus/").mock(
            return_value=httpx.Response(200, json=MOCK_COURT_RESPONSE)
        )

        async with client:
            result = await client.call_tool("get_court", {"court_id": "scotus"})

            assert not result.is_error
            data = result.data
            assert data["id"] == "scotus"
            assert data["full_name"] == "Supreme Court of the United States"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_opinion_success(self, client: Client[Any]) -> None:
        """Test successful opinion retrieval with mocked response."""
        respx.get("https://www.courtlistener.com/api/rest/v4/opinions/123456/").mock(
            return_value=httpx.Response(200, json=MOCK_OPINION_RESPONSE)
        )

        async with client:
            result = await client.call_tool("get_opinion", {"opinion_id": "123456"})

            assert not result.is_error
            data = result.data
            assert data["id"] == 123456
            assert "plain_text" in data


class TestErrorHandling:
    """Tests for HTTP error handling."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_401_unauthorized(self, client: Client[Any]) -> None:
        """Test handling of 401 Unauthorized response."""
        respx.get("https://www.courtlistener.com/api/rest/v4/courts/scotus/").mock(
            return_value=httpx.Response(
                401, json={"detail": "Authentication credentials were not provided."}
            )
        )

        async with client:
            with pytest.raises(ToolError):
                await client.call_tool("get_court", {"court_id": "scotus"})

    @pytest.mark.asyncio
    @respx.mock
    async def test_403_forbidden(self, client: Client[Any]) -> None:
        """Test handling of 403 Forbidden response."""
        respx.get("https://www.courtlistener.com/api/rest/v4/opinions/123/").mock(
            return_value=httpx.Response(
                403, json={"detail": "You do not have permission to perform this action."}
            )
        )

        async with client:
            with pytest.raises(ToolError):
                await client.call_tool("get_opinion", {"opinion_id": "123"})

    @pytest.mark.asyncio
    @respx.mock
    async def test_404_not_found(self, client: Client[Any]) -> None:
        """Test handling of 404 Not Found response."""
        respx.get("https://www.courtlistener.com/api/rest/v4/opinions/999999999/").mock(
            return_value=httpx.Response(404, json={"detail": "Not found."})
        )

        async with client:
            with pytest.raises(ToolError):
                await client.call_tool("get_opinion", {"opinion_id": "999999999"})

    @pytest.mark.asyncio
    @respx.mock
    async def test_429_rate_limited(self, client: Client[Any]) -> None:
        """Test handling of 429 Too Many Requests response."""
        respx.get("https://www.courtlistener.com/api/rest/v4/search/").mock(
            return_value=httpx.Response(
                429,
                json={"detail": "Request was throttled. Expected available in 60 seconds."},
                headers={"Retry-After": "60"},
            )
        )

        async with client:
            with pytest.raises(ToolError):
                await client.call_tool("search_opinions", {"q": "test"})

    @pytest.mark.asyncio
    @respx.mock
    async def test_500_server_error(self, client: Client[Any]) -> None:
        """Test handling of 500 Internal Server Error response."""
        respx.get("https://www.courtlistener.com/api/rest/v4/search/").mock(
            return_value=httpx.Response(500, json={"detail": "Internal server error."})
        )

        async with client:
            with pytest.raises(ToolError):
                await client.call_tool("search_dockets", {"q": "test"})

    @pytest.mark.asyncio
    @respx.mock
    async def test_timeout_error(self, client: Client[Any]) -> None:
        """Test handling of request timeout."""
        respx.get("https://www.courtlistener.com/api/rest/v4/search/").mock(
            side_effect=httpx.TimeoutException("Connection timed out")
        )

        async with client:
            with pytest.raises(ToolError):
                await client.call_tool("search_opinions", {"q": "test"})

    @pytest.mark.asyncio
    @respx.mock
    async def test_connection_error(self, client: Client[Any]) -> None:
        """Test handling of connection error."""
        respx.get("https://www.courtlistener.com/api/rest/v4/search/").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        async with client:
            with pytest.raises(ToolError):
                await client.call_tool("search_opinions", {"q": "test"})


class TestMockedCitationTools:
    """Tests for citation tools with mocked HTTP responses."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_lookup_citation_success(self, client: Client[Any]) -> None:
        """Test successful citation lookup with mocked response."""
        respx.post("https://www.courtlistener.com/api/rest/v4/citation-lookup/").mock(
            return_value=httpx.Response(200, json=MOCK_CITATION_LOOKUP_RESPONSE)
        )

        async with client:
            result = await client.call_tool(
                "citation_lookup_citation", {"citation": "384 U.S. 436"}
            )

            assert not result.is_error
            data = result.data
            assert data["count"] == 1
            assert data["results"][0]["case_name"] == "Miranda v. Arizona"

    @pytest.mark.asyncio
    @respx.mock
    async def test_batch_lookup_citations_success(self, client: Client[Any]) -> None:
        """Test successful batch citation lookup with mocked response."""
        batch_response = [
            {"id": 1, "case_name": "Case One", "citation": "100 U.S. 1"},
            {"id": 2, "case_name": "Case Two", "citation": "200 U.S. 2"},
        ]
        respx.post("https://www.courtlistener.com/api/rest/v4/citation-lookup/").mock(
            return_value=httpx.Response(200, json=batch_response)
        )

        async with client:
            result = await client.call_tool(
                "citation_batch_lookup_citations",
                {"citations": ["100 U.S. 1", "200 U.S. 2"]},
            )

            assert not result.is_error
            data = result.data
            assert data["count"] == 2

    @pytest.mark.asyncio
    async def test_verify_citation_format_valid(self, client: Client[Any]) -> None:
        """Test citation format verification with valid citation."""
        async with client:
            result = await client.call_tool(
                "citation_verify_citation_format", {"citation": "410 U.S. 113"}
            )

            assert not result.is_error
            data = result.data
            assert data["valid"] is True
            assert data["citation"] == "410 U.S. 113"

    @pytest.mark.asyncio
    async def test_verify_citation_format_invalid(self, client: Client[Any]) -> None:
        """Test citation format verification with invalid citation."""
        async with client:
            result = await client.call_tool(
                "citation_verify_citation_format", {"citation": "not a real citation xyz"}
            )

            assert not result.is_error
            data = result.data
            assert data["valid"] is False
            assert len(data["issues"]) > 0

    @pytest.mark.asyncio
    async def test_verify_citation_format_empty(self, client: Client[Any]) -> None:
        """Test citation format verification with empty citation."""
        async with client:
            result = await client.call_tool(
                "citation_verify_citation_format", {"citation": "   "}
            )

            assert not result.is_error
            data = result.data
            assert data["valid"] is False
            assert "Citation is empty" in data["issues"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_enhanced_citation_lookup_success(self, client: Client[Any]) -> None:
        """Test enhanced citation lookup combining citeurl and CourtListener."""
        respx.post("https://www.courtlistener.com/api/rest/v4/citation-lookup/").mock(
            return_value=httpx.Response(200, json=MOCK_CITATION_LOOKUP_RESPONSE)
        )

        async with client:
            result = await client.call_tool(
                "citation_enhanced_citation_lookup",
                {"citation": "384 U.S. 436", "include_courtlistener": True},
            )

            assert not result.is_error
            data = result.data
            assert data["citation"] == "384 U.S. 436"
            assert "citeurl_analysis" in data
            assert "courtlistener_data" in data
            assert "combined_info" in data

    @pytest.mark.asyncio
    async def test_enhanced_citation_lookup_citeurl_only(
        self, client: Client[Any]
    ) -> None:
        """Test enhanced citation lookup with citeurl only (no API call)."""
        async with client:
            result = await client.call_tool(
                "citation_enhanced_citation_lookup",
                {"citation": "410 U.S. 113", "include_courtlistener": False},
            )

            assert not result.is_error
            data = result.data
            assert data["citeurl_analysis"]["success"] is True
            # CourtListener data should be empty when not requested
            assert data["courtlistener_data"] == {}


class TestSearchFilters:
    """Tests for search tool filter parameters with mocked responses."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_with_all_opinion_filters(self, client: Client[Any]) -> None:
        """Test opinion search with all available filters."""
        respx.get("https://www.courtlistener.com/api/rest/v4/search/").mock(
            return_value=httpx.Response(200, json=MOCK_OPINIONS_RESPONSE)
        )

        async with client:
            result = await client.call_tool(
                "search_opinions",
                {
                    "q": "constitutional",
                    "court": "scotus",
                    "case_name": "test",
                    "judge": "Roberts",
                    "filed_after": "2020-01-01",
                    "filed_before": "2023-12-31",
                    "cited_gt": 10,
                    "cited_lt": 1000,
                    "order_by": "dateFiled desc",
                    "limit": 25,
                },
            )

            assert not result.is_error

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_recap_documents(self, client: Client[Any]) -> None:
        """Test RECAP document search with mocked response."""
        recap_response = {
            "count": 1,
            "results": [
                {
                    "id": 555,
                    "description": "Motion to dismiss",
                    "document_number": "5",
                    "attachment_number": None,
                }
            ],
        }
        respx.get("https://www.courtlistener.com/api/rest/v4/search/").mock(
            return_value=httpx.Response(200, json=recap_response)
        )

        async with client:
            result = await client.call_tool(
                "search_recap_documents",
                {"q": "motion to dismiss", "court": "dcd", "limit": 10},
            )

            assert not result.is_error
            data = result.data
            assert data["count"] == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_audio(self, client: Client[Any]) -> None:
        """Test audio search with mocked response."""
        audio_response = {
            "count": 1,
            "results": [
                {
                    "id": 777,
                    "case_name": "Test Oral Argument",
                    "date_argued": "2023-05-01",
                    "duration": 3600,
                }
            ],
        }
        respx.get("https://www.courtlistener.com/api/rest/v4/search/").mock(
            return_value=httpx.Response(200, json=audio_response)
        )

        async with client:
            result = await client.call_tool(
                "search_audio",
                {"q": "oral argument", "court": "scotus", "limit": 5},
            )

            assert not result.is_error

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_people(self, client: Client[Any]) -> None:
        """Test people search with mocked response."""
        people_response = {
            "count": 1,
            "results": [
                {
                    "id": 999,
                    "name_first": "John",
                    "name_last": "Roberts",
                    "position_type": "jud",
                }
            ],
        }
        respx.get("https://www.courtlistener.com/api/rest/v4/search/").mock(
            return_value=httpx.Response(200, json=people_response)
        )

        async with client:
            result = await client.call_tool(
                "search_people",
                {"q": "Roberts", "position_type": "jud", "limit": 5},
            )

            assert not result.is_error


class TestGetTools:
    """Additional tests for get tools with mocked responses."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_docket(self, client: Client[Any]) -> None:
        """Test docket retrieval with mocked response."""
        docket_response = {
            "id": 12345,
            "case_name": "Test Case",
            "docket_number": "1:23-cv-00001",
            "court": "https://www.courtlistener.com/api/rest/v4/courts/dcd/",
        }
        respx.get("https://www.courtlistener.com/api/rest/v4/dockets/12345/").mock(
            return_value=httpx.Response(200, json=docket_response)
        )

        async with client:
            result = await client.call_tool("get_docket", {"docket_id": "12345"})

            assert not result.is_error
            data = result.data
            assert data["id"] == 12345
            assert data["case_name"] == "Test Case"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_audio(self, client: Client[Any]) -> None:
        """Test audio retrieval with mocked response."""
        audio_response = {
            "id": 67890,
            "case_name": "Oral Argument Recording",
            "date_argued": "2023-10-01",
            "download_url": "https://example.com/audio.mp3",
        }
        respx.get("https://www.courtlistener.com/api/rest/v4/audio/67890/").mock(
            return_value=httpx.Response(200, json=audio_response)
        )

        async with client:
            result = await client.call_tool("get_audio", {"audio_id": "67890"})

            assert not result.is_error
            data = result.data
            assert data["id"] == 67890

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_cluster(self, client: Client[Any]) -> None:
        """Test cluster retrieval with mocked response."""
        cluster_response = {
            "id": 11111,
            "case_name": "Smith v. Jones",
            "date_filed": "2023-06-15",
            "citations": [{"volume": 123, "reporter": "U.S.", "page": 456}],
        }
        respx.get("https://www.courtlistener.com/api/rest/v4/clusters/11111/").mock(
            return_value=httpx.Response(200, json=cluster_response)
        )

        async with client:
            result = await client.call_tool("get_cluster", {"cluster_id": "11111"})

            assert not result.is_error
            data = result.data
            assert data["id"] == 11111

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_person(self, client: Client[Any]) -> None:
        """Test person retrieval with mocked response."""
        person_response = {
            "id": 22222,
            "name_first": "Ruth",
            "name_last": "Ginsburg",
            "date_dob": "1933-03-15",
            "positions": [],
        }
        respx.get("https://www.courtlistener.com/api/rest/v4/people/22222/").mock(
            return_value=httpx.Response(200, json=person_response)
        )

        async with client:
            result = await client.call_tool("get_person", {"person_id": "22222"})

            assert not result.is_error
            data = result.data
            assert data["id"] == 22222
            assert data["name_last"] == "Ginsburg"
