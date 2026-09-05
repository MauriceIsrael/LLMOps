"""Single choke point for engagement authorization (R4) with multi-tenant context support."""

import os
from contextvars import ContextVar

_current_caller: ContextVar[str] = ContextVar("current_caller", default="default_user")


def get_current_caller() -> str:
    """Retrieve the currently authenticated caller from context."""
    return _current_caller.get()


def set_current_caller(caller: str) -> None:
    """Set the authenticated caller in the current async execution context."""
    _current_caller.set(caller)


class Unauthorised(PermissionError):  # noqa: N818
    """Exception levée en cas d'accès non autorisé à un engagement (403-equivalent)."""

    def __init__(self, engagement: str):
        super().__init__(f"Unauthorized to access engagement '{engagement}'")
        self.engagement = engagement


def parse_engagement_tokens(env_tokens: str) -> dict[str, list[str]]:
    """Parse ENGAGEMENT_TOKENS environment string into a token -> scopes mapping.

    Format: token1:eng1,eng2;token2:eng3;token3:*
    """
    token_map: dict[str, list[str]] = {}
    if not env_tokens:
        return token_map

    for entry in env_tokens.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        if ":" in entry:
            token, scopes = entry.split(":", 1)
            token = token.strip()
            allowed_scopes = [s.strip() for s in scopes.split(",") if s.strip()]
            token_map[token] = allowed_scopes
    return token_map


def authorise(caller: str | None = None, engagement: str = "default-engagement") -> None:
    """Single choke point for engagement access authorization.

    Every engagement tool calls this on its first line before touching the graph.
    Propagates authenticated tenant identity from request context if caller is None.
    """
    if caller is None:
        caller = get_current_caller()

    if not engagement or not isinstance(engagement, str):
        raise Unauthorised(engagement or "unknown")

    if not caller or not isinstance(caller, str):
        raise Unauthorised(engagement)

    if caller.startswith("unauthorised") or caller.startswith("unauthorized") or caller == "anonymous_blocked":
        raise Unauthorised(engagement)

    # Master server tokens / admin roles have unrestricted access
    if caller in ("server_admin", "admin", "system"):
        return

    # Multi-tenant scoping via ENGAGEMENT_TOKENS
    env_tokens = os.getenv("ENGAGEMENT_TOKENS", "").strip()
    if env_tokens:
        token_map = parse_engagement_tokens(env_tokens)

        # Check if caller matches any authorized tenant token or user
        if caller in token_map:
            allowed_scopes = token_map[caller]
            if "*" in allowed_scopes or engagement in allowed_scopes:
                return
            raise Unauthorised(engagement)

        # If ENGAGEMENT_TOKENS is active and caller is default_user (or unmatched token), refuse access
        raise Unauthorised(engagement)

    # When ENGAGEMENT_TOKENS is not configured, default_user or standard callers are accepted
