"""Deprecation signals (docs/DEPRECATION.md): header, envelope field and log, never a change of behaviour."""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from mcp_server.core.auth import get_current_caller
from mcp_server.core.version import CONTRACT_VERSION

logger = logging.getLogger("mcp_server.deprecation")

MIGRATION_GUIDE_URL = "https://github.com/MauriceIsrael/LLMOps/blob/main/docs/migration-archinex.md"
DOC = "docs/migration-archinex.md"
SINCE = CONTRACT_VERSION

# interface -> replacement on the Archinex side (plan de gouvernance, lot L4)
DEPRECATED: dict[str, str] = {
    "POST /api/elicitation/trigger": "archinex: élicitation par sujet (A2)",
    "GET /api/elicitation/questions": "archinex: questions d'un sujet (A2)",
    "GET /api/arbitration/board": "archinex: tableau de maturité des sujets (A3)",
    "GET /api/arbitration/conflicts": "archinex: conflits et arbitrage (A3)",
    "GET /api/arbitration/statements": "archinex: énoncés d'un sujet (A3)",
    "get_subject": "archinex: fiche sujet (A3)",
    "get_subject_trajectory": "archinex: trajectoire d'un sujet (A3)",
    "get_board": "archinex: tableau de maturité des sujets (A3)",
    "get_statements": "archinex: énoncés d'un sujet (A3)",
    "get_conflicts": "archinex: conflits et arbitrage (A3)",
    "get_open_questions": "archinex: questions d'un sujet (A2)",
    "get_diagram_graph": "archinex: diagrammes d'engagement (A4)",
    "get_render_payload": "archinex: rendu du document d'engagement (A4)",
    "get_dangling_references": "archinex: contrôle des références (A4)",
    "get_engagement_export": "archinex: export de l'engagement (A4)",
}

LEGACY: tuple[str, ...] = (
    "POST /api/rfp/shred-to-candidates",
    "POST /api/documents/zero-draft-blueprint",
    "shred_rfp",
    "generate_zero_draft_hld",
    "trigger_rfp_elicitation",
)


def deprecation_field(name: str) -> dict[str, str]:
    return {"since": SINCE, "replaced_by": DEPRECATED[name], "doc": DOC}


def signal(name: str) -> None:
    logger.warning(
        "deprecated interface called: %s (caller=%s, since %s)", name, get_current_caller(), SINCE
    )


def headers(name: str) -> dict[str, str]:
    return {"Deprecation": "true", "Link": f'<{MIGRATION_GUIDE_URL}>; rel="deprecation"'}


def mark(response: Any, name: str) -> Any:
    """Add the ``deprecation`` field to a response envelope (shape otherwise unchanged) and log the call."""
    if isinstance(response, dict):
        if "deprecation" in response:  # already marked by the tool behind the route: one log line per call
            return response
        response["deprecation"] = deprecation_field(name)
    signal(name)
    return response


F = TypeVar("F", bound=Callable[..., Any])


def deprecated(name: str) -> Callable[[F], F]:
    """Decorator for MCP tools: same signature, same result, plus the ``deprecation`` field and a log line."""

    def decorate(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return mark(func(*args, **kwargs), name)

        return wrapper  # type: ignore[return-value]

    return decorate
