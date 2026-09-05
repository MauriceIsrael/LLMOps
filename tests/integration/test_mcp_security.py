"""Integration tests for MCP Server security (AuthMiddleware, Starlette routing, constant-time validation, SSE sessions)."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from starlette.testclient import TestClient

from mcp_server.config import settings
from mcp_server.main import create_starlette_app, sse_transport

pytestmark = pytest.mark.deterministic

TEST_SERVER_TOKEN = "test-secret-server-token-12345"


@pytest.fixture
def auth_client(monkeypatch):
    """Client de test configuré avec un token de test."""
    monkeypatch.setenv("SERVER_TOKEN", TEST_SERVER_TOKEN)
    monkeypatch.delenv("ENGAGEMENT_TOKENS", raising=False)
    app = create_starlette_app()
    return TestClient(app)


def test_health_endpoint_public_unauthenticated(auth_client):
    """L'endpoint /health et /healthz sont publics et ne nécessitent aucun jeton."""
    resp = auth_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"
    assert "schema_version" in data


def test_missing_token_returns_401(auth_client):
    """Une requête sur une route protégée sans jeton doit renvoyer 401 Unauthorized."""
    resp = auth_client.get("/snapshot/latest")
    assert resp.status_code == 401
    assert "Invalid or missing LLMOps authentication token" in resp.json().get("error", "")


def test_invalid_token_returns_401(auth_client):
    """Un jeton erroné ou malformé doit être rejeté avec 401 Unauthorized."""
    # Mauvais Bearer token
    resp = auth_client.get("/snapshot/latest", headers={"Authorization": "Bearer bad-token"})
    assert resp.status_code == 401

    # Mauvais X-API-Key
    resp = auth_client.get("/snapshot/latest", headers={"X-API-Key": "wrong-key"})
    assert resp.status_code == 401


def test_valid_server_token_accepted(auth_client):
    """Un jeton serveur valide via Bearer ou X-API-Key doit être accepté."""
    # 1. Bearer header
    resp = auth_client.get("/snapshot/latest", headers={"Authorization": f"Bearer {TEST_SERVER_TOKEN}"})
    assert resp.status_code in (200, 404)  # 200 si snapshot présent, mais authentifié dans tous les cas
    if resp.status_code == 401:
        pytest.fail("Valid Bearer token was rejected with 401")

    # 2. X-API-Key header
    resp2 = auth_client.get("/snapshot/latest", headers={"X-API-Key": TEST_SERVER_TOKEN})
    assert resp2.status_code != 401

    # 3. X-Server-Token header
    resp3 = auth_client.get("/snapshot/latest", headers={"X-Server-Token": TEST_SERVER_TOKEN})
    assert resp3.status_code != 401


def test_missing_server_token_config_returns_500(monkeypatch):
    """Si aucun jeton n'est configuré sur le serveur, les requêtes protégées doivent renvoyer 500."""
    monkeypatch.delenv("SERVER_TOKEN", raising=False)
    monkeypatch.delenv("LLMOPS_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("ENGAGEMENT_TOKENS", raising=False)
    monkeypatch.setattr(settings, "AUTH_TOKEN", "")

    app = create_starlette_app()
    client = TestClient(app)

    resp = client.get("/snapshot/latest", headers={"Authorization": "Bearer any-token"})
    assert resp.status_code == 500
    assert "not configured on server" in resp.json().get("error", "")


def test_multi_tenant_token_scoping_in_middleware(monkeypatch):
    """Un jeton locataire déclaré dans ENGAGEMENT_TOKENS est validé et propage son identité."""
    monkeypatch.setenv("SERVER_TOKEN", TEST_SERVER_TOKEN)
    monkeypatch.setenv("ENGAGEMENT_TOKENS", "client-a-token:nordwave-mcx-2027;client-b-token:internal-infra")

    app = create_starlette_app()
    client = TestClient(app)

    # Token client-a valide
    resp = client.get("/snapshot/latest", headers={"Authorization": "Bearer client-a-token"})
    assert resp.status_code != 401

    # Token inconnu refusé
    resp_unknown = client.get("/snapshot/latest", headers={"Authorization": "Bearer unknown-client-token"})
    assert resp_unknown.status_code == 401


def test_sse_session_id_fallback(auth_client):
    """Une requête POST /messages avec session_id valide est acceptée sans Authorization header."""
    fake_session_id = uuid4()
    # Simuler une session SSE enregistrée en mémoire
    sse_transport._read_stream_writers[fake_session_id] = "fake_writer"
    sse_transport._session_callers[fake_session_id] = "tenant-xyz"

    async def mock_handle_post(scope, receive, send):
        from starlette.responses import Response
        res = Response("accepted", status_code=202)
        await res(scope, receive, send)

    try:
        # Requête POST /messages?session_id=... sans header d'autorisation
        with patch.object(sse_transport, "handle_post_message", side_effect=mock_handle_post):
            resp = auth_client.post(f"/messages?session_id={fake_session_id.hex}")
            # Le middleware valide l'accès (ne retourne pas 401)
            assert resp.status_code == 202
    finally:
        sse_transport._read_stream_writers.pop(fake_session_id, None)
        sse_transport._session_callers.pop(fake_session_id, None)


def test_constant_time_comparison(monkeypatch):
    """Vérifier que secrets.compare_digest est bien appelé pour la comparaison sécurisée des jetons."""
    monkeypatch.setenv("SERVER_TOKEN", TEST_SERVER_TOKEN)
    app = create_starlette_app()
    client = TestClient(app)

    with patch("secrets.compare_digest", return_value=True) as mock_compare:
        resp = client.get("/snapshot/latest", headers={"Authorization": f"Bearer {TEST_SERVER_TOKEN}"})
        assert resp.status_code != 401
        assert mock_compare.called
