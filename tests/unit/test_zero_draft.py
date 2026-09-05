from pipelines.rfp_shredder import RFPShredder
from tools.elicitation.repository import ElicitationRepository
from tools.elicitation.zero_draft import ZeroDraftAssembler

SAMPLE_RFP = """# CCTP Sécurisé

## 1. Sécurité & Données
* [REQ-01] Le chiffrement des flux doit s'appuyer sur du mTLS et une PKI avec HSM qualifié.
* [REQ-02] Le système doit implémenter un protocole propriétaire legacy inconnu.
"""


def test_zero_draft_generation(tmp_path):
    db_file = tmp_path / "eng_zero_draft.lbug"
    
    # 1. Shredder et persistance
    shredder = RFPShredder(kb_dir="data/kb")
    reqs = shredder.shred_text(SAMPLE_RFP, engagement="test-zero-draft")
    shredder.persist_to_engagement(
        engagement="test-zero-draft",
        requirements=reqs,
        db_path=db_file,
    )

    # 2. Assemblage Zero-Draft
    assembler = ZeroDraftAssembler(db_path=db_file, kb_dir="data/kb")
    res = assembler.generate_zero_draft_hld(
        engagement="test-zero-draft",
        project_title="Projet Test HLD",
        client_name="Ministère Client",
    )

    assert res["engagement"] == "test-zero-draft"
    assert res["total_requirements"] == 2
    assert res["gap_count"] >= 1
    assert res["status"] == "provisional"

    md = res["document_markdown"]
    assert "# High-Level Design (HLD) — Projet Test HLD" in md
    assert "Ministère Client" in md
    assert "Scorecard de Couverture Réglementaire & Technique" in md
    assert "Matrice Triangulaire de Conformité RFP" in md
    assert "Écarts Identifiés & Plan d'Élicitation Ciblée (Gaps)" in md


def test_targeted_elicitation_trigger(tmp_path):
    db_file = tmp_path / "eng_targeted_elicitation.lbug"
    
    shredder = RFPShredder(kb_dir="data/kb")
    reqs = shredder.shred_text(SAMPLE_RFP, engagement="test-targeted")
    shredder.persist_to_engagement(
        engagement="test-targeted",
        requirements=reqs,
        db_path=db_file,
    )

    assembler = ZeroDraftAssembler(db_path=db_file, kb_dir="data/kb")
    q_res = assembler.trigger_targeted_elicitation(engagement="test-targeted")

    assert q_res["total_gaps_targeted"] >= 1
    assert q_res["questions_created"] >= 1
    
    # Vérifier dans le repo que les questions existent
    repo = ElicitationRepository(db_path=db_file)
    open_qs = repo.get_open_questions("test-targeted")
    assert len(open_qs) >= 1
    assert any("Q-RFP-" in q["id"] for q in open_qs)
