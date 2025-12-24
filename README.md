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

## � Getting a CourtListener API Key

An API key is **required** for authenticated access to the CourtListener API. While some endpoints work without authentication, you will be severely rate-limited (anonymous users get throttled quickly).

### Why You Need an API Key

- **Higher Rate Limits**: Authenticated users get 5,000 queries per hour
- **Full API Access**: Some endpoints require authentication
- **Better Performance**: Avoid anonymous throttling
- **Usage Tracking**: Monitor your API usage in your profile

### How to Get Your API Key

1. **Create an Account**: Go to [CourtListener Sign Up](https://www.courtlistener.com/register/) and create a free account.

2. **Sign In**: Log into your account at [CourtListener Sign In](https://www.courtlistener.com/sign-in/).

3. **Get Your Token**: Navigate to [API Help - REST](https://www.courtlistener.com/help/api/rest/#your-authorization-token) while logged in. Your authorization token will be displayed on that page.

4. **Copy Your Token**: Your token will look something like: `abcd1234567890efghij1234567890abcd123456`

5. **Configure the Server**: Add your token to your `.env` file:

   ```bash
   COURT_LISTENER_API_KEY=your-token-here
   ```

### Token Authentication Format

When making API requests, the token is sent in the `Authorization` HTTP header:

```bash
Authorization: Token your-token-here
```

> **Important**: Don't forget the word "Token" before your actual token value!

## 🐳 Docker Quick Start (Recommended)

The fastest way to get started is with Docker. Pre-built images are available from multiple registries.

### Pull the Image

```bash
# From Docker Hub
docker pull vesha/court-listener-mcp:latest

# From GitHub Container Registry
docker pull ghcr.io/travis-prall/court-listener-mcp:latest
```

### Run with Docker

```bash
# Quick start (minimal configuration)
docker run -d \
  --name court-listener-mcp \
  -p 8785:8785 \
  -e COURT_LISTENER_API_KEY=your-api-key-here \
  vesha/court-listener-mcp:latest

# With all configuration options
docker run -d \
  --name court-listener-mcp \
  -p 8785:8785 \
  -e COURT_LISTENER_API_KEY=your-api-key-here \
  -e COURTLISTENER_BASE_URL=https://www.courtlistener.com/api/rest/v4/ \
  -e COURTLISTENER_TIMEOUT=30 \
  -e COURTLISTENER_LOG_LEVEL=INFO \
  -e ENVIRONMENT=production \
  vesha/court-listener-mcp:latest
```

### Run with Docker Compose

1. **Create a `.env` file** in your project directory:

   ```bash
   # Required: Your CourtListener API Key
   COURT_LISTENER_API_KEY=your-api-key-here

   # Optional: Override defaults
   COURTLISTENER_LOG_LEVEL=INFO
   ENVIRONMENT=production
   ```

2. **Create a `docker-compose.yml`** (or use the one in this repo):

   ```yaml
   services:
     court-listener-mcp:
       image: vesha/court-listener-mcp:latest
       container_name: court-listener-mcp-server
       ports:
         - "8785:8785"
       env_file:
         - .env
       environment:
         - LOG_LEVEL=INFO
         - API_BASE_URL=https://www.courtlistener.com/api/rest/v4
       restart: unless-stopped
   ```

3. **Start the server**:

   ```bash
   docker-compose up -d
   ```

4. **View logs**:

   ```bash
   docker-compose logs -f
   ```

5. **Stop the server**:

   ```bash
   docker-compose down
   ```

### Build Your Own Image

If you prefer to build the image locally:

```bash
# Clone the repository
git clone https://github.com/Travis-Prall/court-listener-mcp.git
cd court-listener-mcp

# Build the image
docker build -t court-listener-mcp:latest .

# Run your local build
docker run -d \
  --name court-listener-mcp \
  -p 8785:8785 \
  -e COURT_LISTENER_API_KEY=your-api-key-here \
  court-listener-mcp:latest
```

### Connecting to the Docker Container

Once running, the MCP server is available at:

- **URL**: `http://localhost:8785/mcp/`
- **Protocol**: Streamable HTTP (FastMCP)

Example client connection:

```python
from fastmcp import Client

async with Client("http://localhost:8785/mcp/") as client:
    # Check server status
    result = await client.call_tool("status")
    print(result)

    # Search for legal opinions
    result = await client.call_tool(
        "search_opinions",
        {"query": "first amendment", "court": "scotus"}
    )
    print(result)
```

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

## 📦 Local Installation (Alternative)

If you prefer to run without Docker:

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) for dependency management
- Internet connection for CourtListener API access

### Install with uv

```bash
# Clone the repository
git clone https://github.com/Travis-Prall/court-listener-mcp.git
cd court-listener-mcp

# Install dependencies
uv sync

# Activate the environment (optional)
uv shell
```

### Environment Configuration

Create a `.env` file in the project root (see `example.env` for all options):

```bash
# Required
COURT_LISTENER_API_KEY=your-api-key-here

# Optional (defaults shown)
COURTLISTENER_BASE_URL=https://www.courtlistener.com/api/rest/v4/
COURTLISTENER_TIMEOUT=30
COURTLISTENER_LOG_LEVEL=INFO
COURTLISTENER_DEBUG=false
HOST=0.0.0.0
MCP_PORT=8785
ENVIRONMENT=production
```

### Running the Server

```bash
uv run python -m app.server
```

This will start the server at:

- **Host**: `0.0.0.0` (accessible from external connections)
- **Port**: `8785`
- **Endpoint**: `http://localhost:8785/mcp/`

Or use the VS Code task: **Run MCP Server**

## 💡 Usage Examples

See [app/README.md](app/README.md) for detailed tool usage and examples, including search, citation, and regulatory queries.

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

### Common Issues

**"unauthorized" or "throttled" errors:**
- Ensure your API key is set correctly in `.env`
- Verify you're using Token authentication (not just the raw token)
- Check your [API usage](https://www.courtlistener.com/profile/api/#usage) in your CourtListener profile

**Container won't start:**
- Check logs: `docker logs court-listener-mcp`
- Verify `.env` file exists and is readable
- Ensure port 8785 is not already in use

**Connection refused:**
- Wait a few seconds for the server to start
- Verify the container is running: `docker ps`
- Check the correct port mapping

See [app/README.md](app/README.md) and [tests/README.md](tests/README.md) for additional troubleshooting.

## 📚 Documentation

- [Source Code Documentation](app/README.md)
- [Test Documentation](tests/README.md)
- [CourtListener API Documentation](https://www.courtlistener.com/api/rest/v4/)
- [CourtListener API Help](https://www.courtlistener.com/help/api/rest/)
- [eCFR API Documentation](https://www.ecfr.gov/developers/documentation/api/v1)
- [FastMCP Framework](https://github.com/jlowin/fastmcp)
- [Model Context Protocol](https://spec.modelcontextprotocol.io/)

## 🐳 Docker Image Registries

Pre-built images are available from:

| Registry | Image |
|----------|-------|
| Docker Hub | `vesha/court-listener-mcp:latest` |
| GitHub Container Registry | `ghcr.io/travis-prall/court-listener-mcp:latest` |

---

**Ready to use!** The CourtListener MCP Server provides production-ready access to federal regulations and legal data through 20+ comprehensive MCP tools.
