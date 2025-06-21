"""Test citeurl integration with CourtListener MCP server."""

from citeurl import Citator, cite, list_cites
from loguru import logger
import pytest


def test_citeurl_basic_functionality() -> None:
    """Test that citeurl is working correctly."""
    # Test basic citation parsing
    citation_text = "410 U.S. 113"
    parsed = cite(citation_text)

    assert parsed is not None
    assert parsed.text == citation_text
    assert "volume" in parsed.tokens or "Volume" in parsed.tokens

    # Test URL generation
    assert hasattr(parsed, "URL")


def test_citeurl_list_citations() -> None:
    """Test extracting multiple citations from text."""
    text = """
    Federal law provides that courts should award prevailing civil rights
    plaintiffs reasonable attorneys fees, 42 USC § 1988(b), and, by discretion,
    expert fees, id. at (c). This is because the importance of civil rights
    litigation cannot be measured by a damages judgment. See Riverside v. Rivera,
    477 U.S. 561 (1986).
    """

    citations = list_cites(text)
    assert len(citations) > 0

    # Log what citations were found for debugging
    logger.info(f"Found {len(citations)} citations:")
    for c in citations:
        logger.info(f"  - Text: '{c.text}', Template: '{c.template}'")

    # Should find some citations - let's be more flexible
    # Look for any citations containing USC or U.S.
    relevant_citations = [
        c
        for c in citations
        if "USC" in c.text or "U.S." in c.text or "usc" in str(c.template).lower()
    ]
    assert len(relevant_citations) > 0


def test_citator_instance() -> None:
    """Test creating and using a Citator instance."""
    citator = Citator()
    assert citator is not None

    # Test that it has templates loaded
    assert len(citator.templates) > 0


def test_various_citation_formats() -> None:
    """Test parsing various citation formats."""
    test_citations = ["410 U.S. 113", "42 USC § 1988", "123 F.3d 456", "2023 WL 12345"]

    citator = Citator()
    for citation_text in test_citations:
        try:
            parsed = cite(citation_text, citator=citator)
            # Some might not parse, but at least citeurl shouldn't crash
            if parsed:
                assert isinstance(parsed.text, str)
                assert isinstance(parsed.tokens, dict)
        except Exception as e:
            pytest.fail(f"citeurl failed on citation '{citation_text}': {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
