# CourtListener MCP Server v2.0

A comprehensive Model Context Protocol (MCP) server for accessing the CourtListener API v4 and eCFR, providing powerful legal and regulatory research capabilities optimized for Large Language Model (LLM) interactions.

> **Latest Update (June 2025):** All MCP tools and modules are documented. Pydantic v2 compatibility, type annotations, and import structure are up-to-date. Server passes all lint checks and includes a comprehensive test suite.

## Code Architecture Overview

- **`app/server.py`**: Main FastMCP server, imports all tool modules and sets up logging
- **`app/tools/`**: Contains all MCP tool implementations:
  - `search.py`: Search tools (opinions, dockets, audio, people, RECAP, regulations)
  - `get.py`: Get tools (opinion, docket, audio, court, person, cluster)
  - `citation.py`: Citation lookup, parsing, batch, and enhanced tools
- **`app/models.py`**: Pydantic models for data validation
- **`app/config.py`**: Configuration and environment variable management
- **`app/utils.py``: Utility functions (XML/JSON conversion, etc.)
- **`app/logs/`**: Server logs

## Server Transport

The server is configured to use **streamable-http** transport by default, making it accessible via HTTP at `http://localhost:8000/mcp/`. This allows:

- **HTTP-based access**: Standard HTTP requests for web-based deployments
- **External connections**: Server binds to `0.0.0.0` for network accessibility
- **RESTful interface**: Modern HTTP transport for better integration
- **Production ready**: Suitable for containerized and cloud deployments

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
- **models.py**: Pydantic models for API responses and validation
- **config.py**: Loads environment and configures logging
- **utils.py**: XML/JSON conversion, helpers

## MCP Tools and Parameters

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
| lookup_citation              | citation (required)                                                                                   | Look up legal citation                           |
| batch_lookup_citations       | citations (list, required)                                                                            | Batch lookup of multiple citations               |
| verify_citation_format       | citation (required)                                                                                   | Verify citation format using citeurl             |
| parse_citation_with_citeurl  | citation (required), broad (bool)                                                                     | Parse and analyze legal citations                |
| extract_citations_from_text  | text (required)                                                                                       | Extract all legal citations from a block of text |
| enhanced_citation_lookup     | citation (required), include_courtlistener (bool)                                                     | Enhanced citation lookup with citeurl & CL data  |
| list_titles                  | (none)                                                                                                | List all CFR titles                              |
| list_agencies                | (none)                                                                                                | List all federal agencies                        |
| search_regulations           | query (required), max_results                                                                         | Search federal regulations                       |
| list_all_corrections         | correction_date                                                                                       | List all editorial corrections                   |
| list_corrections_by_title    | title_number                                                                                          | List corrections for a specific title            |
| get_search_suggestions       | partial_term, max_suggestions                                                                         | Get search term suggestions                      |
| get_search_summary           | query                                                                                                 | Get aggregated search summary                    |
| get_title_search_counts      | query                                                                                                 | Get search result counts by title                |
| get_daily_search_counts      | query, start_date, end_date                                                                           | Get daily search counts                          |
| get_ancestry                 | date, title_number, part_number, section_number                                                       | Get hierarchical ancestry path                   |
| get_title_structure          | date, title_number                                                                                    | Get full title structure                         |
| get_source_xml               | date, title, part, section                                                                            | Download source XML for regulation               |
| get_source_json              | date, title, chapter, part                                                                            | Get regulatory content as JSON                   |
| status, get_api_status, health_check | (none)                                                                                         | System and health checks                         |

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

## Common Use Cases

- Legal research by topic, court, or judge
- Citation verification and lookup
- Regulatory content retrieval and analysis
- Bulk metadata extraction for LLMs

## See Also

- [../README.md](../README.md) — Main project documentation
- [tests/README.md](../tests/README.md) — Test suite documentation
- [context.json](../context.json) — Project context metadata
