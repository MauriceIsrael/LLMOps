"""Tests unitaires pour to_extracted_candidates et l'export vers requirements-intake."""

from pipelines.rfp_shredder import RFPRequirement, to_extracted_candidates


def test_to_extracted_candidates_format():
    reqs = [
        RFPRequirement(
            id="REQ-SEC-01",
            engagement="nordwave",
            section="4.1",
            category="security",
            text="Le système doit chiffrer les flux de bout en bout via mTLS.",
            criticality="mandatory",
            status="covered",
            matched_assets=["ASSET-MTLS"],
            matched_controls=["SEC-01"],
            rationale="Chiffrement mTLS standard.",
        ),
        RFPRequirement(
            id="REQ-SOV-02",
            engagement="nordwave",
            section="4.2",
            category="sovereignty",
            text="L'hébergement des données doit être qualifié SecNumCloud en Union Européenne.",
            criticality="mandatory",
            status="gap",
            matched_assets=[],
            matched_controls=[],
            rationale="Exigence souveraine.",
        ),
    ]

    candidates = to_extracted_candidates(reqs, document_id="cctp-2026", document_version="1.0")

    assert len(candidates) == 2

    # 1. Candidat technique sécurité
    c1 = candidates[0]
    assert c1["id"] == "cand-REQ-SEC-01"
    assert c1["candidateKind"] == "technical-requirement"
    assert c1["suggestedDestination"] == "requirements-intake"
    assert c1["routingConfidence"] == 0.95
    assert "automated-test" in c1["verificationModes"]

    frag1 = c1["sourceFragment"]
    assert frag1["id"] == "frag-REQ-SEC-01"
    assert frag1["documentId"] == "cctp-2026"
    assert frag1["documentVersion"] == "1.0"
    assert frag1["sectionPath"] == ["4.1"]
    assert frag1["hash"].startswith("sha256:")

    # 2. Candidat gouvernance souveraineté
    c2 = candidates[1]
    assert c2["id"] == "cand-REQ-SOV-02"
    assert c2["candidateKind"] == "governance-obligation"
    assert c2["suggestedDestination"] == "requirements-intake"
    assert c2["routingConfidence"] == 0.85
    assert "vendor-attestation" in c2["verificationModes"]
