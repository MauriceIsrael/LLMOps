"""Engagement and working database of the elicitation engine: resolved, never defaulted (issue: no `demo-2026`).

The engagement comes from the caller (option, flow state) or ``LLMOPS_ENGAGEMENT``; without either, an error says so. The
working graph of an engagement is ``artifacts/<engagement>/graph`` (the source ``elicit publish`` installs into
``data/engagements/``): two engagements never share a working database.
"""

from __future__ import annotations

from pathlib import Path

from mcp_server.core.config import require_engagement
from mcp_server.core.db import validate_engagement_id

WORKING_ROOT = Path("artifacts")


def engagement_of(value: str | None = None) -> str:
    """The explicit engagement, else ``LLMOPS_ENGAGEMENT``; raises ``DeploymentDefaultMissing`` when there is none."""
    return validate_engagement_id(require_engagement(value))


def working_database(engagement: str) -> str:
    return str(WORKING_ROOT / validate_engagement_id(engagement) / "graph")


def database_path(db_path: str | Path | None, engagement: str | None = None) -> str:
    """The explicit database path, else the working graph of the engagement."""
    return str(db_path) if db_path else working_database(engagement_of(engagement))
