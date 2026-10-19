"""Tests unitaires pour les assertions d'acteur EdDSA (Ed25519) et JWKS (Issue #7)."""

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from mcp_server.core.assertion import (
    ActorAssertionError,
    ActorAssertionVerifier,
    JTIReplayStore,
    JWKSRegistry,
    RevocationStore,
    generate_ed25519_keypair,
    jwk_to_public_key,
    sign_actor_assertion,
)


def test_ed25519_keypair_generation_and_jwk():
    priv, pub_jwk = generate_ed25519_keypair(kid="test-key-1")

    assert pub_jwk["kty"] == "OKP"
    assert pub_jwk["crv"] == "Ed25519"
    assert pub_jwk["kid"] == "test-key-1"
    assert "x" in pub_jwk
    assert "d" not in pub_jwk

    pub = jwk_to_public_key(pub_jwk)
    assert isinstance(pub, ed25519.Ed25519PublicKey)


def test_jwks_registry():
    registry = JWKSRegistry()
    priv, pub_jwk = generate_ed25519_keypair(kid="key-archinex-1")
    registry.add_jwk(pub_jwk)

    jwks = registry.to_jwks()
    assert "keys" in jwks
    assert len(jwks["keys"]) == 1
    assert jwks["keys"][0]["kid"] == "key-archinex-1"

    loaded_pub = registry.get_key("key-archinex-1")
    assert isinstance(loaded_pub, ed25519.Ed25519PublicKey)


def test_sign_and_verify_assertion():
    priv, pub_jwk = generate_ed25519_keypair(kid="key-1")
    registry = JWKSRegistry()
    registry.add_jwk(pub_jwk)

    token = sign_actor_assertion(
        priv,
        sub="architect@example.org",
        kid="key-1",
        handle="@core-owner-architecture",
        email="architect@example.org",
        roles=["kb:review", "kb:evaluate"],
        domain_roles={"architecture/*": ["kb:review"]},
        exp_seconds=300,
    )

    verifier = ActorAssertionVerifier(registry=registry)
    claims = verifier.verify(token)

    assert claims["handle"] == "@core-owner-architecture"
    assert claims["email"] == "architect@example.org"
    assert "kb:review" in claims["roles"]
    assert "architecture/*" in claims["domain_roles"]
    assert "jti" in claims


def test_anti_replay_prevention():
    priv, pub_jwk = generate_ed25519_keypair(kid="key-1")
    registry = JWKSRegistry()
    registry.add_jwk(pub_jwk)
    replay_store = JTIReplayStore()

    token = sign_actor_assertion(
        priv,
        sub="architect@example.org",
        kid="key-1",
        handle="@core-owner-architecture",
        email="architect@example.org",
        roles=["kb:review"],
    )

    verifier = ActorAssertionVerifier(registry=registry, replay_store=replay_store)
    # Premier passage : succès
    claims = verifier.verify(token)
    assert claims["handle"] == "@core-owner-architecture"

    # Deuxième passage avec le même token (rejeu) : échec replay_detected
    with pytest.raises(ActorAssertionError) as exc_info:
        verifier.verify(token)
    assert exc_info.value.code == "replay_detected"


def test_expired_assertion():
    priv, pub_jwk = generate_ed25519_keypair(kid="key-1")
    registry = JWKSRegistry()
    registry.add_jwk(pub_jwk)

    # Jeton expiré il y a 60 secondes
    token = sign_actor_assertion(
        priv,
        sub="architect@example.org",
        kid="key-1",
        handle="@core-owner-architecture",
        email="architect@example.org",
        roles=["kb:review"],
        exp_seconds=-60,
    )

    verifier = ActorAssertionVerifier(registry=registry)
    with pytest.raises(ActorAssertionError) as exc_info:
        verifier.verify(token)
    assert exc_info.value.code == "token_expired"


def test_revocation_by_jti_and_actor():
    priv, pub_jwk = generate_ed25519_keypair(kid="key-1")
    registry = JWKSRegistry()
    registry.add_jwk(pub_jwk)
    revocation_store = RevocationStore()

    token = sign_actor_assertion(
        priv,
        sub="architect@example.org",
        kid="key-1",
        handle="@core-owner-architecture",
        email="architect@example.org",
        roles=["kb:review"],
    )

    verifier = ActorAssertionVerifier(registry=registry, revocation_store=revocation_store)

    # Révoquer l'acteur
    revocation_store.revoke_actor("@core-owner-architecture", reason="Incident de sécurité")

    with pytest.raises(ActorAssertionError) as exc_info:
        verifier.verify(token)
    assert exc_info.value.code == "token_revoked"
    assert "Incident de sécurité" in exc_info.value.reason


def test_invalid_signature_tampered_payload():
    priv1, pub_jwk1 = generate_ed25519_keypair(kid="key-1")
    priv2, pub_jwk2 = generate_ed25519_keypair(kid="key-2")
    registry = JWKSRegistry()
    registry.add_jwk(pub_jwk1)

    # Signé avec priv2 mais déclaré comme key-1
    token = sign_actor_assertion(
        priv2,
        sub="architect@example.org",
        kid="key-1",
        handle="@core-owner-architecture",
        email="architect@example.org",
        roles=["kb:review"],
    )

    verifier = ActorAssertionVerifier(registry=registry)
    with pytest.raises(ActorAssertionError) as exc_info:
        verifier.verify(token)
    assert exc_info.value.code == "invalid_signature"
