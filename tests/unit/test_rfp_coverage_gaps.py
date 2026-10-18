"""Tests for RFP Coverage Gap indicators and blind spots analytics (Issue #133)."""

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from mcp_server.main import create_starlette_app
from pipelines.rfp_shredder import (
    RFPRequirement,
    RFPShredder,
    compute_rfp_coverage_gaps,
)


KB = Path(__file__).parent.parent.parent / "data" / "kb"


def test_empty_requirements_coverage_gaps():
    gaps = compute_rfp_coverage_gaps([])
    assert gaps["total_requirements"] == 0
    assert gaps["covered"] == 0
    assert gaps["gaps"] == 0
    assert gaps["critical_gaps"] == 0
    assert gaps["gap_rate"] == 0.0
    assert gaps["status"] == "ready"
    assert gaps["section_gaps"] == []
    assert gaps["category_gaps"] == []
    assert gaps["blind_spots"] == []


def test_compute_rfp_coverage_gaps_breakdown():
    requirements = [
        RFPRequirement(
            id="REQ-01",
            engagement="tender-a",
            section="1. Architecture Générale",
            category="cloud-platform",
            text="La plateforme doit être déployée sur Kubernetes.",
            criticality="mandatory",
            status="covered",
            matched_assets=["K8S-PATTERN"],
        ),
        RFPRequirement(
            id="REQ-02",
            engagement="tender-a",
            section="2. Sécurité & Données",
            category="security",
            text="Chiffrement obligatoire au repos AES-256.",
            criticality="mandatory",
            status="covered",
            matched_assets=["AES-PATTERN"],
            matched_controls=["SEC-01"],
        ),
        RFPRequirement(
            id="REQ-03",
            engagement="tender-a",
            section="2. Sécurité & Données",
            category="security",
            text="Four-eyes validation sur la console d'administration.",
            criticality="mandatory",
            status="gap",
        ),
        RFPRequirement(
            id="REQ-04",
            engagement="tender-a",
            section="3. Cœur de Réseau Télécom",
            category="telco-core",
            text="Le proxy SEPP doit supporter le filtrage roaming N32.",
            criticality="mandatory",
            status="gap",
        ),
        RFPRequirement(
            id="REQ-05",
            engagement="tender-a",
            section="3. Cœur de Réseau Télécom",
            category="telco-core",
            text="Autonomie de synchronisation horloge 72h souhaitée en cas de brouillage GNSS.",
            criticality="desirable",
            status="gap",
        ),
    ]

    report = compute_rfp_coverage_gaps(requirements)

    assert report["total_requirements"] == 5
    assert report["covered"] == 2
    assert report["gaps"] == 3
    assert report["critical_gaps"] == 2  # REQ-03 and REQ-04 (mandatory gaps)
    assert report["gap_rate"] == 60.0
    assert report["status"] == "high_risk"

    # Section 3 (telco-core) should be a blind spot (100% gaps, 1 mandatory)
    sec_names = [s["section"] for s in report["section_gaps"]]
    assert "3. Cœur de Réseau Télécom" in sec_names
    telco_sec = next(s for s in report["section_gaps"] if s["section"] == "3. Cœur de Réseau Télécom")
    assert telco_sec["total"] == 2
    assert telco_sec["gaps"] == 2
    assert telco_sec["gap_rate"] == 100.0
    assert telco_sec["critical_gaps"] == 1
    assert telco_sec["severity"] == "critical"

    # Category telco-core should have suggestions
    telco_cat = next(c for c in report["category_gaps"] if c["category"] == "telco-core")
    assert "3GPP TS 33.501" in telco_cat["suggested_frameworks"]
    assert "telco/5g-core" in telco_cat["suggested_domains"]

    # Blind spots list should include section 3 and category telco-core
    blind_spot_names = [b["name"] for b in report["blind_spots"]]
    assert "3. Cœur de Réseau Télécom" in blind_spot_names
    assert "telco-core" in blind_spot_names


def test_build_compliance_matrix_includes_coverage_gaps():
    shredder = RFPShredder(kb_dir=KB)
    sample_text = """
    # Section 1 : Exigences
    1.1 Le système doit intégrer une solution de conteneurisation Kubernetes.
    1.2 Le système doit assurer un chiffrement des flux en transit TLS 1.3.
    1.3 Une passerelle SEPP roaming 5G doit être déployée.
    """
    requirements = shredder.shred_text(sample_text, engagement="test-eng")
    matrix = shredder.build_compliance_matrix(requirements)

    assert "coverage_gaps" in matrix
    gaps = matrix["coverage_gaps"]
    assert "total_requirements" in gaps
    assert "section_gaps" in gaps
    assert "category_gaps" in gaps
    assert "blind_spots" in gaps


def test_mcp_get_rfp_coverage_gaps_tool():
    from mcp_server.knowledge.tools import get_rfp_coverage_gaps

    sample_text = """
    # Chapitre 1
    1.1 L'infrastructure doit être hébergée dans un cloud souverain SecNumCloud.
    1.2 Le maintien de synchronisation horloge doit être assuré sans GNSS pendant 72h.
    """
    res = get_rfp_coverage_gaps(engagement="default", rfp_text=sample_text)
    assert res.get("status") == "ok"
    data = res.get("data", {})
    assert "blind_spots" in data
    assert "section_gaps" in data
    assert "category_gaps" in data


def test_api_rfp_coverage_gaps_endpoint(monkeypatch):
    monkeypatch.setenv("LLMOPS_AUTH_TOKEN", "secret-test-token")
    client = TestClient(create_starlette_app(), raise_server_exceptions=False)
    headers = {"Authorization": "Bearer secret-test-token"}

    # POST with raw text
    r = client.post(
        "/api/rfp/coverage-gaps",
        json={
            "engagement": "default",
            "rfp_text": "1.1 Le système doit respecter la norme ISO 27001.\n1.2 Double validation requise.",
        },
        headers=headers,
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    assert "blind_spots" in data.get("data", {})

    # GET for existing engagement
    r = client.get("/api/rfp/coverage-gaps?engagement=default", headers=headers)
    assert r.status_code == 200
    assert r.json().get("status") == "ok"

