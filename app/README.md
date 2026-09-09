# CourtListener MCP Server v2.0

A comprehensive Model Context Protocol (MCP) server for accessing the CourtListener API v4, the GovInfo statute collections, and the Regulations.gov federal rulemaking database, providing powerful legal, statutory, and regulatory research capabilities optimized for Large Language Model (LLM) interactions.

> **Latest Update (June 2025):** All MCP tools and modules are documented. Pydantic v2 compatibility, type annotations, and import structure are up-to-date. Server passes all lint checks and includes a comprehensive test suite.

## Code Architecture Overview

- **`app/server.py`**: Main FastMCP server, imports all tool modules and sets up logging
- **`app/tools/`**: Contains all MCP tool implementations:
  - `search.py`: Search tools (opinions, dockets, audio, people, RECAP, regulations)
  - `get.py`: Get tools (opinion, docket, audio, court, person, cluster)
  - `citation.py`: Citation lookup, parsing, batch, and enhanced tools
  - `govinfo.py`: GovInfo statute search and lookup tools (USC, Statutes at Large, PLAW, COMPS)
  - `regulations.py`: Regulations.gov federal rulemaking tools (documents, comments, agencies)
- **`app/models.py`**: Pydantic models for data validation
- **`app/config.py`**: Configuration and environment variable management
- **`app/utils.py``: Utility functions (XML/JSON conversion, etc.)
- **`app/logs/`**: Server logs

## Server Transport

The server is configured to use the **HTTP** (streamable) transport by default, making it accessible via HTTP at `http://localhost:8000/mcp/`. This allows:

- **HTTP-based access**: Standard HTTP requests for web-based deployments
- **External connections**: Server binds to `0.0.0.0` for network accessibility
- **RESTful interface**: Modern HTTP transport for better integration
- **Production ready**: Suitable for containerized and cloud deployments
- **Health endpoint**: Unauthenticated `GET /health` liveness probe (returns status, version, and timestamp) for load balancers, Docker `HEALTHCHECK`, and Kubernetes probes

To connect to the server programmatically:

```python
from fastmcp import Client

async with Client("http://localhost:8000/mcp/") as client:
    result = await client.call_tool("status")
```

## Modules and Purposes

- **server.py**: FastMCP entrypoint, imports all tool servers
- **tools/search.py**: Implements search tools for opinions, dockets, audio, people, RECAP, regulations
- **tools/get.py**: Implements get tools for detailed entity retrieval (opinion, docket, audio, court, person, cluster)
- **tools/citation.py**: Implements citation lookup, parsing, batch, and enhanced tools
- **tools/govinfo.py**: Implements GovInfo statute search and lookup tools (USCODE, STATUTE, PLAW, COMPS collections)
- **tools/regulations.py**: Implements Regulations.gov tools (document search/retrieval, public comments, agency data)
- **models.py**: Pydantic models for API responses and validation
- **config.py**: Loads environment and configures logging
- **utils.py**: XML/JSON conversion, helpers

## MCP Tools and Parameters

Every key-required tool is tagged (`requires-courtlistener-key`, `requires-govinfo-key`, or `requires-regulations-key`). At startup the server checks `COURT_LISTENER_API_KEY`, `GOVINFO_API_KEY`, and `REGULATIONS_API_KEY`: any group whose key is missing is disabled automatically, logged as a warning, and hidden from clients (the `status` tool reports this under `tools_disabled`). Set the key and restart to re-enable the group.

Long-running tools (`citation_batch_lookup`, `citation_batch_lookup_citations`, `statutes_get_statute_content`) are additionally marked `task=True` for the MCP background tasks extension, so task-capable clients can execute them in the background.

| Tool Name                    | Parameters (all optional unless noted)                                                                 | Description                                      |
|------------------------------|------------------------------------------------------------------------------------------------------|--------------------------------------------------|
| search_opinions              | q (required), court, case_name, judge, filed_after, filed_before, cited_gt, cited_lt, order_by, limit | Search legal opinions                            |
| search_dockets               | q (required), court, case_name, docket_number, date_filed_after, date_filed_before, party_name, order_by, limit | Search court dockets                             |
| search_dockets_with_documents| q (required), court, case_name, docket_number, date_filed_after, date_filed_before, party_name, order_by, limit | Search dockets with nested documents             |
| search_recap_documents       | q (required), court, case_name, docket_number, document_number, attachment_number, filed_after, filed_before, party_name, order_by, limit | Search RECAP filing documents                    |
| search_audio                 | q (required), court, case_name, judge, argued_after, argued_before, order_by, limit                  | Search oral argument audio                       |
| search_people                | q (required), name, position_type, political_affiliation, school, appointed_by, selection_method, order_by, limit | Search judges and legal professionals            |
| get_opinion                  | opinion_id (required)                                                                                 | Get detailed opinion information                 |
| get_docket                   | docket_id (required)                                                                                  | Get detailed docket information                  |
| get_audio                    | audio_id (required)                                                                                   | Get oral argument audio information              |
| get_court                    | court_id (required)                                                                                   | Get detailed court information                   |
| get_person                   | person_id (required)                                                                                  | Get detailed person/judge information            |
| get_cluster                  | cluster_id (required)                                                                                 | Get opinion cluster information                  |
| citation_lookup_citation     | citation (required) — API key required                 | Find the opinion a citation references            |
| citation_batch_lookup_citations | citations (list, required) — API key required       | Look up multiple citations in one request         |
| citation_batch_lookup        | citations (list, required) — API key required          | Batch citation lookup with details                |
| citation_get_citations       | citation (required) — API key required                 | Look up citations found in a text block           |
| citation_get_citation_details | citation_id (required) — API key required             | Detailed information for a citation ID            |
| citation_enhanced_citation_lookup | citation (required), include_courtlistener (bool) | Enhanced lookup with citeurl & CourtListener data |
| citation_parse_citation      | citation (required)                                    | Parse a citation into its components              |
| citation_validate_citation   | citation (required)                                    | Validate citation format and structure            |
| citation_verify_citation_format | citation (required)                                 | Verify citation format via citeurl                |
| citation_parse_citation_with_citeurl | citation (required), broad (bool)              | Parse citations with citeurl recognition          |
| citation_extract_citations_from_text | text (required)                                | Extract all citations from a block of text        |
| statutes_search_statutes     | query (required), collection, congress, title_number, section, start_date, end_date, page_size, offset_mark — API key required | Search US statute collections                     |
| statutes_get_uscode_title    | title_number (required), edition, chapter, section, page_size, offset_mark — API key required | Find USC sections within a title                  |
| statutes_get_public_laws_by_congress | congress (required), law_type, law_number, start_date, end_date, page_size, offset_mark — API key required | Look up public/private laws by Congress           |
| statutes_get_statutes_at_large | volume (required), page, congress, page_size, offset_mark — API key required | Search Statutes at Large by volume                |
| statutes_get_statute_content | package_id (required), content_type, granule_id — API key required | Get statute package summary or download links     |
| statutes_list_statute_collections | none — no API call                                     | List statute collections with descriptions        |
| regulations_search_documents     | query (required), filter_agency, filter_posted_date, filter_document_type, sort, page_size (5-250), page — API key required | Search federal rulemaking documents             |
| regulations_get_document         | document_id (required), include_attachments — API key required | Get detailed regulation document information      |
| regulations_search_comments      | document_id (required), page_size (5-250), page — API key required | List public comments filed on a document         |
| regulations_get_comment          | comment_id (required) — API key required               | Get detailed public comment information           |
| regulations_get_agencies         | none (live endpoint rejects pagination) — API key required | List federal agencies on Regulations.gov         |
| regulations_get_agency           | agency_id (required) — API key required                | Get detailed federal agency information          |

## Usage Examples

### Search Legal Opinions

```python
search_opinions(q="Miranda rights", court="scotus", limit=5)
```

### Get Specific Opinion Details

```python
get_opinion(opinion_id="12345")
```

### Search Court Cases

```python
search_dockets(q="intellectual property", court="ca9", date_filed_after="2020-01-01")
```

### List Available Courts

```python
search_people(q="", position_type="jud")
```

### Extract Citations from Text

```python
extract_citations_from_text(text="See 410 U.S. 113 and 42 USC § 1988.")
```

### Search United States Code Sections

```python
statutes_get_uscode_title(title_number="42", section="540b")
```

### Look Up Public Laws by Congress

```python
statutes_get_public_laws_by_congress(congress=117, law_type="public")
```

## Common Use Cases

- Legal research by topic, court, or judge
- Citation verification and lookup
- Statutory lookup and verification (USC, Statutes at Large, public laws)
- Bulk metadata extraction for LLMs

## See Also

- [../README.md](../README.md) — Main project documentation
- [tests/README.md](../tests/README.md) — Test suite documentation
- [context.json](../context.json) — Project context metadata
