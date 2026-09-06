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


def test_rfp_shred_to_candidates_rest_endpoint():
    """Vérifie POST /api/rfp/shred-to-candidates pour l'intégration avec requirements-intake."""
    with patch.dict(os.environ, {"LLMOPS_AUTH_TOKEN": "secret-test-token"}):
        app = create_starlette_app()
        client = TestClient(app)
        headers = {"Authorization": "Bearer secret-test-token"}

        # Requête invalide
        res = client.post("/api/rfp/shred-to-candidates", json={}, headers=headers)
        assert res.status_code == 400

        # Requête nominale
        payload = {
            "rfp_text": "### 4.1 Sécurité\nLe système doit supporter le chiffrement TLS 1.3 et mTLS pour toutes les interfaces.",
            "document_id": "cctp-sec-2026",
            "document_version": "1.0",
            "engagement": "test-intake",
        }
        res = client.post("/api/rfp/shred-to-candidates", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        assert "candidates" in data
        assert len(data["candidates"]) >= 1
        c = data["candidates"][0]
        assert c["candidateKind"] == "technical-requirement"
        assert c["suggestedDestination"] == "requirements-intake"
        assert c["sourceFragment"]["documentId"] == "cctp-sec-2026"


def test_zero_draft_blueprint_rest_endpoint():
    """Vérifie POST /api/documents/zero-draft-blueprint pour l'intégration avec document-engine."""
    with patch.dict(os.environ, {"LLMOPS_AUTH_TOKEN": "secret-test-token"}):
        app = create_starlette_app()
        client = TestClient(app)
        headers = {"Authorization": "Bearer secret-test-token"}

        payload = {
            "engagement": "default",
            "project_title": "HLD Plateforme Télécom 5G",
            "client_name": "Opérateur National",
        }
        res = client.post("/api/documents/zero-draft-blueprint", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data.get("status") == "ok"
        assert "blueprint" in data
        assert "prose_store" in data
        assert data["blueprint"]["version"] == "1.0"
        assert data["blueprint"]["documentType"] == "hld"


def test_prose_suggest_batch_rest_endpoint():
    """Vérifie POST /api/prose/suggest-batch conforme à ADR-DE-02 de document-engine."""
    with patch.dict(os.environ, {"LLMOPS_AUTH_TOKEN": "secret-test-token"}):
        app = create_starlette_app()
        client = TestClient(app)
        headers = {"Authorization": "Bearer secret-test-token"}

        payload = {
            "requests": [
                {
                    "blockId": "block-sec-1",
                    "anchorIds": ["securite", "mtls"],
                    "instructions": "Préciser le chiffrement.",
                },
                {
                    "blockId": "block-core-2",
                    "anchorIds": ["core-5g"],
                },
            ]
        }
        res = client.post("/api/prose/suggest-batch", json=payload, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "drafts" in data
        assert "block-sec-1" in data["drafts"]
        assert "block-core-2" in data["drafts"]
        assert "generatedAt" in data
        assert "basedOnModelHash" in data
