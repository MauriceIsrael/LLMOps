"""Promotion never validates a clause (#101): unchanged clauses keep their decision, the others are drafts."""

from pipelines.doctrine.checks import aggregate_checks_status, parse_checks
from pipelines.kb_candidates.clauses import carry_clause_decisions

RULE = {"kind": "forbids", "when": {"terms_any": ["no backup"]}, "message": "Backups are required."}


def test_new_clauses_are_drafts_whatever_the_content_says():
    fm = {"checks": [{"id": "X-C1", **RULE, "status": "validated"}], "checks_status": "validated"}
    carry_clause_decisions(fm, None)
    assert fm["checks"][0]["status"] == "draft" and fm["checks_status"] == "draft"


def test_an_unchanged_clause_keeps_its_decision_and_a_modified_one_returns_to_draft():
    review = {"by": "@security-compliance-team", "at": "2026-10-12T10:00:00Z", "decision": "validate"}
    previous = {"checks": [{"id": "X-C1", **RULE, "status": "validated", "review": review},
                           {"id": "X-C2", **RULE, "status": "validated", "review": review}]}
    fm = {"checks": [{"id": "X-C1", **RULE}, {"id": "X-C2", **RULE, "message": "Changed."}, {"id": "X-C3", **RULE}]}
    carry_clause_decisions(fm, previous)
    assert [(c["status"], "review" in c) for c in fm["checks"]] == [("validated", True), ("draft", False), ("draft", False)]
    assert fm["checks_status"] == "partial"


def test_inherited_status_of_legacy_assets_is_kept():
    previous = {"checks": [{"id": "X-C1", **RULE}], "checks_status": "validated"}  # before contract 1.26
    fm = {"checks": [{"id": "X-C1", **RULE}]}
    carry_clause_decisions(fm, previous)
    assert fm["checks"][0]["status"] == "validated" and fm["checks_status"] == "validated"


def test_per_clause_status_drives_the_judge():
    raw = [{"id": "X-C1", **RULE, "status": "validated"}, {"id": "X-C2", **RULE, "status": "rejected"},
           {"id": "X-C3", **RULE}]
    assert [(c.id, c.status) for c in parse_checks(raw, "draft")] == [("X-C1", "validated"), ("X-C3", "draft")]
    assert aggregate_checks_status(raw) == "partial"
