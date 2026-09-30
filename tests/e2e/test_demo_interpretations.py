"""The reference demo's scripted interpretations reproduce the scenario unchanged.

The expected outputs below are the ones the engine produced when the scenario was
hard-coded in tools/elicitation/flows/intake.py (before plan L3 §6.4).
"""

from pathlib import Path

from tools.elicitation.interpreters import ScriptedInterpreter, get_interpreter

ENGAGEMENT = "nordwave-mcx-2027"
SCRIPT = Path(__file__).parent.parent.parent / "examples" / ENGAGEMENT / "scripted_interpretations.yaml"


def _state(text, **extra):
    return {"answer_text": text, "engagement": ENGAGEMENT, "question": {"id": "Q-0002", "section": "4.1"}, **extra}


def test_demo_engagement_uses_its_script():
    assert isinstance(get_interpreter(ENGAGEMENT), ScriptedInterpreter)


def test_act2_framing():
    text = "The MCX layer delivers group voice. Boundary is 3GPP MC service layer. I do not yet know the platform."
    res = ScriptedInterpreter.from_file(SCRIPT).interpret(_state(text))
    assert [(s["subject"], s["predicate"], s["value"], s["confidence"]) for s in res["candidate_statements"]] == [
        ("mcx-services", "is_constrained_by", "3GPP MC service layer boundary", "designed"),
        ("mcx-services", "has_property", "group voice must survive site isolation from national data centres",
         "stated-by-client"),
    ]
    assert res["candidate_statements"][0]["author"] == "Amina Duarte"
    assert res["candidate_statements"][0]["role"] == "mcx-service-architect"
    assert res["advance_level_to"] == "L1_framed"
    assert res["uncertainties"] == [{
        "engagement": ENGAGEMENT, "subject": "mcx-services",
        "text": "I do not yet know whether the platform we shortlist can do it without a local instance",
    }]


def test_act3_decomposition():
    res = ScriptedInterpreter.from_file(SCRIPT).interpret(_state("It splits in four parts."))
    assert res["candidate_statements"][0]["predicate"] == "decomposes_into"
    assert res["created_subjects"] == ["group-management", "floor-control", "media-distribution", "lmr-interworking"]
    assert res["advance_level_to"] == "L2_decomposed"
    assert res["candidate_patterns"][0]["id"] == "PAT-006"
    assert res["no_pattern_for_decomposition"] is True


def test_act2b_mobile_core_matches_the_raw_answer():
    res = ScriptedInterpreter.from_file(SCRIPT).interpret(_state("A dedicated 5G\nstandalone core? The mobile core, yes."))
    stmt = res["candidate_statements"][0]
    assert (stmt["section"], stmt["subject"]) == ("5.1", "mobile-core")
    assert res["advance_level_to"] == "L1_framed"


def test_other_answers_fall_back_to_one_statement():
    text = "x" * 100
    res = ScriptedInterpreter.from_file(SCRIPT).interpret(_state(text, question={"id": "Q-9", "section": "7.2", "subject": "transport"}))
    stmt = res["candidate_statements"][0]
    assert (stmt["section"], stmt["subject"], stmt["value"]) == ("7.2", "transport", "x" * 80)
    assert res["advance_level_to"] is None
