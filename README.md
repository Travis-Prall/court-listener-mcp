# CourtListener ++ MCP Server

A Model Context Protocol (MCP) server that provides LLM-friendly access to the CourtListener legal database through the official CourtListener API v4, plus United States statute lookup through the official GovInfo API and federal rulemaking document search through the official Regulations.gov API. This server enables searching and retrieving legal opinions, court cases, judges, legal documents, enacted federal statutes, and federal rulemaking documents for precise legal research and citation verification.

## 🎯 Purpose

The CourtListener ++ MCP Server provides comprehensive access to **legal case data, court opinions, federal statutes, and federal rulemaking documents** through the extensive CourtListener, GovInfo, and Regulations.gov databases. CourtListener contains millions of legal opinions from federal and state courts, GovInfo provides the United States Code, Statutes at Large, and Public and Private Laws, and Regulations.gov indexes federal rulemaking dockets, proposed rules, and final rules.

## 📋 Key Advantages

- **Comprehensive Legal Database:**
  - Access to millions of court opinions and legal decisions
  - Federal and state court coverage
  - Real-time updates from court systems
- **Full Text Content:**
  - Complete opinion text for citation verification
  - Structured legal document organization
  - Rich metadata including judges, courts, and dates
- **Statutory Research:**
  - Search across USC, Statutes at Large, Public/Private Laws, and Compilations
  - Find USC sections, chapters, and subchapters within a title
  - Retrieve statute package summaries or XML/PDF/text download links
- **Federal Rulemaking Research:**
  - Search federal rulemaking documents by keyword, agency, type, or posted date
  - Retrieve full document details, optionally with attachments
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

## 🏛️ Getting a GovInfo API Key

The statute lookup tools (`statutes_*`) use the GovInfo API from the U.S. Government Publishing Office and **require** a `GOVINFO_API_KEY`.

1. **Get a free key**: Sign up at [api.data.gov](https://api.data.gov/signup/) — the same key works for `api.govinfo.gov`.

2. **Configure the Server**: Add the key to your `.env` file:

   ```bash
   GOVINFO_API_KEY=your-api-data-gov-key-here
   ```

GovInfo requests authenticate with an `X-Api-Key` HTTP header. If `GOVINFO_API_KEY` is missing at startup, the server logs a warning and **automatically disables every tool that requires it** — the `statutes_*` tools are hidden from clients until the key is set and the server is restarted. The same startup behavior applies to `COURT_LISTENER_API_KEY` and the `search_*`, `get_*`, and `citation_*` tools. As a fallback, calling a key-required tool without its key still raises an error asking for the key to be set.

The `status` tool reports which tool groups are live under `tools_available` and which are disabled (with the missing key) under `tools_disabled`.

## 📜 Getting a Regulations.gov API Key

The federal rulemaking tools (`regulations_*`) use the official Regulations.gov API and **require** a `REGULATIONS_API_KEY`.

1. **Get a free key**: Sign up at [api.data.gov](https://api.data.gov/signup/) — the same key works for `api.regulations.gov`.

2. **Configure the Server**: Add the key to your `.env` file:

   ```bash
   REGULATIONS_API_KEY=your-api-data-gov-key-here
   ```

Regulations.gov requests authenticate with an `X-Api-Key` HTTP header. The same automatic startup behavior applies: if `REGULATIONS_API_KEY` is missing, the `regulations_*` tools are disabled and hidden from clients until the key is set and the server is restarted.

**Note:** the Regulations.gov API rejects `page[size]` values below 5, so `regulations_search_documents` enforces a page size between 5 and 250.

## ⚙️ Background Tasks (MCP Tasks Extension)

The server registers the MCP background tasks extension (SEP-2663). Long-running tools — `citation_batch_lookup`, `citation_batch_lookup_citations`, and `statutes_get_statute_content` — are marked `task=True`, so clients that opt in to the tasks capability can run them in the background with progress polling instead of blocking. Calls from ordinary clients still run synchronously, so nothing changes for existing integrations. FastMCP uses an in-memory task backend by default; set `FASTMCP_DOCKET_URL` (e.g. `redis://localhost:6379/0`) for a persistent, horizontally scalable deployment.

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

   # Required for statute lookup: Your GovInfo (api.data.gov) API Key
   GOVINFO_API_KEY=your-govinfo-api-key-here

   # Optional: Regulations.gov federal rulemaking tools (auto-disabled if missing)
   REGULATIONS_API_KEY=your-api-data-gov-key-here

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
       init: true
       security_opt:
         - no-new-privileges:true
       cap_drop:
         - ALL
       read_only: true
       tmpfs:
         - /tmp:uid=10001,gid=10001,noexec,nosuid,size=64m
         - /src/app/logs:uid=10001,gid=10001,noexec,nosuid,size=64m
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
        "search_opinions", {"query": "first amendment", "court": "scotus"}
    )
    print(result)
```

### Health Checks

The server exposes an unauthenticated liveness endpoint for load balancers,
monitoring systems, and container orchestrators:

```bash
curl http://localhost:8785/health
# {"status":"healthy","service":"CourtListener ++ MCP Server","version":"0.2.2",...}
```

The Docker image ships with a `HEALTHCHECK` against this endpoint and the
provided `docker-compose.yml` mirrors it, so `docker ps` and
`docker compose ps` report container health automatically.

### HTTP Deployment Notes

Following the [FastMCP HTTP deployment guide](https://gofastmcp.com/deployment/http.md),
the server uses the **direct HTTP server** approach (`mcp.run_async(transport="http")`),
which the guide recommends for standalone, single-instance deployments. For
larger deployments, optional knobs (all environment-configurable):

- **Horizontal scaling**: set `FASTMCP_STATELESS_HTTP=true` when running
  multiple replicas behind a load balancer (streamable HTTP sessions are
  per-instance, and sticky sessions are unreliable for MCP clients). Pair
  with `FASTMCP_DOCKET_URL` so the tasks backend is shared.
- **Host/origin protection**: set `FASTMCP_HTTP_HOST_ORIGIN_PROTECTION=true`
  with explicit allow-lists (`FASTMCP_HTTP_ALLOWED_HOSTS`,
  `FASTMCP_HTTP_ALLOWED_ORIGINS`) when exposing a public hostname.
- **Long-running tools behind proxies**: for tools that may exceed proxy
  timeouts, the guide recommends an EventStore for SSE polling; and when
  fronting with nginx set `proxy_buffering off` plus generous
  `proxy_read_timeout` (300s+) so streaming responses reach clients.

## 🛠️ Available MCP Tools

The CourtListener ++ MCP Server provides these production-ready tools (see [app/README.md](app/README.md) for full details and parameters):

- **Opinion & Case Search:**
  - `search_opinions` — Search legal opinions and court decisions
  - `search_dockets` — Search court cases and dockets
  - `search_dockets_with_documents` — Search dockets with nested documents
  - `search_recap_documents` — Search RECAP filing documents
  - `search_audio` — Search oral argument audio
  - `search_people` — Search judges and legal professionals
- **Entity Retrieval:**
  - `get_opinion`, `get_docket`, `get_audio`, `get_court`, `get_person`, `get_cluster`
- **Citation Tools (CourtListener API + citeurl):**
  - `citation_lookup_citation` — Find the opinion a citation references (API key required)
  - `citation_batch_lookup_citations` — Look up multiple citations in one request (API key required)
  - `citation_batch_lookup` — Batch citation lookup with details (API key required)
  - `citation_get_citations` — Look up citations found in a text block (API key required)
  - `citation_get_citation_details` — Detailed information for a citation ID (API key required)
  - `citation_enhanced_citation_lookup` — Citeurl parsing combined with CourtListener data (API key optional)
  - `citation_parse_citation` / `citation_parse_citation_with_citeurl` — Parse citations offline with citeurl
  - `citation_validate_citation` / `citation_verify_citation_format` — Validate citation format offline
  - `citation_extract_citations_from_text` — Extract all citations from a block of text (offline)
- **Statute Tools (GovInfo API — `GOVINFO_API_KEY` required):**
  - `statutes_search_statutes` — Search across USC, Statutes at Large, Public/Private Laws, and Compilations
  - `statutes_get_uscode_title` — Find USC sections, chapters, and subchapters within a title
  - `statutes_get_statute_content` — Retrieve package/granule summaries or XML/PDF/text download links
  - `statutes_list_statute_collections` — List available statute collections (no API call)
- **Regulations.gov Tools (Federal Rulemaking — `REGULATIONS_API_KEY` required):**
  - `regulations_search_documents` — Search federal rulemaking documents by keyword, agency, type, or posted date
  - `regulations_get_document` — Get full document details, optionally with attachments

See [app/README.md](app/README.md) for a full reference of all tools, parameters, and usage examples.

## 📦 Local Installation (Alternative)

If you prefer to run without Docker:

### Prerequisites

- Python 3.14+
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

# Required for statute lookup tools
GOVINFO_API_KEY=your-api-data-gov-key-here

# Optional: Regulations.gov federal rulemaking tools (auto-disabled if missing)
REGULATIONS_API_KEY=your-api-data-gov-key-here

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

See [app/README.md](app/README.md) for detailed tool usage and examples, including search, citation, statute, and regulations queries.

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
- [GovInfo API Documentation](https://api.govinfo.gov/docs/)
- [FastMCP Framework](https://github.com/jlowin/fastmcp)
- [Model Context Protocol](https://spec.modelcontextprotocol.io/)

## 🐳 Docker Image Registries

Pre-built images are available from:

| Registry | Image |
|----------|-------|
| Docker Hub | `vesha/court-listener-mcp:latest` |
| GitHub Container Registry | `ghcr.io/travis-prall/court-listener-mcp:latest` |
| Private Registry | `docker.vesha.net/court-listener-mcp:latest` |

Images are published to the GitHub Container Registry automatically by [GitHub Actions](.github/workflows/docker-publish.yml) on every push to `main` and on `v*` version tags. Multi-arch builds (`linux/amd64` and `linux/arm64`) are supported. Docker Hub and the private `docker.vesha.net` registry are published manually with the same multi-arch image (`docker buildx build --platform linux/amd64,linux/arm64`), and versioned tags follow the `X.Y.Z` + `latest` + git-short-SHA conventions.

## ⚖️ License

This project is licensed under the **PolyForm Noncommercial License**. You are free to use, modify, and self-host this MCP server for personal, academic, or non-commercial legal research.

Integration into a commercial product, hosted service, or paid application is strictly prohibited without explicit permission.

## 💖 Support

If you find this project useful, please consider supporting its maintainer. It's completely optional, but always appreciated:

<a href="https://www.buymeacoffee.com/travisprall"><img src="https://img.buymeacoffee.com/button-api/?text=Buy me a coffee&emoji=☕&slug=travisprall&button_colour=FFDD00&font_colour=000000&font_family=Inter&outline_colour=000000&coffee_colour=ffffff" alt="Buy travisprall a coffee"></a>

Prefer crypto? See [DONATE.md](DONATE.md) for donation addresses.

---

**Ready to use!** The CourtListener ++ MCP Server provides production-ready access to legal data, federal statutes, and federal rulemaking documents through 30 comprehensive MCP tools.
