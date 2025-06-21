"""Citation lookup tools for CourtListener MCP server.

This module provides FastMCP tools for legal citation lookup, parsing, and validation
using the CourtListener API and citeurl library. It includes tools for single and batch
citation lookup, citation format verification, parsing, extraction from text, and
enhanced lookups combining citeurl and CourtListener data.
"""

from functools import lru_cache
import os
from pathlib import Path
import re
from typing import Annotated, Any

from citeurl import Citator, cite as citeurl_cite, list_cites
from dotenv import load_dotenv
from fastmcp import Context, FastMCP
import httpx
from loguru import logger
from pydantic import Field

# Load environment variables
load_dotenv()

# Get API key from environment
API_KEY = os.getenv("COURT_LISTENER_API_KEY")

# Create the citation server
citation_server: FastMCP[Any] = FastMCP(
    name="CourtListener Citation Server",
    instructions="Citation processing server for legal citation lookup, parsing, validation, and analysis. "
    "This server combines the power of the CourtListener API with the citeurl library to provide comprehensive citation tools. "
    "Available capabilities include: single and batch citation lookup, citation format verification and validation, "
    "citation parsing and normalization, citation extraction from text, and enhanced lookups combining multiple data sources. "
    "Supports various citation formats including U.S. Reporter, Federal Reporter, WestLaw, and state reporter citations. "
    "Use this server for all citation-related tasks including validation, parsing, and data retrieval.",
)


@citation_server.tool()
async def lookup_citation(
    citation: Annotated[
        str,
        Field(
            description="The citation to look up (e.g., '410 U.S. 113', '2023 WL 12345')"
        ),
    ],
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Look up a legal citation to find the opinion it references in CourtListener.

    This tool accepts various citation formats including:
    - U.S. Reporter citations (e.g., "410 U.S. 113")
    - Federal Reporter citations (e.g., "123 F.3d 456")
    - WestLaw citations (e.g., "2023 WL 12345")
    - State reporter citations

    Args:
        citation: The citation string to look up.
        ctx: Optional FastMCP context for logging and error reporting.

    Returns:
        dict[str, Any]: The opinion(s) that match the citation, or an error dict if the lookup fails.

    Raises:
        ValueError: If COURT_LISTENER_API_KEY is not found in environment variables.

    """
    if ctx:
        await ctx.info(f"Looking up citation: {citation}")
    else:
        logger.info(f"Looking up citation: {citation}")

    if not API_KEY:
        error_msg = "COURT_LISTENER_API_KEY not found in environment variables"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise ValueError(error_msg)

    headers = {"Authorization": f"Token {API_KEY}"}

    try:
        async with httpx.AsyncClient() as client:
            # The citation lookup API uses POST with form data
            response = await client.post(
                "https://www.courtlistener.com/api/rest/v4/citation-lookup/",
                headers=headers,
                data={"text": citation},
                timeout=30.0,
            )
            response.raise_for_status()
            result: dict[str, Any] = response.json()

            if ctx:
                await ctx.info(f"Successfully looked up citation: {citation}")
            else:
                logger.info(f"Successfully looked up citation: {citation}")

            return result

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error looking up citation: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e
    except Exception as e:
        error_msg = f"Error looking up citation: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e


@citation_server.tool()
async def batch_lookup_citations(
    citations: Annotated[
        list[str],
        Field(
            description="List of citations to look up (max 100)",
            min_length=1,
            max_length=100,
        ),
    ],
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Look up multiple legal citations in a single request.

    This is more efficient than making individual requests for each citation.
    Accepts up to 100 citations at once.

    Args:
        citations: List of citation strings to look up (max 100).
        ctx: Optional FastMCP context for logging and error reporting.

    Returns:
        dict[str, Any]: A dictionary mapping each citation to its corresponding opinion(s).

    Raises:
        ValueError: If COURT_LISTENER_API_KEY is not found in environment variables.

    """
    if ctx:
        await ctx.info(f"Looking up {len(citations)} citations")
    else:
        logger.info(f"Looking up {len(citations)} citations")

    if not API_KEY:
        error_msg = "COURT_LISTENER_API_KEY not found in environment variables"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise ValueError(error_msg)

    headers = {"Authorization": f"Token {API_KEY}"}

    try:
        async with httpx.AsyncClient() as client:
            # Use POST with form data for the citation text
            # Join all citations into one text block separated by spaces
            citation_text = " ".join(citations)
            response = await client.post(
                "https://www.courtlistener.com/api/rest/v4/citation-lookup/",
                headers=headers,
                data={"text": citation_text},
                timeout=60.0,  # Longer timeout for batch requests
            )
            response.raise_for_status()

            result = response.json()

            if ctx:
                await ctx.info(f"Successfully looked up {len(citations)} citations")
            else:
                logger.info(f"Successfully looked up {len(citations)} citations")

            return result

    except httpx.HTTPStatusError as e:
        error_msg = f"HTTP error in batch citation lookup: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e
    except Exception as e:
        error_msg = f"Error in batch citation lookup: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e


@citation_server.tool()
async def verify_citation_format(
    citation: Annotated[
        str,
        Field(description="The citation to verify"),
    ],
    ctx: Context | None = None,
) -> dict[str, str | bool | list[str] | None]:
    """Verify if a citation string is in a valid format using citeurl's advanced parsing.

    This tool performs validation using citeurl's comprehensive citation templates
    to check if a citation appears to be in a recognized legal citation format.
    This is much more accurate than simple regex matching.

    Returns information about the citation format and any detected issues.

    Args:
        citation: The citation string to verify.
        ctx: Optional FastMCP context for logging.

    Returns:
        dict[str, str | bool | list[str] | None]: A dictionary containing validation results with:
            - valid: Whether the citation is in a valid format
            - format: The recognized citation format type (if valid)
            - template: The citation template matched (if valid)
            - issues: List of any validation issues found
            - citation: The original citation string

    """
    if ctx:
        await ctx.info(f"Verifying citation format: {citation}")
    else:
        logger.info(f"Verifying citation format: {citation}")

    citation_stripped = citation.strip()

    # Check if citation is empty
    if not citation_stripped:
        return {
            "valid": False,
            "format": None,
            "template": None,
            "issues": ["Citation is empty"],
            "citation": citation,
        }

    try:
        citator = get_citator()

        # Try broad matching first
        parsed_broad = citeurl_cite(citation_stripped, broad=True, citator=citator)
        # Try strict matching
        parsed_strict = citeurl_cite(citation_stripped, broad=False, citator=citator)

        if parsed_strict:
            # Citation is valid in strict mode
            result = {
                "valid": True,
                "format": "Recognized legal citation",
                "template": str(parsed_strict.template),
                "matching_mode": "strict",
                "citation": citation,
                "normalized": parsed_strict.text,
                "tokens": parsed_strict.tokens,
                "issues": [],
            }
        elif parsed_broad:
            # Citation is valid only in broad mode
            result = {
                "valid": True,
                "format": "Recognized legal citation (broad matching)",
                "template": str(parsed_broad.template),
                "matching_mode": "broad",
                "citation": citation,
                "normalized": parsed_broad.text,
                "tokens": parsed_broad.tokens,
                "issues": [
                    "Citation recognized only with broad matching - may be informal format"
                ],
            }
        else:
            # Citation not recognized by citeurl
            result = {
                "valid": False,
                "format": None,
                "template": None,
                "matching_mode": None,
                "citation": citation,
                "normalized": citation_stripped,
                "issues": [
                    "Citation does not match any recognized legal citation format in citeurl's templates",
                    "Consider checking the citation format against standard legal citation styles (Bluebook, etc.)",
                ],
            }

    except Exception as e:
        # Fallback to basic validation if citeurl fails
        logger.warning(
            f"citeurl verification failed, falling back to basic patterns: {e}"
        )

        # Basic patterns for fallback
        basic_patterns = {
            "U.S. Reporter": r"^\d+\s+U\.S\.\s+\d+",
            "Federal Reporter": r"^\d+\s+F\.(2d|3d|4th)?\s+\d+",
            "Federal Supplement": r"^\d+\s+F\.\s*Supp\.(2d|3d)?\s+\d+",
            "State Reporter": r"^\d+\s+[A-Z][a-z]+\.(\s*(2d|3d|4th))?\s+\d+",
        }

        matched_format = None
        matched_format = None
        for format_name, pattern in basic_patterns.items():
            if re.match(pattern, citation_stripped, re.IGNORECASE):
                matched_format = format_name
                break

        result = {
            "valid": matched_format is not None,
            "format": matched_format,
            "template": "Basic regex fallback",
            "matching_mode": "fallback",
            "citation": citation,
            "normalized": citation_stripped,
            "issues": ["Verified using basic patterns only - citeurl parsing failed"]
            if matched_format
            else [
                "Citation not recognized by basic patterns",
                "citeurl parsing also failed",
                f"Error: {e}",
            ],
        }

    if ctx:
        await ctx.info(f"Citation format verification complete: {result['valid']}")
    else:
        logger.info(f"Citation format verification complete: {result['valid']}")

    return result


def get_citator() -> Citator:
    """Get or create the citeurl citator instance with custom citation templates.

    Returns:
        Citator: The singleton citeurl Citator instance with custom citation support.

    """
    return _get_citator_singleton()


@lru_cache(maxsize=1)
def _get_citator_singleton() -> Citator:
    """Get or create the citeurl citator instance with custom citation templates.

    Returns:
        Citator: The singleton citeurl Citator instance with custom citation support.

    """
    template_path = Path(__file__).parent / "custom_citation_templates.yaml"
    citator = Citator(yaml_paths=[str(template_path)])
    logger.info(f"Created citator with custom citation templates from {template_path}")
    return citator


@citation_server.tool()
async def parse_citation_with_citeurl(
    citation: Annotated[
        str,
        Field(
            description="The citation to parse (e.g., '410 U.S. 113', '42 USC § 1988')"
        ),
    ],
    broad: Annotated[
        bool,
        Field(description="Use broad matching for more flexible parsing", default=True),
    ] = True,
    ctx: Context | None = None,
) -> dict[str, str | dict | None]:
    """Parse a legal citation using citeurl's advanced citation recognition.

    This tool uses the citeurl library to parse legal citations and extract
    structured information including tokens, normalized format, and URL generation.

    Returns detailed information about the citation including:
    - Recognized citation format and source
    - Extracted tokens (volume, reporter, page, etc.)
    - Generated URL if available
    - Normalized citation text

    Args:
        citation: The citation string to parse.
        broad: Whether to use broad matching for flexible parsing.
        ctx: Optional FastMCP context for logging.

    Returns:
        dict[str, str | dict | None]: A dictionary containing the parsed citation data,
            including success status, original citation, and detailed parsing results.

    """
    if ctx:
        await ctx.info(f"Parsing citation with citeurl: {citation}")
    else:
        logger.info(f"Parsing citation with citeurl: {citation}")

    try:
        citator = get_citator()
        parsed_citation = citeurl_cite(citation, broad=broad, citator=citator)

        if not parsed_citation:
            return {
                "success": False,
                "error": "Citation not recognized by citeurl",
                "citation": citation,
                "suggestion": "Try using a more standard citation format",
            }

        result = {
            "success": True,
            "citation": citation,
            "parsed": {
                "text": parsed_citation.text,
                "tokens": parsed_citation.tokens,
                "template": str(parsed_citation.template),
                "URL": getattr(parsed_citation, "URL", None),
                "canonical_name": getattr(parsed_citation, "name", None),
            },
        }

        if ctx:
            await ctx.info(f"Successfully parsed citation: {parsed_citation.text}")
        else:
            logger.info(f"Successfully parsed citation: {parsed_citation.text}")

        return result

    except Exception as e:
        error_msg = f"Error parsing citation with citeurl: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e


@citation_server.tool()
async def extract_citations_from_text(
    text: Annotated[
        str,
        Field(description="Text containing legal citations to extract"),
    ],
    ctx: Context | None = None,
) -> dict[str, list | int]:
    """Extract all legal citations from a block of text using citeurl.

    This tool finds and parses all legal citations within a given text,
    including both long-form and short-form citations (like 'id.' references).

    Args:
        text: The text containing legal citations to extract.
        ctx: Optional FastMCP context for logging.

    Returns:
        dict[str, list | int]: A dictionary containing:
            - total_citations: Number of citations found
            - citations: List of parsed citation information
            - text_length: Length of the input text
            - error (optional): Error message if extraction failed

    """
    if ctx:
        await ctx.info(f"Extracting citations from text ({len(text)} characters)")
    else:
        logger.info(f"Extracting citations from text ({len(text)} characters)")

    try:
        citator = get_citator()
        citations = list_cites(text, citator=citator)

        parsed_citations = []
        for citation in citations:
            citation_info = {
                "text": citation.text,
                "tokens": citation.tokens,
                "template": str(citation.template),
                "URL": getattr(citation, "URL", None),
                "canonical_name": getattr(citation, "name", None),
            }
            parsed_citations.append(citation_info)

        result = {
            "total_citations": len(citations),
            "citations": parsed_citations,
            "text_length": len(text),
        }

        if ctx:
            await ctx.info(f"Found {len(citations)} citations in text")
        else:
            logger.info(f"Found {len(citations)} citations in text")

        return result

    except Exception as e:
        error_msg = f"Error extracting citations from text: {e}"
        if ctx:
            await ctx.error(error_msg)
        else:
            logger.error(error_msg)
        raise e


@citation_server.tool()
async def enhanced_citation_lookup(
    citation: Annotated[
        str,
        Field(description="The citation to look up and analyze"),
    ],
    include_courtlistener: Annotated[
        bool,
        Field(
            description="Whether to also perform CourtListener API lookup", default=True
        ),
    ] = True,
    ctx: Context | None = None,
) -> dict[str, dict | str | bool]:
    """Enhanced citation lookup combining citeurl parsing with CourtListener data.

    This tool first uses citeurl to parse and validate the citation format,
    then optionally queries the CourtListener API for additional case information.

    Returns:
        dict: Comprehensive citation information from both sources, containing:
            - citation: The original citation string
            - citeurl_analysis: Parsing results from citeurl
            - courtlistener_data: Lookup results from CourtListener API
            - combined_info: Summary of available information from both sources

    Args:
        citation: The citation string to look up and analyze.
        include_courtlistener: Whether to include CourtListener API lookup.
        ctx: Optional FastMCP context for logging.

    Returns:
        dict[str, dict | str | bool]: A dictionary containing the enhanced citation information.

    """
    if ctx:
        await ctx.info(f"Enhanced lookup for citation: {citation}")
    else:
        logger.info(f"Enhanced lookup for citation: {citation}")

    result = {
        "citation": citation,
        "citeurl_analysis": {},
        "courtlistener_data": {},
        "combined_info": {},
    }

    # First, parse with citeurl
    try:
        citator = get_citator()
        parsed = citeurl_cite(citation, broad=True, citator=citator)

        if parsed:
            result["citeurl_analysis"] = {
                "success": True,
                "text": parsed.text,
                "tokens": parsed.tokens,
                "template": str(parsed.template),
                "URL": getattr(parsed, "URL", None),
                "canonical_name": getattr(parsed, "name", None),
            }
        else:
            result["citeurl_analysis"] = {
                "success": False,
                "error": "Citation not recognized by citeurl",
            }
    except Exception as e:
        result["citeurl_analysis"] = {
            "success": False,
            "error": f"citeurl parsing error: {e}",
        }

    # Then, lookup in CourtListener if requested and API key available
    if include_courtlistener and API_KEY:
        try:
            headers = {"Authorization": f"Token {API_KEY}"}
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://www.courtlistener.com/api/rest/v4/citation-lookup/",
                    headers=headers,
                    data={"text": citation},
                    timeout=30.0,
                )
                if response.status_code == 200:
                    result["courtlistener_data"] = {
                        "success": True,
                        "data": response.json(),
                    }
                else:
                    result["courtlistener_data"] = {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}",
                    }
        except Exception as e:
            result["courtlistener_data"] = {
                "success": False,
                "error": f"CourtListener API error: {e}",
            }
    elif not API_KEY:
        result["courtlistener_data"] = {
            "success": False,
            "error": "COURT_LISTENER_API_KEY not found",
        }

    # Combine information
    citeurl_analysis = result.get("citeurl_analysis", {})
    courtlistener_data = result.get("courtlistener_data", {})
    if (
        isinstance(citeurl_analysis, dict)
        and citeurl_analysis.get("success")
        and isinstance(courtlistener_data, dict)
        and courtlistener_data.get("success")
    ):
        result["combined_info"] = {
            "has_both_sources": True,
            "citeurl_url": citeurl_analysis.get("URL"),
            "canonical_citation": citeurl_analysis.get("canonical_name"),
            "tokens": citeurl_analysis.get("tokens"),
            "courtlistener_matches": len(courtlistener_data.get("data", [])),
        }
    else:
        available_sources = []
        if isinstance(citeurl_analysis, dict) and citeurl_analysis.get("success"):
            available_sources.append("citeurl")
        if isinstance(courtlistener_data, dict) and courtlistener_data.get("success"):
            available_sources.append("courtlistener")
        result["combined_info"] = {
            "has_both_sources": False,
            "available_sources": available_sources,
        }

    if ctx:
        await ctx.info(f"Enhanced lookup complete for: {citation}")
    else:
        logger.info(f"Enhanced lookup complete for: {citation}")

    return result
