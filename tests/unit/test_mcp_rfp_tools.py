from mcp_server.knowledge.tools import (
    generate_zero_draft_hld,
    get_rfp_compliance_matrix,
    shred_rfp,
    trigger_rfp_elicitation,
)

SAMPLE_RFP_TEXT = """# Appel d'Offres Sécurisé
## 1. Sécurité
* [REQ-01] Les accès d'administration doivent obligatoirement transiter par un bastion avec mTLS.
* [REQ-02] Le système doit implémenter une intégration propriétaire non standard.
"""

def test_mcp_rfp_tools(tmp_path, monkeypatch):
    from mcp_server.core.config import server_config
    monkeypatch.setattr(server_config, "engagements_dir", tmp_path)

    # 1. shred_rfp
    res = shred_rfp(SAMPLE_RFP_TEXT, engagement="test-mcp-rfp", persist=True)
    assert res["status"] == "ok"
    matrix = res["data"]
    assert matrix["total_requirements"] >= 2
    assert matrix["covered"] >= 1
    assert matrix["gaps"] >= 1

    # 2. get_rfp_compliance_matrix
    comp_res = get_rfp_compliance_matrix(engagement="test-mcp-rfp")
    assert comp_res["status"] == "ok"
    assert comp_res["data"]["total_requirements"] >= 2

    # 3. generate_zero_draft_hld
    hld_res = generate_zero_draft_hld(
        engagement="test-mcp-rfp",
        project_title="Système Sécurisé Démo",
        client_name="Client Test",
    )
    assert hld_res["status"] == "ok"
    assert "Système Sécurisé Démo" in hld_res["data"]["document_markdown"]
    assert "Client Test" in hld_res["data"]["document_markdown"]

    # 4. trigger_rfp_elicitation
    elicit_res = trigger_rfp_elicitation(engagement="test-mcp-rfp")
    assert elicit_res["status"] == "ok"
    assert elicit_res["data"]["questions_created"] >= 1
