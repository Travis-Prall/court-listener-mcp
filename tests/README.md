# Test Suite for CourtListener ++ MCP Server

This document describes how to run, understand, and extend the test suite for the CourtListener ++ MCP Server.

## Running Tests

- **With uv:**

  ```bash
  uv run pytest
  uv run pytest --cov=app --cov-report=term-missing
  ```

- **With VS Code Task:**

  Use the built-in task: **Run Tests**

Tests are located in the `tests/` directory. All test modules are prefixed with `test_`.

## Test Structure and Organization

- **Unit Tests:**
  - Test individual modules and functions (e.g., `test_config.py`)
- **Integration Tests:**
  - Test end-to-end server and MCP tool behavior (e.g., `test_server.py`, `test_runner.py`)
- **Live API Integration Tests:**
  - Exercise the real upstream APIs and skip automatically when the matching key is
    absent, so the suite stays runnable without credentials:
    - `test_courtlistener_integration.py` — `COURT_LISTENER_API_KEY`; covers every
      CourtListener tool (`status`, all `search_*`, all `get_*`, and all
      `citation_*`). Requests are spaced apart and retried with backoff on HTTP 429
      to respect the API's ~5-requests-per-minute authenticated throttle, so a full
      run takes several minutes.
    - `test_govinfo_integration.py` — `GOVINFO_API_KEY`; GovInfo statute tools.
    - `test_regulations_integration.py` — `REGULATIONS_API_KEY`; Regulations.gov
      rulemaking document tools.
- **Citation/Parsing Tests:**
  - Test citation parsing, extraction, and enhanced tools (e.g., `test_citeurl_integration.py`, `test_enhanced_citation_tools.py`)
- **Logs:**
  - Test logs are written to `tests/logs/` and `tests/test_logs/`

## Coverage Requirements

- All MCP tools must have corresponding tests.
- Aim for 90%+ code coverage. Run:

  ```bash
  uv run pytest --cov=app
  ```

- Ensure test names are descriptive and unique.
- Remove duplicate test cases.
- All async tools should be tested with `pytest-asyncio` or equivalent.
- Mock data should match current API schema and be updated as needed.

## Troubleshooting

- **Common Issues:**
  - Missing dependencies: Run `uv sync` or `uv pip install -r requirements.txt`
  - Async test failures: Ensure `pytest-asyncio` is installed and used for async tests.
  - Mock data errors: Update mock responses to match current API schema.
- **Debugging:**
  - Use `-s` with pytest to see print/log output.
  - Check `tests/logs/` for error logs.

## Notes

- File paths are relative to the project root.
- For Ubuntu/Linux, all commands are bash-compatible.
- See [../README.md](../README.md) and [../app/README.md](../app/README.md) for more details on MCP tools and usage.
