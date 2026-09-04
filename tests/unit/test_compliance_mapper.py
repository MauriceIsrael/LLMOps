"""Unit tests for compliance mapper, regulatory control detection and gap auditing."""

from pipelines.compliance_mapper import (
    audit_compliance_gaps,
    load_all_controls,
    match_text_to_controls,
)


def test_load_all_controls():
    controls = load_all_controls("data/kb/controls")
    assert len(controls) == 27
    assert "SNC-REQ-01" in controls
    assert "ISO-27001-A8-09" in controls
    assert "NIS2-ART21-2A" in controls
    assert "3GPP-TS33501-SBI" in controls

    snc_01 = controls["SNC-REQ-01"]
    assert snc_01.framework == "SecNumCloud"
    assert "sovereignty-boundary" in snc_01.terms


def test_match_text_to_controls_sovereignty():
    title = "Local LLM inference within the trust boundary"
    text = "Deploying local models on general-purpose CPUs ensures data localization and protection against Cloud Act extraterritoriality."
    matches = match_text_to_controls(title=title, text=text, threshold=0.35)
    matched_ids = [m.control_id for m in matches]

    assert "SNC-REQ-01" in matched_ids


def test_match_text_to_controls_hsm():
    title = "Hardware security module and KMS envelope encryption"
    text = "All root-of-trust secrets and crypto keys must be managed in a qualified HSM."
    matches = match_text_to_controls(title=title, text=text, threshold=0.35)
    matched_ids = [m.control_id for m in matches]

    assert "SNC-REQ-03" in matched_ids
    assert any(m.control_id in ("ISO-27001-A8-24", "SNC-REQ-03") for m in matches)


def test_match_text_to_controls_gitops():
    title = "GitOps configuration controller"
    text = "Continuous drift detection ensuring Git remains the single source of truth for platform states."
    matches = match_text_to_controls(title=title, text=text, threshold=0.35)
    matched_ids = [m.control_id for m in matches]

    assert "ISO-27001-A8-09" in matched_ids


def test_audit_compliance_gaps_100_percent():
    report = audit_compliance_gaps("data/kb")
    assert report["global_total"] == 27
    assert report["global_covered"] == 27
    assert report["global_coverage_percentage"] == 100.0

    fw = report["frameworks"]
    assert fw["NIS2"]["uncovered"] == 0
    assert fw["SecNumCloud"]["uncovered"] == 0
    assert fw["ISO27001"]["uncovered"] == 0
    assert fw["3GPP"]["uncovered"] == 0
