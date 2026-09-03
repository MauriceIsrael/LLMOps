"""Unit tests for G5_unstaffed_skill_gap and Best-Match routing."""

from tools.elicitation.mailbox.roster import RosterManager
from tools.elicitation.models.blueprint_schema import load_blueprint


def test_roster_manager_skills_and_contractors(tmp_path):
    roster_file = tmp_path / "roster.yaml"
    roster_file.write_text("""
- login: user1
  name: User One
  roles: [cloud-architect]
  skills: [SKL-KUBE-TELCO]
""", encoding="utf-8")

    mgr = RosterManager(engagement="test-eng", roster_path=roster_file)
    assert mgr.get_skills("user1") == ["SKL-KUBE-TELCO"]
    assert "SKL-KUBE-TELCO" in mgr.get_all_covered_skills()
    assert "SKL-CRYPTO-HSM" not in mgr.get_all_covered_skills()

    # Add skill
    ok = mgr.add_skill("user1", "SKL-AUTO-GITOPS", level="expert")
    assert ok is True
    assert "SKL-AUTO-GITOPS" in mgr.get_skills("user1")

    # Contract external expertise
    mgr.contract_expertise(skill_id="SKL-CRYPTO-HSM", provider="Security Vault Ltd", ref="PO-TEST-123")
    assert "SKL-CRYPTO-HSM" in mgr.get_all_covered_skills()
    assert len(mgr.external_contractors) == 1
    assert mgr.external_contractors[0]["provider"] == "Security Vault Ltd"


def test_blueprint_skills_loading():
    bp = load_blueprint("data/kb/blueprints/BLU-hla-mcx.yaml")
    sections_with_skills = [s for s in bp.sections if getattr(s, "required_skills", None)]
    assert len(sections_with_skills) >= 8

    # Section 7.3 must require SKL-CRYPTO-HSM
    sec_73 = next(s for s in bp.sections if s.id == "7.3")
    assert "SKL-CRYPTO-HSM" in sec_73.required_skills
    assert "SKL-SEC-ZEROTRUST" in sec_73.required_skills
