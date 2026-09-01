"""Single choke point for engagement authorization (R4)."""

import os


class Unauthorised(PermissionError):  # noqa: N818
    """Exception levée en cas d'accès non autorisé à un engagement (403-equivalent)."""

    def __init__(self, engagement: str):
        super().__init__(f"Unauthorized to access engagement '{engagement}'")
        self.engagement = engagement


def authorise(caller: str = "default_user", engagement: str = "default-engagement") -> None:
    """Single choke point for engagement access authorization.
    Every engagement tool calls this on its first line before touching the graph.
    """
    if not engagement or not isinstance(engagement, str):
        raise Unauthorised(engagement or "unknown")

    if caller.startswith("unauthorised") or caller.startswith("unauthorized") or caller == "anonymous_blocked":
        raise Unauthorised(engagement)

    # Optional multi-tenant token mapping from environment
    env_tokens = os.getenv("ENGAGEMENT_TOKENS", "")
    if env_tokens and caller != "default_user":
        # Format: token1:eng1,eng2;token2:eng3
        allowed = False
        for token_entry in env_tokens.split(";"):
            if ":" in token_entry:
                token, scopes = token_entry.split(":", 1)
                if caller == token:
                    allowed_scopes = [s.strip() for s in scopes.split(",")]
                    if "*" in allowed_scopes or engagement in allowed_scopes:
                        allowed = True
                        break
        if not allowed:
            raise Unauthorised(engagement)
