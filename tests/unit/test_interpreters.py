"""Interpreters of the intake flow: passthrough by default, scripted when an engagement ships a script."""

from pathlib import Path

import yaml

from tools.elicitation.interpreters import (
    PassthroughInterpreter,
    ScriptedInterpreter,
    get_interpreter,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "elicitation" / "verbatim_statement_script.yaml"


def test_passthrough_is_the_default_and_invents_nothing(monkeypatch, tmp_path):
    monkeypatch.setenv("LLMOPS_EXAMPLES_DIR", str(tmp_path))
    interpreter = get_interpreter("any-engagement")
    assert isinstance(interpreter, PassthroughInterpreter)
    res = interpreter.interpret({
        "answer_text": "  We would use two sites.  ", "engagement": "any-engagement", "author": "alice", "role": "arch",
        "question": {"id": "Q-1", "subject": "storage"},
    })
    assert res["candidate_statements"] == []
    assert res["advance_level_to"] is None
    assert res["uncertainties"] == [{
        "engagement": "any-engagement", "subject": "storage", "text": "We would use two sites.",
        "author": "alice", "role": "arch", "question_id": "Q-1",
    }]
    assert PassthroughInterpreter().interpret({"answer_text": " ", "engagement": "e"})["uncertainties"] == []


def test_scripted_interpreter_is_used_when_the_engagement_ships_a_script(scripted_interpretation):
    scripted_interpretation("eng-with-script")
    assert isinstance(get_interpreter("eng-with-script"), ScriptedInterpreter)


def test_scripted_rules_uncertainties_and_fallback(tmp_path):
    script = {
        "defaults": {"section": "1", "subject": "platform", "author": "bob", "role": "architect"},
        "rules": [{
            "name": "sites",
            "when_any": ["two sites"],
            "statements": [{"subject": "platform", "predicate": "has_property", "value": "2 sites"}],
            "uncertainties": [{"when_any": ["not sure"], "text": "Site count to confirm"}],
            "advance_level_to": "L1_framed",
            "created_subjects": ["site-a"],
        }],
        "fallback": {"statements": [{"value": "$verbatim80"}]},
    }
    path = tmp_path / "script.yaml"
    path.write_text(yaml.safe_dump(script))
    interp = ScriptedInterpreter.from_file(path)
    res = interp.interpret({"answer_text": "Two   sites, not sure", "engagement": "e", "question": {"id": "Q-2"}})
    assert res["candidate_statements"][0]["value"] == "2 sites"
    assert res["candidate_statements"][0]["author"] == "bob"
    assert res["uncertainties"] == [{"engagement": "e", "subject": "platform", "text": "Site count to confirm"}]
    assert res["created_subjects"] == ["site-a"] and res["advance_level_to"] == "L1_framed"
    fallback = interp.interpret({"answer_text": "Something else", "engagement": "e", "question": {"id": "Q-3"}})
    assert fallback["candidate_statements"][0]["value"] == "Something else"
    assert fallback["candidate_statements"][0]["section"] == "1"


def test_fixture_script_is_valid():
    assert ScriptedInterpreter.from_file(FIXTURE).fallback
