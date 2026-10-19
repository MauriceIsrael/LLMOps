"""Single choke point for engagement authorization (R4) with multi-tenant context support."""

from __future__ import annotations

import os
from contextvars import ContextVar
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

_current_caller: ContextVar[str] = ContextVar("current_caller", default="default_user")
_current_actor_email: ContextVar[str | None] = ContextVar("current_actor_email", default=None)
_current_actor: ContextVar[Actor | None] = ContextVar("current_actor", default=None)


@dataclass
class Actor:
    """An authenticated expert acting in the knowledge governance plane (issue #7)."""

    handle: str
    email: str | None = None
    roles: tuple[str, ...] = ()
    domain_roles: dict[str, list[str]] = field(default_factory=dict)
    auth_method: str = "header"  # "assertion" | "header" | "service_token" | "local"
    jti: str | None = None
    delegated_by: str | None = None
    claims: dict[str, Any] = field(default_factory=dict)

    def has_role(self, role: str, domain: str | None = None) -> bool:
        """Check if the actor holds `role`, taking domain scope and maintainer bypass into account."""
        if "kb:maintain" in self.roles:
            return True
        if role in self.roles and (domain is None or not self.domain_roles):
            return True
        if domain and self.domain_roles:
            from pipelines.governance.rbac import domain_matches

            for pat, roles in self.domain_roles.items():
                if (role in roles or "*" in roles) and domain_matches(pat, domain):
                    return True
        return False


def get_current_actor() -> Actor | None:
    """Retrieve the currently authenticated Actor from context."""
    return _current_actor.get()


def set_current_actor(actor: Actor | None) -> None:
    """Set the authenticated Actor in the current async execution context."""
    _current_actor.set(actor)
    if actor and actor.email:
        set_current_actor_email(actor.email)
    elif actor is None:
        set_current_actor_email(None)

DELEGATE_SCOPE = "kb:delegate"
ENGAGEMENT_DELEGATE_SCOPE = "eng:delegate"  # a trusted client (Archinex) may act for the person named by X-Actor-Email
ENGAGEMENT_SERVICE_SCOPE = "eng:service"  # a service (the suite's adapter, automation) may read without a person
ENGAGEMENT_CREATE_SCOPE = "eng:create"  # may create a managed engagement


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


class Forbidden(Unauthorised):
    """An authenticated caller lacks the role an action on a managed engagement requires (still a 403)."""

    def __init__(self, engagement: str, action: str, reason: str):
        super().__init__(engagement)
        self.action = action
        self.reason = reason
        self.args = (f"Forbidden: '{action}' on engagement '{engagement}' ({reason})",)


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


def has_scope(scope: str, caller: str | None = None) -> bool:
    """Whether the caller's token or authenticated actor carries an explicit scope (e.g. ``kb:review``).

    Scopes are declared next to the engagement scopes in ``ENGAGEMENT_TOKENS``
    (``reviewer-token:kb:review;tenant-token:eng-1,eng-2``), or in the authenticated actor's
    cryptographic assertion claims / assigned KB roles (issue #7).
    """
    if caller is None:
        caller = get_current_caller()
    env_tokens = os.getenv("ENGAGEMENT_TOKENS", "").strip()
    if caller and env_tokens:
        if scope in parse_engagement_tokens(env_tokens).get(caller, []):
            return True

    # Checked from current authenticated actor (issue #7)
    actor = _current_actor.get()
    if actor is not None:
        if scope in actor.roles:
            return True
        if "scopes" in actor.claims and scope in actor.claims["scopes"]:
            return True
        if "scope" in actor.claims and scope in str(actor.claims["scope"]).split():
            return True

    return False


def set_current_actor_email(email: str | None) -> None:
    """Record the ``X-Actor-Email`` header of the current request (``None`` clears it)."""
    _current_actor_email.set((email or "").strip() or None)


def delegated_actor_email(caller: str | None = None) -> str | None:
    """E-mail of the person the caller acts for, or ``None``.

    The e-mail is honoured when an assertion-verified actor is present, or when the caller's
    token carries ``kb:delegate`` (the token of a trusted client such as Archinex, plan
    governance §3.1); for any other token it is ignored, so a raw header cannot be used
    to impersonate an owner.
    """
    actor = _current_actor.get()
    if actor and actor.email:
        return actor.email
    email = _current_actor_email.get()
    if email and has_scope(DELEGATE_SCOPE, caller):
        return email
    return None


def resolve_actor(request: Any = None) -> Actor | None:
    """Resolve acting expert from signed assertion, delegation header, or execution context.

    Extension point planned in L5 and delivered in issue #7 (contract 1.37):
    1. If request carries ``X-Actor-Token`` or ``X-Actor-Assertion``:
       Validates cryptographic EdDSA assertion against JWKS, enforces anti-replay (jti),
       and constructs an Actor with assertion claims and domain_owners lookup.
    2. Else if request carries ``X-Actor-Email`` with a ``kb:delegate`` service token:
       Resolves handle and roles from domain_owners registry (contract 1.4 backward compat).
    3. Else returns current context actor if already set.
    """
    if request is not None:
        headers = getattr(request, "headers", {})
        token = headers.get("X-Actor-Token") or headers.get("X-Actor-Assertion")
        if token:
            from mcp_server.core.assertion import ActorAssertionVerifier

            verifier = ActorAssertionVerifier()
            claims = verifier.verify(token)

            sub = str(claims.get("sub") or "").strip()
            email = claims.get("email") or (sub if "@" in sub and not sub.startswith("@") else None)
            handle = claims.get("handle") or (sub if sub.startswith("@") else None)

            from mcp_server.core.config import server_config
            from pipelines.kb_candidates.owners import load_owners

            registry = load_owners(server_config.kb_dir)
            owner = None
            if email:
                owner = registry.by_email(email)
            if not owner and handle:
                owner = registry.owners.get(handle)

            if owner:
                handle = handle or owner.handle
                email = email or owner.email
                roles = tuple(sorted(set(claims.get("roles") or ()).union(owner.roles)))
            else:
                handle = handle or (f"@{sub.split('@')[0]}" if email else f"@{sub}")
                roles = tuple(claims.get("roles") or ("kb:review",))

            domain_roles = claims.get("domain_roles") or {}
            delegation = claims.get("delegation") or {}
            delegated_by = delegation.get("delegator")

            actor = Actor(
                handle=handle,
                email=email,
                roles=roles,
                domain_roles=domain_roles,
                auth_method="assertion",
                jti=claims.get("jti"),
                delegated_by=delegated_by,
                claims=claims,
            )
            set_current_actor(actor)
            return actor

        email_header = headers.get("X-Actor-Email")
        if email_header:
            set_current_actor_email(email_header)
            caller = getattr(getattr(request, "state", None), "caller", None) or get_current_caller()
            if has_scope(DELEGATE_SCOPE, caller):
                from mcp_server.core.config import server_config
                from pipelines.kb_candidates.owners import load_owners

                registry = load_owners(server_config.kb_dir)
                owner = registry.by_email(email_header)
                if owner:
                    actor = Actor(
                        handle=owner.handle,
                        email=owner.email,
                        roles=tuple(owner.roles),
                        auth_method="header",
                    )
                    set_current_actor(actor)
                    return actor

    current = _current_actor.get()
    if current is not None:
        return current

    email = delegated_actor_email()
    if email:
        from mcp_server.core.config import server_config
        from pipelines.kb_candidates.owners import load_owners

        registry = load_owners(server_config.kb_dir)
        owner = registry.by_email(email)
        if owner:
            actor = Actor(
                handle=owner.handle,
                email=owner.email,
                roles=tuple(owner.roles),
                auth_method="header",
            )
            set_current_actor(actor)
            return actor

    return None


def open_access_warning() -> str | None:
    """Message to log at HTTP startup when engagement access is open, else ``None`` (K9, ADR-KH-01 A10-d-1).

    Access is open when no ``ENGAGEMENT_TOKENS`` are configured outside production: any authenticated
    caller then reads every engagement. Production fails closed (see ``authorise``).
    """
    if os.getenv("ENGAGEMENT_TOKENS", "").strip():
        return None
    if os.getenv("LLMOPS_ENV", "development").lower().strip() in ("production", "prod"):
        return None
    return (
        "ENGAGEMENT ACCESS IS OPEN: ENGAGEMENT_TOKENS is not set and LLMOPS_ENV is not production, so every "
        "authenticated caller can read every engagement. Set ENGAGEMENT_TOKENS (token:eng1,eng2;...) before "
        "putting real engagement data in this server."
    )


def caller_label(caller: str) -> str:
    """A loggable name for a caller: roles by name, tokens by a short fingerprint (the caller *is* the secret token)."""
    import hashlib

    if caller in (Role.SERVER_ADMIN.value, Role.SYSTEM.value, Role.LOCAL_DEV.value, "default_user"):
        return caller
    return "token:" + hashlib.sha256(caller.encode("utf-8")).hexdigest()[:8]


def authorise_action(engagement: str, action: str, caller: str | None = None) -> None:
    """Authorise ``action`` (read, contribute, decide, export, members) on ``engagement`` (K14, ADR-KH-01 A11).

    1. ``authorise``: the token must cover the engagement (scopes, production fail-closed).
    2. An engagement that is **not managed** (no registry row, or no governance database) keeps the legacy behaviour.
    3. A **managed** engagement is closed in every environment: the person behind the call (``X-Actor-Email`` through a token
       carrying ``eng:delegate``) must be a member whose role allows the action. Without a person only a token with
       ``eng:service`` may read; the operator token (``server_admin``) may manage members but never read the content.

    Refusals are audited; so is every allowed action other than a read.
    """
    from pipelines.engagement.access import ROLE_ACTIONS, get_access

    if caller is None:
        caller = get_current_caller()
    authorise(caller=caller, engagement=engagement)
    access = get_access()
    if access is None or not access.is_managed(engagement):
        return

    def refuse(reason: str, actor: str) -> None:
        access.audit(engagement, actor, action, "denied", {"reason": reason, "caller": caller_label(caller)})
        raise Forbidden(engagement, action, reason)

    email = _current_actor_email.get() if has_scope(ENGAGEMENT_DELEGATE_SCOPE, caller) else None
    if not email:
        if action == "members" and caller == Role.SERVER_ADMIN.value:
            access.audit(engagement, caller, action, "allowed", {"as": "operator"})
            return
        if action == "read" and has_scope(ENGAGEMENT_SERVICE_SCOPE, caller):
            return
        refuse("actor_required", caller_label(caller))
        return
    member = access.member(engagement, email)
    if member is None:
        refuse("not_a_member", caller_label(caller))
        return
    if action not in ROLE_ACTIONS[member["role"]]:
        refuse("role_insufficient", member["handle"])
        return
    if action != "read":
        access.audit(engagement, member["handle"], action, "allowed", {"role": member["role"]})


def acting_member(engagement: str, caller: str | None = None) -> dict[str, str] | None:
    """The member (``{email, handle, role}``) behind the current call on a managed engagement, else ``None``."""
    from pipelines.engagement.access import get_access

    caller = caller or get_current_caller()
    access = get_access()
    email = _current_actor_email.get() if has_scope(ENGAGEMENT_DELEGATE_SCOPE, caller) else None
    if access is None or not email or not access.is_managed(engagement):
        return None
    return access.member(engagement, email)


def require_distinct_validator(validator_handle: str, author_handle: str | None) -> None:
    """Separation of duties: nobody validates what they wrote (raises ``PermissionError``)."""
    if author_handle and validator_handle == author_handle:
        raise PermissionError("self_validation: the author of an item cannot be its only validator")


def require_distinct_reviewer(
    reviewer_handle: str,
    candidate: dict[str, Any],
    reviewer_email: str | None = None,
) -> None:
    """Separation of duties: candidate author cannot review it (issue #7, raises ``CandidateForbiddenError``)."""
    from pipelines.governance.rbac import check_separation_of_duties

    check_separation_of_duties(reviewer_handle, candidate, reviewer_email=reviewer_email)
