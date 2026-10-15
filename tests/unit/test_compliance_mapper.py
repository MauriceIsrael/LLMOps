"""Unit tests for compliance mapper, regulatory control detection and gap auditing."""

from pipelines.compliance_mapper import (
    audit_compliance_gaps,
    load_all_controls,
    match_text_to_controls,
)

HAND_CURATED_CONTROLS = 62  # the controls the base held before any framework was ingested from a source; it only grows


def test_load_all_controls():
    controls = load_all_controls("data/kb/controls")
    # A floor, not an exact count: every framework ingestion (`kb ingest-framework`) adds controls to the base.
    assert len(controls) >= HAND_CURATED_CONTROLS
    assert "SNC-REQ-01" in controls
    assert "ISO-27001-A8-09" in controls
    assert "NIS2-ART21-2A" in controls
    assert "3GPP-TS33501-SBI" in controls
    assert "CER-ART13-RESIL" in controls
    assert "CRA-REQ-VULN-01" in controls
    assert "TELCO-RESIL-PTP-01" in controls
    assert "PPDR-RADIO-B68" in controls

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
    """Every hand-curated control is implemented by a KB asset; only controls ingested from a source can still be unlinked."""
    controls = load_all_controls("data/kb/controls")
    report = audit_compliance_gaps("data/kb")
    fw = report["frameworks"]

    uncovered = {c["id"] for f in fw.values() for c in f["controls"] if not c["covered"]}
    curated = {cid for cid, c in controls.items() if not c.from_source}
    assert curated, "no hand-curated control left to check"
    assert not (uncovered & curated), f"hand-curated controls without an implementing asset: {sorted(uncovered & curated)}"

    # The report accounts for every control, once.
    assert report["global_total"] == len(controls)
    assert report["global_covered"] == len(controls) - len(uncovered)

    # The 9 NIS2 requirements published by the first full ingestion are not yet implemented by a KB asset.
    nis2_unlinked = {"NIS2-ART20-1", "NIS2-ART20-2", "NIS2-ART21-1", "NIS2-ART21-3", "NIS2-ART21-4",
                     "NIS2-ART23-1", "NIS2-ART23-2", "NIS2-ART23-3", "NIS2-ART23-4"}
    assert {c["id"] for c in fw["NIS2"]["controls"] if not c["covered"]} == nis2_unlinked

    # Frameworks that were fully curated stay fully covered.
    for name in ("SecNumCloud", "ISO27001", "3GPP", "CER", "GSMA", "TELCO-RESIL", "PPDR-DEVICE"):
        assert fw[name]["uncovered"] == 0, name


# --- Controls ingested from a source are matched on their legal text -------------------------------

INGESTED = """---
id: NIS2-ART23-4
title: Reporting obligations
type: control
framework: NIS2
version: "2022/2555"
domain: [security-governance]
severity: mandatory
status: active
---

# NIS2-ART23-4

## Legal Requirement
Entities shall submit an early warning within 24 hours of becoming aware of the significant incident, an incident notification within 72 hours, and a final report not later than one month after the incident notification.

## Architecture Acceptance Criteria
_To be proposed._
"""
CURATED = """---
id: NIS2-ART21-2B
title: Incident handling
type: control
framework: NIS2
version: "2022/2555"
domain: [security-governance]
severity: mandatory
status: active
terms: [incident-handling]
---

# NIS2-ART21-2B

## Legal Requirement
Incident handling.
"""


def _controls(tmp_path):
    d = tmp_path / "controls" / "NIS2"
    d.mkdir(parents=True)
    (d / "NIS2-ART23-4.md").write_text(INGESTED, encoding="utf-8")
    (d / "NIS2-ART21-2B.md").write_text(CURATED, encoding="utf-8")
    return load_all_controls(tmp_path / "controls")


def test_ingested_control_is_matched_on_its_legal_text(tmp_path):
    controls = _controls(tmp_path)
    text = ("The supplier shall issue an early warning of any significant incident within 24 hours, "
            "an incident notification within 72 hours and a final report within one month.")
    ids = [m.control_id for m in match_text_to_controls("Incident handling", text, controls=controls, threshold=0.30)]
    assert "NIS2-ART23-4" in ids
    match = next(m for m in match_text_to_controls("Incident handling", text, controls=controls, threshold=0.30)
                 if m.control_id == "NIS2-ART23-4")
    assert any(k.startswith("legal:") for k in match.matched_keywords)


def test_unrelated_text_does_not_match_the_ingested_control(tmp_path):
    controls = _controls(tmp_path)
    text = "The supplier shall provide a user manual, a training plan and a delivery calendar for the new building."
    assert match_text_to_controls("Deliverables", text, controls=controls, threshold=0.30) == []


def test_function_words_alone_do_not_match(tmp_path):
    controls = _controls(tmp_path)
    assert match_text_to_controls("x", "the of and to in shall be within", controls=controls, threshold=0.30) == []


def test_curated_control_matching_is_unchanged(tmp_path):
    controls = _controls(tmp_path)
    # A curated control (with terms) never gets a legal-text score: only its terms count.
    text = "Incident handling with early warning within 24 hours and incident notification within 72 hours"
    scores = {m.control_id: m.matched_keywords for m in match_text_to_controls("t", text, controls=controls, threshold=0.0)}
    assert not any(k.startswith("legal:") for k in scores.get("NIS2-ART21-2B", []))
