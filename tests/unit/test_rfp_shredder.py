from pipelines.rfp_shredder import RFPShredder

SAMPLE_RFP_TEXT = """# Appel d'Offres : Réseau Critique Sécurisé (CCTP)

## 1. Souveraineté & Hébergement
* [REQ-SEC-01] Le système doit impérativement être hébergé sur une infrastructure qualifiée SecNumCloud 3.2 par l'ANSSI.
* [REQ-SEC-02] Les clés cryptographiques de chiffrement doivent être générées et séquestrées sur un module matériel HSM qualifié.

## 2. Infrastructure & Conteneurs
* [REQ-INF-01] La plateforme de conteneurs doit être pilotée par une réconciliation continue en GitOps sous Kubernetes.
* [REQ-INF-02] Le stockage du cluster de management devrait s'appuyer sur un SAN NVMe dual-controller.

## 3. Cœur de Réseau & Télécom
* [REQ-TEL-01] Les fonctions de signalisation vocale critique doivent respecter les spécifications 3GPP et MCX (MCPTT).
* [REQ-EXC-01] Le fournisseur doit intégrer un protocole propriétaire propriétaire-xyz non documenté sur liaisons analogiques.
"""


def test_rfp_shredder_extraction():
    shredder = RFPShredder(kb_dir="data/kb")
    reqs = shredder.shred_text(SAMPLE_RFP_TEXT, engagement="test-rfp")

    assert len(reqs) >= 5

    # Vérification des IDs
    ids = [r.id for r in reqs]
    assert "REQ-RFP-001" in ids

    # Vérification de la détection de souveraineté / sécurité
    secnum_req = next((r for r in reqs if "SecNumCloud" in r.text), None)
    assert secnum_req is not None
    assert secnum_req.category in ("sovereignty", "security")
    assert secnum_req.criticality == "mandatory"
    assert secnum_req.status in ("covered", "partially_covered")
    assert any("SNC-REQ" in c or "ADR-" in c or "PAT-" in c for c in secnum_req.matched_controls + secnum_req.matched_assets)

    # Vérification du HSM
    hsm_req = next((r for r in reqs if "HSM" in r.text), None)
    assert hsm_req is not None
    assert hsm_req.status == "covered"
    assert "PAT-004" in hsm_req.matched_assets or "ADR-0005" in hsm_req.matched_assets or any("SNC" in c for c in hsm_req.matched_controls)

    # Vérification de l'exigence souhaitée (desirable)
    desirable_req = next((r for r in reqs if "devrait" in r.text.lower()), None)
    assert desirable_req is not None
    assert desirable_req.criticality == "desirable"

    # Vérification du Gap (protocole propriétaire non standard)
    gap_req = next((r for r in reqs if "propriétaire-xyz" in r.text), None)
    assert gap_req is not None
    assert gap_req.status == "gap"
    assert "Élicitation requise" in gap_req.rationale


def test_build_compliance_matrix():
    shredder = RFPShredder(kb_dir="data/kb")
    reqs = shredder.shred_text(SAMPLE_RFP_TEXT, engagement="test-rfp")
    matrix = shredder.build_compliance_matrix(reqs)

    assert matrix["total_requirements"] == len(reqs)
    assert matrix["covered"] >= 3
    assert matrix["gaps"] >= 1
    assert 0 < matrix["coverage_rate"] <= 100.0
    assert "breakdown_by_category" in matrix
    assert len(matrix["matrix"]) == len(reqs)


def test_persist_to_engagement(tmp_path):
    db_file = tmp_path / "test_engagement.lbug"
    shredder = RFPShredder(kb_dir="data/kb")
    reqs = shredder.shred_text(SAMPLE_RFP_TEXT, engagement="test-rfp")

    result = shredder.persist_to_engagement(
        engagement="test-rfp",
        requirements=reqs,
        db_path=db_file,
    )

    assert result["saved_requirements"] == len(reqs)

    from tools.elicitation.repository import ElicitationRepository
    repo = ElicitationRepository(db_path=db_file)
    persisted = repo.get_requirements("test-rfp")
    assert len(persisted) == len(reqs)
