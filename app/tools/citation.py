"""Citation tools for CourtListener MCP server.

This module provides FastMCP tools for legal citation lookup, parsing, and
validation using the CourtListener API and the citeurl library. It includes
tools for single and batch citation lookup, citation format verification,
parsing, extraction from text, and enhanced lookups that combine citeurl and
CourtListener data.
"""

from functools import lru_cache
from pathlib import Path
import re
from typing import Annotated, Any

# citeurl does not ship type stubs; mypy treats the package as untyped.
from citeurl import (  # type: ignore[import-untyped]
    Citator,
    cite as citeurl_cite,
    list_cites,
)
from fastmcp import Context, FastMCP
import httpx
from loguru import logger
from pydantic import Field

from app.tools.common import (
    API_KEY,
    BATCH_TIMEOUT,
    CITATION_LOOKUP_URL,
    DEFAULT_TIMEOUT,
    HTTP_OK,
    auth_headers,
    log_error,
    log_info,
)

# Create the citation server
citation_server: FastMCP[Any] = FastMCP(
    name="CourtListener Citation Tools Server",
    instructions=(
        "Citation parsing, validation, and lookup server. This server provides "
        "tools for working with legal citations: parse citation strings into "
        "their components, validate citation format and correctness, look up "
        "citations in the CourtListener database to find matching opinions and "
        "cases, and verify whether a specific citation is valid and can be "
        "formatted."
    ),
)

# Maximum number of citation strings accepted per batch request
MAX_BATCH_CITATIONS = 100

# Regex used as a fallback when the citeurl library cannot parse a citation
_FALLBACK_CITATION_PATTERN = re.compile(
    r"^(?P<volume>\d+)\s+(?P<reporter>[A-Za-z.0-9' ]+?)\s+(?P<page>\d+)"
    r"(?:\s*\(\s*(?P<year>\d{4})\s*\))?$"
)

# Basic patterns used when citeurl format verification fails
_BASIC_CITATION_PATTERNS = {
    "U.S. Reporter": r"^\d+\s+U\.S\.\s+\d+",
    "Federal Reporter": r"^\d+\s+F\.(2d|3d|4th)?\s+\d+",
    "Federal Supplement": r"^\d+\s+F\.\s*Supp\.(2d|3d)?\s+\d+",
    "State Reporter": r"^\d+\s+[A-Z][a-z]+\.(\s*(2d|3d|4th))?\s+\d+",
}


def get_citator() -> Citator:
    """Get or create the citeurl citator instance with custom templates.

    Returns:
        Citator: The singleton citeurl Citator instance with custom citation
        support.

    """
    return _get_citator_singleton()


@lru_cache(maxsize=1)
def _get_citator_singleton() -> Citator:
    """Get or create the citeurl citator instance with custom templates.

    Returns:
        Citator: The singleton citeurl Citator instance loaded with the custom
        citation templates shipped alongside this module.

    """
    template_path = Path(__file__).parent / "custom_citation_templates.yaml"
    citator = Citator(yaml_paths=[str(template_path)])
    logger.info(f"Created citator with custom citation templates from {template_path}")
    return citator


def _parse_with_citator(citation: str) -> dict[str, Any] | None:
    """Parse a citation string using the citeurl library.

    Args:
        citation: The citation string to parse.

    Returns:
        dict[str, Any] | None: Parsed components ('volume', 'reporter',
        'page', 'year') or None when citeurl cannot parse the citation.

    """
    try:
        parsed = citeurl_cite(citation)
    except Exception as e:  # citeurl may raise on malformed input
        logger.debug(f"citeurl failed to parse '{citation}': {e}")
        return None

    if not parsed:
        return None

    result: dict[str, Any] = {"original": citation}
    for key in ("volume", "reporter", "page", "year"):
        if hasattr(parsed, key):
            result[key] = getattr(parsed, key)
    return result


def _parse_with_fallback(citation: str) -> dict[str, Any] | None:
    """Parse a citation string with a regex fallback when citeurl fails.

    Args:
        citation: The citation string to parse.

    Returns:
        dict[str, Any] | None: Parsed components ('volume', 'reporter',
        'page', 'year') or None when the citation does not match.

    """
    match = _FALLBACK_CITATION_PATTERN.match(citation.strip())
    if not match:
        return None

    return {
        "original": citation,
        "volume": match.group("volume"),
        "reporter": match.group("reporter"),
        "page": match.group("page"),
        "year": match.group("year"),
    }


async def _lookup_citations_batch(
    citations: list[str],
    ctx: Context | None,
    request_timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Send a batch of citations to the CourtListener citation-lookup API.

    Args:
        citations: Citation strings to look up.
        ctx: Optional FastMCP context for logging and error reporting.
        request_timeout: Request timeout in seconds.

    Returns:
        dict[str, Any]: The raw response data from the citation-lookup API.

    Raises:
        ValueError: If the CourtListener API key is missing.
        httpx.HTTPStatusError: If the API returns an HTTP error status.

    """
    await log_info(ctx, f"Looking up {len(citations)} citation(s)")

    if not API_KEY:
        error_msg = "COURT_LISTENER_API_KEY not found in environment variables"
        await log_error(ctx, error_msg)
        raise ValueError(error_msg)

    try:
        async with httpx.AsyncClient() as client:
            # The citation lookup API uses POST with form data
            response = await client.post(
                CITATION_LOOKUP_URL,
                data={"text": " ".join(citations)},
                headers=auth_headers(),
                timeout=request_timeout,
            )
            response.raise_for_status()
            data: dict[str, Any] = response.json()
    except httpx.HTTPStatusError as e:
        await log_error(ctx, f"HTTP error looking up citations: {e}")
        raise
    except Exception as e:
        await log_error(ctx, f"Error looking up citations: {e}")
        raise

    await log_info(ctx, f"Successfully looked up {len(citations)} citation(s)")
    return data


def _verify_with_citator(citation: str, citation_stripped: str) -> dict[str, Any]:
    """Verify a citation's format with citeurl strict and broad matching.

    Args:
        citation: The original citation string as provided.
        citation_stripped: The stripped citation string to verify.

    Returns:
        dict[str, Any]: A result dictionary describing the verification
        outcome, including validity, matched template, tokens, and issues.

    """
    citator = get_citator()

    # Try broad matching first, then strict matching
    parsed_broad = citeurl_cite(citation_stripped, broad=True, citator=citator)
    parsed_strict = citeurl_cite(citation_stripped, broad=False, citator=citator)

    if parsed_strict:
        # Citation is valid in strict mode
        return {
            "valid": True,
            "format": "Recognized legal citation",
            "template": str(parsed_strict.template),
            "matching_mode": "strict",
            "citation": citation,
            "normalized": parsed_strict.text,
            "tokens": parsed_strict.tokens,
            "issues": [],
        }

    if parsed_broad:
        # Citation is valid only in broad mode
        return {
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

    # Citation not recognized by citeurl
    return {
        "valid": False,
        "format": None,
        "template": None,
        "matching_mode": None,
        "citation": citation,
        "normalized": citation_stripped,
        "issues": [
            (
                "Citation does not match any recognized legal citation format "
                "in citeurl's templates"
            ),
            (
                "Consider checking the citation format against standard legal "
                "citation styles (Bluebook, etc.)"
            ),
        ],
    }


def _verify_with_basic_patterns(
    citation_stripped: str,
    error: Exception,
) -> dict[str, Any]:
    """Verify a citation with basic regex patterns when citeurl fails.

    Args:
        citation_stripped: The stripped citation string to verify.
        error: The citeurl error that triggered the fallback.

    Returns:
        dict[str, Any]: A result dictionary describing the verification
        outcome using the basic patterns only.

    """
    matched_format: str | None = None
    for format_name, pattern in _BASIC_CITATION_PATTERNS.items():
        if re.match(pattern, citation_stripped, re.IGNORECASE):
            matched_format = format_name
            break

    return {
        "valid": matched_format is not None,
        "format": matched_format,
        "template": "Basic regex fallback",
        "matching_mode": "fallback",
        "citation": citation_stripped,
        "normalized": citation_stripped,
        "issues": ["Verified using basic patterns only - citeurl parsing failed"]
        if matched_format
        else [
            "Citation not recognized by basic patterns",
            "citeurl parsing also failed",
            f"Error: {error}",
        ],
    }


def _citeurl_citation_analysis(citation: str) -> dict[str, Any]:
    """Analyze a citation with citeurl parsing for the enhanced lookup.

    Args:
        citation: The citation string to analyze.

    Returns:
        dict[str, Any]: The citeurl analysis result, including success status
        and parsed citation data when recognition succeeds.

    """
    try:
        parsed = citeurl_cite(citation, broad=True, citator=get_citator())
    except Exception as e:
        return {"success": False, "error": f"citeurl parsing error: {e}"}

    if not parsed:
        return {"success": False, "error": "Citation not recognized by citeurl"}

    return {
        "success": True,
        "text": parsed.text,
        "tokens": parsed.tokens,
        "template": str(parsed.template),
        "URL": getattr(parsed, "URL", None),
        "canonical_name": getattr(parsed, "name", None),
    }


async def _courtlistener_citation_data(citation: str) -> dict[str, Any]:
    """Query CourtListener citation lookup data for the enhanced lookup.

    Args:
        citation: The citation string to look up.

    Returns:
        dict[str, Any]: The CourtListener lookup result, including success
        status and data, or an error description.

    """
    if not API_KEY:
        return {"success": False, "error": "COURT_LISTENER_API_KEY not found"}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                CITATION_LOOKUP_URL,
                data={"text": citation},
                headers=auth_headers(),
                timeout=DEFAULT_TIMEOUT,
            )
    except Exception as e:
        return {"success": False, "error": f"CourtListener API error: {e}"}

    if response.status_code != HTTP_OK:
        return {
            "success": False,
            "error": f"HTTP {response.status_code}: {response.text}",
        }

    return {"success": True, "data": response.json()}


def _combined_citation_info(result: dict[str, Any]) -> dict[str, Any]:
    """Build the combined summary for the enhanced citation lookup.

    Args:
        result: The enhanced lookup result containing the citeurl_analysis and
        courtlistener_data entries.

    Returns:
        dict[str, Any]: The combined summary of information from both sources.

    """
    citeurl_analysis = result.get("citeurl_analysis", {})
    courtlistener_data = result.get("courtlistener_data", {})

    if (
        isinstance(citeurl_analysis, dict)
        and citeurl_analysis.get("success")
        and isinstance(courtlistener_data, dict)
        and courtlistener_data.get("success")
    ):
        return {
            "has_both_sources": True,
            "citeurl_url": citeurl_analysis.get("URL"),
            "canonical_citation": citeurl_analysis.get("canonical_name"),
            "tokens": citeurl_analysis.get("tokens"),
            "courtlistener_matches": len(courtlistener_data.get("data", [])),
        }

    available_sources: list[str] = []
    if isinstance(citeurl_analysis, dict) and citeurl_analysis.get("success"):
        available_sources.append("citeurl")
    if isinstance(courtlistener_data, dict) and courtlistener_data.get("success"):
        available_sources.append("courtlistener")

    return {"has_both_sources": False, "available_sources": available_sources}


@citation_server.tool()
async def get_citations(
    citation: Annotated[
        str,
        Field(
            description=(
                "One or more citations to look up (e.g., 'Bush v. Gore, 531 U.S. 98')"
            )
        ),
    ],
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Look up citation(s) in CourtListener and get detailed information.

    Args:
        citation: One or more citations to look up (e.g., 'Bush v. Gore, 531
            U.S. 98').
        ctx: Optional context for logging and error reporting.

    Returns:
        dict[str, Any]: The lookup results with matching opinions and cases.

    Note:
        Requires the COURT_LISTENER_API_KEY environment variable; missing keys
        raise ValueError through the batch lookup helper.

    """
    citations = [line.strip() for line in citation.split(";") if line.strip()]
    return await _lookup_citations_batch(citations, ctx)


@citation_server.tool()
async def parse_citation(
    citation: Annotated[str, Field(description="The citation string to parse")],
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Parse a legal citation string into its components.

    Args:
        citation: The citation string to parse.
        ctx: Optional context for logging and error reporting.

    Returns:
        dict[str, Any]: The parsed citation components.

    """
    await log_info(ctx, f"Parsing citation: {citation}")

    result = _parse_with_citator(citation)
    if result is not None:
        parser_used = "citeurl"
    else:
        result = _parse_with_fallback(citation)
        parser_used = "fallback regex"

    if result is None:
        await log_error(ctx, f"Could not parse citation: {citation}")
        return {
            "original": citation,
            "success": False,
            "error": "Could not parse citation",
            "parser_used": parser_used,
        }

    await log_info(ctx, f"Successfully parsed citation using {parser_used}")
    return {"success": True, "parser_used": parser_used, **result}


@citation_server.tool()
async def validate_citation(
    citation: Annotated[str, Field(description="The citation string to validate")],
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Validate a legal citation format and structure.

    Args:
        citation: The citation string to validate.
        ctx: Optional context for logging and error reporting.

    Returns:
        dict[str, Any]: Validation results including whether the citation is
        valid.

    """
    await log_info(ctx, f"Validating citation: {citation}")

    parsed = _parse_with_citator(citation)
    if parsed is None:
        parsed = _parse_with_fallback(citation)

    if parsed is None:
        await log_error(ctx, f"Citation validation failed: {citation}")
        return {"valid": False, "citation": citation}

    await log_info(ctx, f"Citation is valid: {citation}")
    return {"valid": True, "citation": citation, "parsed": parsed}


@citation_server.tool()
async def verify_citation_format(
    citation: Annotated[
        str,
        Field(description="The citation to verify"),
    ],
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Verify if a citation string is in a valid format using citeurl parsing.

    This tool performs validation using citeurl's comprehensive citation
    templates to check if a citation appears to be in a recognized legal
    citation format. This is much more accurate than simple regex matching.

    Args:
        citation: The citation string to verify.
        ctx: Optional FastMCP context for logging.

    Returns:
        dict[str, Any]: A dictionary containing validation results with:
            - valid: Whether the citation is in a valid format
            - format: The recognized citation format type (if valid)
            - template: The citation template matched (if valid)
            - matching_mode: The citeurl matching mode used
            - issues: List of any validation issues found
            - citation: The original citation string

    """
    await log_info(ctx, f"Verifying citation format: {citation}")

    citation_stripped = citation.strip()

    if not citation_stripped:
        return {
            "valid": False,
            "format": None,
            "template": None,
            "issues": ["Citation is empty"],
            "citation": citation,
        }

    try:
        result = _verify_with_citator(citation, citation_stripped)
    except Exception as e:
        # Fallback to basic validation if citeurl fails
        logger.warning(
            f"citeurl verification failed, falling back to basic patterns: {e}"
        )
        result = _verify_with_basic_patterns(citation_stripped, e)

    await log_info(ctx, f"Citation format verification complete: {result['valid']}")
    return result


@citation_server.tool()
async def batch_lookup(
    citations: Annotated[
        list[str],
        Field(
            description=(
                f"List of citation strings to look up (max {MAX_BATCH_CITATIONS})"
            )
        ),
    ],
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Look up multiple citations at once in CourtListener.

    Args:
        citations: List of citation strings to look up (max 100).
        ctx: Optional context for logging and error reporting.

    Returns:
        dict[str, Any]: The batch lookup results with all matching opinions
        and cases.

    Raises:
        ValueError: If no citations are provided or the list exceeds the
            maximum batch size, or when the CourtListener API key is missing.

    """
    await log_info(ctx, f"Looking up {len(citations)} citation(s) in batch")

    if not citations:
        error_msg = "No citations provided"
        await log_error(ctx, error_msg)
        raise ValueError(error_msg)

    if len(citations) > MAX_BATCH_CITATIONS:
        error_msg = (
            f"Too many citations ({len(citations)}); max is {MAX_BATCH_CITATIONS}"
        )
        await log_error(ctx, error_msg)
        raise ValueError(error_msg)

    return await _lookup_citations_batch(citations, ctx, request_timeout=BATCH_TIMEOUT)


@citation_server.tool()
async def get_citation_details(
    citation_id: Annotated[str, Field(description="The citation ID to retrieve")],
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Get detailed information about a specific citation by ID.

    Args:
        citation_id: The citation ID to retrieve.
        ctx: Optional context for logging and error reporting.

    Returns:
        dict[str, Any]: The citation details as returned by the CourtListener
        API.

    Note:
        Requires the COURT_LISTENER_API_KEY environment variable; missing keys
        raise ValueError through the batch lookup helper.

    """
    await log_info(ctx, f"Getting citation details for ID: {citation_id}")

    if not API_KEY:
        await log_info(ctx, "Using public API access (no authentication)")

    return await _lookup_citations_batch([citation_id], ctx)


@citation_server.tool()
async def lookup_citation(
    citation: Annotated[
        str,
        Field(
            description=(
                "The citation to look up (e.g., '410 U.S. 113', '2023 WL 12345')"
            )
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
        dict[str, Any]: The opinion(s) that match the citation, or an error
        dict if the lookup fails.

    Raises:
        ValueError: If the COURT_LISTENER_API_KEY is not found in the
            environment variables.

    """
    if not API_KEY:
        error_msg = "COURT_LISTENER_API_KEY not found in environment variables"
        await log_error(ctx, error_msg)
        raise ValueError(error_msg)

    await log_info(ctx, f"Looking up citation: {citation}")
    return await _lookup_citations_batch([citation], ctx)


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
        dict[str, Any]: A dictionary mapping each citation to its corresponding
        opinion(s).

    """
    await log_info(ctx, f"Looking up {len(citations)} citations")
    return await _lookup_citations_batch(citations, ctx, request_timeout=BATCH_TIMEOUT)


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
) -> dict[str, Any]:
    """Parse a legal citation using citeurl's advanced citation recognition.

    This tool uses the citeurl library to parse legal citations and extract
    structured information including tokens, normalized format, and URL
    generation.

    Args:
        citation: The citation string to parse.
        broad: Whether to use broad matching for flexible parsing.
        ctx: Optional FastMCP context for logging.

    Returns:
        dict[str, Any]: A dictionary containing the parsed citation data,
            including success status, original citation, and detailed parsing
            results.

    """
    await log_info(ctx, f"Parsing citation with citeurl: {citation}")

    try:
        parsed_citation = citeurl_cite(citation, broad=broad, citator=get_citator())

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
    except Exception as e:
        error_msg = f"Error parsing citation with citeurl: {e}"
        await log_error(ctx, error_msg)
        raise

    await log_info(ctx, f"Successfully parsed citation: {parsed_citation.text}")
    return result


@citation_server.tool()
async def extract_citations_from_text(
    text: Annotated[
        str,
        Field(description="Text containing legal citations to extract"),
    ],
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Extract all legal citations from a block of text using citeurl.

    This tool finds and parses all legal citations within a given text,
    including both long-form and short-form citations (like 'id.' references).

    Args:
        text: The text containing legal citations to extract.
        ctx: Optional FastMCP context for logging.

    Returns:
        dict[str, Any]: A dictionary containing:
            - total_citations: Number of citations found
            - citations: List of parsed citation information
            - text_length: Length of the input text
            - error (optional): Error message if extraction failed

    """
    await log_info(ctx, f"Extracting citations from text ({len(text)} characters)")

    try:
        citations = list_cites(text, citator=get_citator())

        parsed_citations = [
            {
                "text": citation.text,
                "tokens": citation.tokens,
                "template": str(citation.template),
                "URL": getattr(citation, "URL", None),
                "canonical_name": getattr(citation, "name", None),
            }
            for citation in citations
        ]
    except Exception as e:
        error_msg = f"Error extracting citations from text: {e}"
        await log_error(ctx, error_msg)
        raise

    await log_info(ctx, f"Found {len(citations)} citations in text")
    return {
        "total_citations": len(citations),
        "citations": parsed_citations,
        "text_length": len(text),
    }


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
) -> dict[str, Any]:
    """Enhanced citation lookup combining citeurl parsing with CourtListener data.

    This tool first uses citeurl to parse and validate the citation format,
    then optionally queries the CourtListener API for additional case
    information. The result contains the original citation, the citeurl
    analysis, the CourtListener data, and a combined summary.

    Args:
        citation: The citation string to look up and analyze.
        include_courtlistener: Whether to include CourtListener API lookup.
        ctx: Optional FastMCP context for logging.

    Returns:
        dict[str, Any]: A dictionary containing the enhanced citation
        information.

    """
    await log_info(ctx, f"Enhanced lookup for citation: {citation}")

    result: dict[str, Any] = {
        "citation": citation,
        "citeurl_analysis": _citeurl_citation_analysis(citation),
        "courtlistener_data": {},
        "combined_info": {},
    }

    if include_courtlistener:
        result["courtlistener_data"] = await _courtlistener_citation_data(citation)

    result["combined_info"] = _combined_citation_info(result)
    return result


# Export the server and helpers for mounting and reuse
__all__ = [
    "MAX_BATCH_CITATIONS",
    "batch_lookup",
    "batch_lookup_citations",
    "citation_server",
    "enhanced_citation_lookup",
    "extract_citations_from_text",
    "get_citation_details",
    "get_citations",
    "get_citator",
    "lookup_citation",
    "parse_citation",
    "parse_citation_with_citeurl",
    "validate_citation",
    "verify_citation_format",
]
