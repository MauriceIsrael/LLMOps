"""Grounded prose assistance: knowledge with identifiers and honest confidence, never a fabricated or validating sentence."""

from pipelines.prose_grounding import ground_block


def doctrine_returning(items):
    return lambda **_: {"status": "ok", "data": {"items": items}}


REQUEST = {"blockId": "b", "context": {"anchoredItems": [{"attributes": {"label": "Out-of-band management network"}}]}, "instructions": "Resilience."}


def test_a_draft_cites_the_knowledge_and_states_nothing_about_the_project():
    draft, reason = ground_block(REQUEST, doctrine_returning([{"id": "P-002", "type": "principle", "title": "Human approval", "confidence": "verified", "excerpt": "Automated remediation requires approval."}]))
    assert reason is None and draft
    assert "[P-002] Human approval (principe, vérifié) : Automated remediation requires approval." in draft
    assert "ne démontrent pas" in draft


def test_confidence_is_never_upgraded():
    items = [
        {"id": "V-1", "type": "control", "title": "Vendor claim", "confidence": "vendor-stated", "excerpt": "x"},
        {"id": "A-1", "type": "decision", "title": "Guess", "confidence": "assumed", "excerpt": "y"},
    ]
    draft, _ = ground_block(REQUEST, doctrine_returning(items))
    assert "déclaration constructeur, non vérifiée" in draft and "hypothèse" in draft
    assert "(contrôle, vérifié)" not in draft


def test_no_applicable_knowledge_gives_no_draft():
    draft, reason = ground_block(REQUEST, doctrine_returning([]))
    assert draft is None and "Aucune connaissance applicable" in reason


def test_nothing_to_query_with_gives_no_draft_and_does_not_call_the_base():
    called = []
    draft, reason = ground_block({"blockId": "b", "anchorIds": ["core-5g"]}, lambda **kw: called.append(kw) or {})
    assert draft is None and "Aucun libellé" in reason and not called


def test_a_failing_doctrine_lookup_gives_no_draft():
    draft, reason = ground_block(REQUEST, lambda **_: {"status": "error"})
    assert draft is None and reason
