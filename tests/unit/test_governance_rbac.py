"""Tests unitaires pour le RBAC fin, les délégations temporaires et la séparation des tâches (Issue #7)."""

from datetime import UTC, datetime, timedelta

import pytest

from pipelines.governance.rbac import (
    DelegationStore,
    check_separation_of_duties,
    domain_matches,
    expert_can_review_domain,
)
from pipelines.kb_candidates.owners import Owner, OwnersRegistry
from pipelines.kb_candidates.service import CandidateForbiddenError


def test_domain_matches():
    assert domain_matches("architecture/*", "architecture/networking")
    assert domain_matches("architecture/*", "architecture/core/mcx")
    assert not domain_matches("architecture/*", "security/iam")
    assert domain_matches("security", "security")
    assert domain_matches("security", "security/iam")
    assert not domain_matches("security", "telecom/voice")
    assert domain_matches("*", "anything")


def test_separation_of_duties():
    candidate = {
        "id": "CAND-001",
        "title": "Test candidate",
        "source": {
            "system": "mcp",
            "author": "@alice",
            "author_email": "alice@example.org",
        },
    }

    # Le même handle ne peut pas réviser
    with pytest.raises(CandidateForbiddenError) as exc_info:
        check_separation_of_duties("@alice", candidate)
    assert exc_info.value.argument == "reviewer"

    # La même adresse e-mail ne peut pas réviser
    with pytest.raises(CandidateForbiddenError) as exc_info:
        check_separation_of_duties("@reviewer-alias", candidate, reviewer_email="alice@example.org")
    assert exc_info.value.argument == "reviewer"

    # Un réviseur distinct est accepté
    check_separation_of_duties("@bob", candidate, reviewer_email="bob@example.org")


def test_delegation_lifecycle():
    store = DelegationStore()
    expires_at = (datetime.now(UTC) + timedelta(hours=2)).isoformat()

    # Création d'une délégation
    rec = store.create_delegation(
        delegator="@core-owner-architecture",
        delegate="@ciso-office",
        domains=["architecture/*"],
        roles=["kb:review"],
        expires_at=expires_at,
        created_by="@core-owner-architecture",
    )

    del_id = rec["id"]
    assert bool(del_id)
    assert rec["delegate"] == "@ciso-office"

    # Vérification d'éligibilité
    assert store.is_delegated("@ciso-office", "architecture/gateway", "kb:review")
    assert not store.is_delegated("@ciso-office", "security/iam", "kb:review")
    assert not store.is_delegated("@ciso-office", "architecture/gateway", "kb:maintain")

    # Révocation immédiate
    revoked = store.revoke_delegation(del_id, revoked_by="@core-owner-architecture")
    assert revoked is True

    # Après révocation, n'est plus délégué
    assert not store.is_delegated("@ciso-office", "architecture/gateway", "kb:review")


def test_expert_can_review_domain_with_delegations():
    store = DelegationStore()
    expires_at = (datetime.now(UTC) + timedelta(hours=2)).isoformat()

    store.create_delegation(
        delegator="@core-owner-architecture",
        delegate="@ciso-office",
        domains=["architecture/*"],
        roles=["kb:review"],
        expires_at=expires_at,
        created_by="@core-owner-architecture",
    )

    registry = OwnersRegistry(
        owners={
            "@core-owner-architecture": Owner(handle="@core-owner-architecture", roles=("kb:review",)),
            "@ciso-office": Owner(handle="@ciso-office", roles=("kb:evaluate",)),
            "@maintainers": Owner(handle="@maintainers", roles=("kb:maintain", "kb:admin")),
        },
        domains={"architecture": "@core-owner-architecture"},
        default_owner="@maintainers",
    )

    # Propriétaire direct
    assert expert_can_review_domain("@core-owner-architecture", ["architecture/gateway"], registry, delegation_store=store)

    # Délégué via délégation active
    assert expert_can_review_domain("@ciso-office", ["architecture/gateway"], registry, delegation_store=store)

    # Autre domaine non délégué
    assert not expert_can_review_domain("@ciso-office", ["telecom/voice"], registry, delegation_store=store)

    # Maintainer a accès
    assert expert_can_review_domain("@maintainers", ["telecom/voice"], registry, delegation_store=store)
