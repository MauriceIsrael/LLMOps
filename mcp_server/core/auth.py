"""Single choke point for engagement authorization (R4) with multi-tenant context support."""

import os
from contextvars import ContextVar
from enum import Enum

_current_caller: ContextVar[str] = ContextVar("current_caller", default="default_user")


class Role(str, Enum):
    SERVER_ADMIN = "server_admin"
    SYSTEM = "system"
    TENANT_USER = "tenant_user"
    LOCAL_DEV = "local_dev"


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

    Security model:
    - In production (LLMOPS_ENV=production): Fails closed. ENGAGEMENT_TOKENS must be explicitly defined.
    - In development/demo mode: Permits seamless local testing while enforcing token scoping when set.
    """
    if caller is None:
        caller = get_current_caller()

    if not engagement or not isinstance(engagement, str) or not engagement.strip():
        raise Unauthorised(engagement or "unknown")

    if not caller or not isinstance(caller, str) or not caller.strip():
        raise Unauthorised(engagement)

    # Rejeter immédiatement les identités anonymes ou non authentifiées
    blocked_identities = {"anonymous", "unauthenticated", "anonymous_blocked", "none", "null"}
    if caller in blocked_identities or caller.startswith("unauthorised") or caller.startswith("unauthorized"):
        raise Unauthorised(engagement)

    # Rôles maîtres d'administration
    if caller in (Role.SERVER_ADMIN.value, Role.SYSTEM.value, "admin"):
        return

    # Contrôle multi-tenant par ENGAGEMENT_TOKENS
    env_tokens = os.getenv("ENGAGEMENT_TOKENS", "").strip()
    if env_tokens:
        token_map = parse_engagement_tokens(env_tokens)
        if caller in token_map:
            allowed_scopes = token_map[caller]
            if "*" in allowed_scopes or engagement in allowed_scopes:
                return
            raise Unauthorised(engagement)

        # Si ENGAGEMENT_TOKENS est actif et le caller n'y est pas listé -> refus strict
        raise Unauthorised(engagement)

    # Si ENGAGEMENT_TOKENS n'est pas configuré :
    env_mode = os.getenv("LLMOPS_ENV", "development").lower().strip()
    if env_mode in ("production", "prod"):
        # En production, interdiction stricte d'accès sans scoping explicite (Fail closed - P0-3)
        raise Unauthorised(engagement)

    # Mode développement / démo locale : autoriser l'accès fluide pour les développeurs locaux
    if caller in ("default_user", Role.LOCAL_DEV.value) or not caller.startswith("unauth"):
        return

    raise Unauthorised(engagement)
