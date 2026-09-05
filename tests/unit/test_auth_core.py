"""Unit tests for mcp_server.core.auth (multi-tenant authorization and context propagation)."""

import pytest

from mcp_server.core.auth import (
    Unauthorised,
    authorise,
    get_current_caller,
    parse_engagement_tokens,
    set_current_caller,
)


def test_unauthorised_exception():
    exc = Unauthorised("eng-secret")
    assert exc.engagement == "eng-secret"
    assert "Unauthorized to access engagement 'eng-secret'" in str(exc)
    assert isinstance(exc, PermissionError)


def test_parse_engagement_tokens():
    assert parse_engagement_tokens("") == {}
    assert parse_engagement_tokens("   ") == {}

    raw = "tok-alpha:eng-1,eng-2; tok-beta:eng-3; tok-wildcard:*"
    parsed = parse_engagement_tokens(raw)

    assert parsed["tok-alpha"] == ["eng-1", "eng-2"]
    assert parsed["tok-beta"] == ["eng-3"]
    assert parsed["tok-wildcard"] == ["*"]


def test_authorise_invalid_inputs():
    with pytest.raises(Unauthorised):
        authorise(caller="default_user", engagement="")

    with pytest.raises(Unauthorised):
        authorise(caller="default_user", engagement=None)  # type: ignore[arg-type]

    with pytest.raises(Unauthorised):
        authorise(caller="", engagement="eng-1")  # type: ignore[arg-type]


def test_authorise_blocked_callers():
    with pytest.raises(Unauthorised):
        authorise(caller="unauthorised_bot", engagement="eng-1")

    with pytest.raises(Unauthorised):
        authorise(caller="unauthorized_agent", engagement="eng-1")

    with pytest.raises(Unauthorised):
        authorise(caller="anonymous_blocked", engagement="eng-1")


def test_authorise_single_tenant_mode(monkeypatch):
    monkeypatch.delenv("ENGAGEMENT_TOKENS", raising=False)
    # Dans le mode standard sans multi-tenant, default_user et les callers réguliers passent
    authorise(caller="default_user", engagement="nordwave-mcx-2027")
    authorise(caller="custom_user", engagement="any-project")


def test_authorise_multi_tenant_scoping(monkeypatch):
    env_config = "tenant-a:nordwave-mcx-2027,sec-2027;tenant-b:internal-infra;super-token:*"
    monkeypatch.setenv("ENGAGEMENT_TOKENS", env_config)

    # 1. Tenant-A accès autorisé
    authorise(caller="tenant-a", engagement="nordwave-mcx-2027")
    authorise(caller="tenant-a", engagement="sec-2027")

    # 2. Tenant-A tente d'accéder à l'engagement d'un autre tenant
    with pytest.raises(Unauthorised) as exc_info:
        authorise(caller="tenant-a", engagement="internal-infra")
    assert exc_info.value.engagement == "internal-infra"

    # 3. Tenant-B accès autorisé et non autorisé
    authorise(caller="tenant-b", engagement="internal-infra")
    with pytest.raises(Unauthorised):
        authorise(caller="tenant-b", engagement="nordwave-mcx-2027")

    # 4. Token wildcard
    authorise(caller="super-token", engagement="anything")

    # 5. Master admin bypass (server_admin, admin, system)
    authorise(caller="server_admin", engagement="nordwave-mcx-2027")
    authorise(caller="admin", engagement="internal-infra")

    # 6. default_user non autorisé en mode multi-tenant strict
    with pytest.raises(Unauthorised):
        authorise(caller="default_user", engagement="nordwave-mcx-2027")

    # 7. Token inconnu
    with pytest.raises(Unauthorised):
        authorise(caller="unknown-token", engagement="nordwave-mcx-2027")


def test_contextvar_caller_propagation(monkeypatch):
    monkeypatch.setenv("ENGAGEMENT_TOKENS", "scoped-token:project-x")

    # Par défaut default_user
    set_current_caller("default_user")
    assert get_current_caller() == "default_user"

    # Changement de caller dans le contexte
    set_current_caller("scoped-token")
    assert get_current_caller() == "scoped-token"

    # authorise sans paramètre caller utilise le ContextVar
    authorise(engagement="project-x")

    with pytest.raises(Unauthorised):
        authorise(engagement="project-other")
