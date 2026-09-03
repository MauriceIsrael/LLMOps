"""Contract tests for Technical Skills and Staffing Matrix Tools."""

from mcp_server.knowledge.tools import (
    get_skills_matrix,
    list_skills,
)


def test_list_skills_contract():
    res = list_skills()
    assert res["status"] == "ok"
    assert res["count"] >= 9
    skill_ids = {s["id"] for s in res["data"]}
    assert "SKL-CRYPTO-HSM" in skill_ids
    assert "SKL-SEC-ZEROTRUST" in skill_ids
    assert "SKL-TELCO-CORE" in skill_ids
    assert "SKL-NET-UNDERLAY" in skill_ids
    assert "SKL-AUTO-GITOPS" in skill_ids
    assert "SKL-OBS-SOC" in skill_ids
    assert "SKL-KUBE-TELCO" in skill_ids
    assert "SKL-MOB-FLEET" in skill_ids
    assert "SKL-RESIL-DR" in skill_ids

    for s in res["data"]:
        assert "title" in s
        assert "domain" in s
        assert "criticality" in s
        assert "keywords" in s
        assert isinstance(s["keywords"], list)


def test_list_skills_filtering():
    res_sec = list_skills(domain="security-cryptography")
    assert res_sec["status"] == "ok"
    assert res_sec["count"] >= 1
    for s in res_sec["data"]:
        assert s["domain"] == "security-cryptography"


def test_get_skills_matrix_contract():
    res = get_skills_matrix(engagement="nordwave-mcx-2027")
    assert res["status"] == "ok"
    data = res["data"]
    assert "coverage_percentage" in data
    assert "risk_level" in data
    assert "total_required_skills" in data
    assert "covered_skills_count" in data
    assert "missing_skills" in data
    assert "sections" in data
    assert data["total_required_skills"] >= 8
    assert data["coverage_percentage"] >= 70.0
