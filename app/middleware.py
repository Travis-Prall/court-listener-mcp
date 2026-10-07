"""Cross-cutting middleware for the CourtListener ++ MCP server.

Middleware is registered on the root :class:`fastmcp.FastMCP` instance in
``app.server`` and runs for every request, including those routed to the
namespace-mounted tool subservers. The order is deliberate (see
https://gofastmcp.com/servers/middleware):

1. :class:`ErrorHandlingMiddleware` — added first so it catches exceptions
   raised by all later middleware and shapes them into MCP error responses.
2. :class:`TimingMiddleware` — added second so it times the request after
   error shaping but before logging records the outcome.
3. :class:`LoggingMiddleware` — added last so it observes the final
   behavior of the pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware
from fastmcp.server.middleware.logging import LoggingMiddleware
from fastmcp.server.middleware.timing import TimingMiddleware
from loguru import logger

if TYPE_CHECKING:
    from fastmcp import FastMCP


def register_middleware(mcp: FastMCP) -> None:
    """Register the server's observability middleware in a deliberate order.

    Adds error handling, timing, and logging middleware to the supplied
    server. Error handling is registered first so it wraps the rest of the
    chain; logging is registered last so it records the request only after
    the other middleware have processed it.

    Args:
        mcp: The root FastMCP server instance to attach middleware to.

    """
    # 1st in / last out: log exceptions from everything downstream. Keep
    # transform_errors=False so FastMCP's normal ToolError contract is
    # preserved (the middleware centralizes logging without rewriting the
    # error type/code clients observe).
    mcp.add_middleware(ErrorHandlingMiddleware(transform_errors=False))
    # 2nd in / 2nd out: record request timing.
    mcp.add_middleware(TimingMiddleware())
    # 3rd in / first out: log the final request/response after processing.
    mcp.add_middleware(LoggingMiddleware())
    logger.info("Registered server middleware: error-handling, timing, logging")
