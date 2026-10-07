"""Shared tool metadata helpers for the CourtListener MCP tool servers.

This module centralizes the MCP annotation metadata every tool in this
server advertises, so the read-only/idempotent contract is expressed once
and applied consistently across all tool groups. Keeping these helpers in
one place means a future non-read-only tool only needs a new helper here
rather than a bespoke annotation block in each module.
"""

from __future__ import annotations

from mcp.types import ToolAnnotations


def read_only_annotations(title: str) -> ToolAnnotations:
    """Build MCP annotations for a read-only, external-data tool.

    Every tool in this server retrieves data from a public read-only API
    without mutating state, so all four MCP hints are set deliberately:

    - ``readOnlyHint=True``: the tool never modifies its environment.
    - ``destructiveHint=False``: no updates are ever destructive.
    - ``idempotentHint=True``: identical arguments return the same data.
    - ``openWorldHint=True``: the tool reaches external systems.

    Args:
        title: Human-readable display title for the tool (mirrors the
            ``title`` passed to the ``@tool`` decorator).

    Returns:
        ToolAnnotations: A fully-populated annotations object for a
        read-only tool.

    """
    return ToolAnnotations(
        title=title,
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=True,
    )
