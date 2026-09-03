"""Contract tests for suggest_knowledge_improvement tool."""

from mcp_server.knowledge.tools import suggest_knowledge_improvement


def test_suggest_knowledge_improvement_contract():
    # 1. Test validation on empty arguments
    res_err = suggest_knowledge_improvement(title="", rationale="", suggested_change="")
    assert res_err["status"] == "invalid_argument"

    # 2. Test successful suggestion submission
    res = suggest_knowledge_improvement(
        title="Proposition de Pattern : Double Validation Canary pour NetDevOps",
        rationale="Évite les régressions de routage BGP en injectant un préfixe canary avant déploiement généralisé.",
        suggested_change="Créer un nouveau pattern PAT-007 spécifiant le canary testing réseau.",
        author="Alice (Cloud Architect)",
        contact_email="alice@nordwave.eu",
        source_engagement="nordwave-mcx-2027",
    )
    assert res["status"] == "ok"
    assert res["count"] == 1
    data = res["data"]
    assert data["suggestion_id"].startswith("SUG-")
    assert data["owner_notified"] == "maurice.israel@free.fr"
    assert "local_archive" in data["notifications_sent"]
    assert "cloud_logging" in data["notifications_sent"]
