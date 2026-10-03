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

# interface -> replacement. Empty since contract 1.14 (K10): the engagement plane is back in service, the Hub holds the
# engagement base (ADR-KH-01 A10). The mechanism stays for the next deprecation; ``docs/migration-archinex.md`` is
# kept as history (it was cancelled by 1.14).
DEPRECATED: dict[str, str] = {}

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
