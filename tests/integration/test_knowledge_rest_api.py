"""Integration tests for Knowledge REST endpoints (/api/knowledge/search and /api/knowledge/suggestions)."""

import os
from unittest.mock import patch

from starlette.testclient import TestClient

from mcp_server.main import create_starlette_app


def test_knowledge_rest_endpoints_unauthorized():
    """Vérifie que les routes REST /api/knowledge/* sont bien protégées par AuthMiddleware."""
    with patch.dict(os.environ, {"LLMOPS_AUTH_TOKEN": "secret-test-token"}):
        app = create_starlette_app()
        client = TestClient(app)

        # 1. Sans header Authorization -> 401
        res = client.get("/api/knowledge/search")
        assert res.status_code == 401

        res = client.post("/api/knowledge/suggestions", json={"title": "Test"})
        assert res.status_code == 401

        # 2. Avec mauvais token -> 401
        res = client.get("/api/knowledge/search", headers={"Authorization": "Bearer wrong-token"})
        assert res.status_code == 401


def test_knowledge_search_rest_endpoint():
    """Vérifie l'exécution de search_assets via GET /api/knowledge/search."""
    with patch.dict(os.environ, {"LLMOPS_AUTH_TOKEN": "secret-test-token"}):
        app = create_starlette_app()
        client = TestClient(app)
        headers = {"Authorization": "Bearer secret-test-token"}

        # Requête vide
        res = client.get("/api/knowledge/search?query=", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        assert isinstance(data.get("data"), list)

        # Requête avec mot-clé
        res = client.get("/api/knowledge/search?query=security", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        assert isinstance(data.get("data"), list)


def test_knowledge_suggestions_rest_endpoint():
    """Vérifie la soumission d'une proposition via POST /api/knowledge/suggestions."""
    with patch.dict(os.environ, {"LLMOPS_AUTH_TOKEN": "secret-test-token"}):
        app = create_starlette_app()
        client = TestClient(app)
        headers = {"Authorization": "Bearer secret-test-token"}

        # 1. Corps non JSON ou invalide
        res = client.post(
            "/api/knowledge/suggestions",
            content="bad json",
            headers={**headers, "Content-Type": "application/json"},
        )
        assert res.status_code == 400

        # 2. Validation champs requis manquants (title, rationale, suggested_change)
        res = client.post("/api/knowledge/suggestions", json={}, headers=headers)
        assert res.status_code == 400

        res = client.post(
            "/api/knowledge/suggestions",
            json={"title": "Titre seul"},
            headers=headers,
        )
        assert res.status_code == 400

        # 3. Payload complet valide
        valid_payload = {
            "title": "Pattern Architecture Zero-Trust Edge",
            "rationale": "Amélioration issue de la rédaction Document Studio",
            "suggested_change": "Ajout d'un contrôle d'isolation mTLS systématique.",
            "author": "john.doe@enterprise.org",
            "source_engagement": "HLD-5G-Core",
        }
        res = client.post("/api/knowledge/suggestions", json=valid_payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        assert "data" in data
        assert data["data"].get("suggestion_id", "").startswith("SUG-")
        assert "Pattern Architecture Zero-Trust Edge" in data["data"].get("message", "")
