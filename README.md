# CourtListener MCP Server

A Model Context Protocol (MCP) server that provides LLM-friendly access to the CourtListener legal database and the Electronic Code of Federal Regulations (eCFR) through the official CourtListener API v4. This server enables searching and retrieving legal opinions, court cases, judges, legal documents, and federal regulations for precise legal research and citation verification.

## 🎯 Purpose

The CourtListener MCP Server provides comprehensive access to **legal case data, court opinions, and federal regulations** through the extensive CourtListener and eCFR databases. CourtListener contains millions of legal opinions from federal and state courts, while eCFR provides up-to-date federal regulations.

## 📋 Key Advantages

- **Comprehensive Legal Database:**
  - Access to millions of court opinions and legal decisions
  - Federal and state court coverage
  - Real-time updates from court systems
- **Full Text Content:**
  - Complete opinion text for citation verification
  - Structured legal document organization
  - Rich metadata including judges, courts, and dates
- **Regulatory Research:**
  - Search and retrieve current federal regulations
  - Validate regulatory citations and references
- **Legal Research:**
  - Search by judge, court, case name, or content
  - Verify exact legal language and precedents
  - Validate legal citations and references

## 🛠️ Available MCP Tools

The CourtListener MCP Server provides these production-ready tools (see [app/README.md](app/README.md) for full details and parameters):

- **Opinion & Case Search:**
  - `search_opinions` — Search legal opinions and court decisions
  - `search_dockets` — Search court cases and dockets
  - `search_dockets_with_documents` — Search dockets with nested documents
  - `search_recap_documents` — Search RECAP filing documents
  - `search_audio` — Search oral argument audio
  - `search_people` — Search judges and legal professionals
- **Entity Retrieval:**
  - `get_opinion`, `get_docket`, `get_audio`, `get_court`, `get_person`, `get_cluster`
- **Citation & Regulation Tools:**
  - `lookup_citation`, `batch_lookup_citations`, `verify_citation_format`, `parse_citation_with_citeurl`, `extract_citations_from_text`, `enhanced_citation_lookup`
  - `list_titles`, `list_agencies`, `search_regulations`, `list_all_corrections`, `list_corrections_by_title`, `get_search_suggestions`, `get_search_summary`, `get_title_search_counts`, `get_daily_search_counts`, `get_ancestry`, `get_title_structure`, `get_source_xml`, `get_source_json`
- **System & Health:**
  - `status`, `get_api_status`, `health_check`

See [app/README.md](app/README.md) for a full reference of all tools, parameters, and usage examples.

## 📦 Installation

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) for dependency management
- Internet connection for CourtListener API access

### Install with uv

```bash
# Clone the repository
 git clone <repository-url>
 cd CourtListener

# Install dependencies
 uv sync

# Activate the environment (optional)
 uv shell
```

### Environment Configuration

Create a `.env` file in the project root:

```bash
COURTLISTENER_BASE_URL=https://www.courtlistener.com/api/rest/v4/
COURT_LISTENER_TIMEOUT=30
LOG_LEVEL=INFO
RATE_LIMIT_REQUESTS=10
RATE_LIMIT_PERIOD=60
DEBUG=false
MCP_PORT=8765
MCP_DEV_PORT=8766
```

### Running the Server

The server now runs with streamable-http transport by default:

```bash
uv run python -m app.server
```

This will start the server at:

- **Host**: `0.0.0.0` (accessible from external connections)
- **Port**: `8000`
- **Endpoint**: `http://localhost:8000/mcp/`

Or use the VS Code task: **Run MCP Server**

#### Connecting to the Server

When using the streamable-http transport, clients can connect to the server using:

```python
from fastmcp import Client

async with Client("http://localhost:8000/mcp/") as client:
    result = await client.call_tool("status")
    print(result)
```

## 💡 Usage Examples

See [app/README.md](app/README.md) for detailed tool usage and examples, including search, citation, and regulatory queries.

## 🐳 Docker Setup

```bash
# Production
 docker-compose up -d
# Development with hot reload
 docker-compose --profile dev up --build
```

## 🧪 Testing

```bash
uv run pytest
uv run pytest --cov=app --cov-report=term-missing
```

See [tests/README.md](tests/README.md) for test suite details, coverage, and troubleshooting.

## 🔧 Development

```bash
uv run ruff format .
uv run ruff check .
uv run mypy app/
uv run pip-audit
```

## 🚨 Troubleshooting

See [app/README.md](app/README.md) and [tests/README.md](tests/README.md) for troubleshooting and advanced usage.

## 📚 Documentation

- [Source Code Documentation](app/README.md)
- [Test Documentation](tests/README.md)
- [Project Context](context.json)
- [CourtListener API Documentation](https://www.courtlistener.com/api/rest/v4/)
- [eCFR API Documentation](https://www.ecfr.gov/developers/documentation/api/v1)
- [FastMCP Framework](https://github.com/jlowin/fastmcp)
- [Model Context Protocol](https://spec.modelcontextprotocol.io/)

---

**Ready to use!** The CourtListener MCP Server provides production-ready access to federal regulations and legal data through 20+ comprehensive MCP tools.
