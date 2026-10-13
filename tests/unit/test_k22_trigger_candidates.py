"""K22 (ADR-KH-01 A10): trigger rules and facts-vocabulary keys in the candidate cycle, extracted by a model, reviewed by people."""

import json
import shutil
from pathlib import Path

import pytest
import yaml
from starlette.testclient import TestClient

from mcp_server.core.config import server_config
from pipelines import triggers
from pipelines.engagement import facts as fact_module
from pipelines.kb_candidates import rules as rule_candidates
from pipelines.kb_candidates.model import CandidateError
from pipelines.kb_candidates.repository import FileCandidateRepository
from pipelines.kb_candidates.service import CandidateService, CandidateStateError
from pipelines.trigger_extraction import extract_triggers

ROOT = Path(__file__).resolve().parents[2]
RULE = yaml.safe_load((ROOT / "data/kb/triggers/TRG-multisite-replication.yaml").read_text(encoding="utf-8"))
KEY = {"key": "data.rpo_class", "type": "enum", "values": ["zero", "minutes", "hours"],
       "label": {"fr": "Classe de RPO", "en": "RPO class"}}


@pytest.fixture
def kb(tmp_path):
    target = tmp_path / "kb"
    shutil.copytree(ROOT / "data/kb", target)
    return target


@pytest.fixture
def service(kb, tmp_path):
    return CandidateService(repository=FileCandidateRepository(tmp_path / "candidates"), kb_dir=kb,
                            notify_owner=lambda *a: [], notify_consumers=lambda *a: [])


def dump(doc):
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=1000, default_flow_style=None)


def submit(service, doc, asset_type="trigger", **over):
    title = f"Trigger {doc['trigger_id']}" if asset_type == "trigger" else f"Fact key {doc['key']}"
    payload = {"kind": "new_asset", "asset_type": asset_type, "title": title, "proposed_content": dump(doc),
               "source": {"system": "kb-extraction", "production_mode": "llm-derived"}, **over}
    return service.submit(payload, actor="kb-extraction")


def new_rule(**over):
    return {**RULE, "trigger_id": "TRG-active-passive-failover", "when": [{"key": "topology.mode", "op": "eq", "value": "active-passive"}],
            "question": {"fr": "Comment la bascule est-elle déclenchée ?", "en": "How is the failover triggered?"}, **over}


def schema_check(c):
    return next(x for x in c["checks"] if x["name"] == "schema")


# --- the cycle ------------------------------------------------------------------------------------------------------


def test_a_valid_rule_candidate_goes_to_review_and_nothing_is_published(service, kb):
    c = submit(service, new_rule())
    assert c["status"] == "in_review" and schema_check(c)["status"] == "pass"
    assert {x["name"] for x in c["checks"]} == {"schema", "anonymization", "llm_unreviewed", "previously_rejected"}
    assert any(x["name"] == "llm_unreviewed" and x["status"] == "warn" for x in c["checks"])
    assert not (kb / "triggers/TRG-active-passive-failover.yaml").exists()  # a candidate is not knowledge


def test_a_rule_citing_an_unknown_key_fails_with_the_path_of_the_key(service):
    c = submit(service, new_rule(when=[{"key": "topology.sites", "op": "eq", "value": 2}]))
    assert c["status"] == "checks_failed"
    assert "when[0].key [UNKNOWN_FACT_KEY]" in schema_check(c)["detail"]


@pytest.mark.parametrize("mutation,expected", [
    ({"asset": "NO-SUCH-ASSET"}, "UNKNOWN_ASSET"),
    ({"when": [{"key": "topology.dc_count", "op": "gte", "value": "2"}]}, "VALUE_TYPE"),
    ({"trigger_id": "TRG-multisite-replication"}, "EXISTS"),  # exists: an amendment is needed
    ({"initial_level": "L4_specified"}, "LEVEL"),
])
def test_the_schema_check_is_the_k19_validator(service, mutation, expected):
    assert expected in schema_check(submit(service, new_rule(**mutation)))["detail"]


def test_accepting_and_promoting_writes_the_rule_and_publication_records_its_version(service, kb):
    c = submit(service, new_rule())
    service.review(c["id"], "accept", "@maintainers")
    promoted = service.promote(c["id"])
    path = kb / "triggers/TRG-active-passive-failover.yaml"
    assert Path(promoted["promoted"]["path"]) == path and yaml.safe_load(path.read_text(encoding="utf-8"))["version"] == 1
    assert [r["trigger_id"] for r in triggers.load_all(kb) if r["trigger_id"] == "TRG-active-passive-failover"]  # now a valid rule of the base
    assert service.get(c["id"])["source"]["production_mode"] == "llm-proposed-human-approved"


def test_an_amendment_of_a_rule_must_raise_its_version_by_one(service, kb):
    amended = {**RULE, "question": {**RULE["question"], "en": "Which replication strategy, for which RPO class?"}}
    bad = submit(service, amended, kind="amendment", target_asset_id=RULE["trigger_id"])
    assert bad["status"] == "checks_failed" and "must be version 2" in schema_check(bad)["detail"]
    good = submit(service, {**amended, "version": 2}, kind="amendment", target_asset_id=RULE["trigger_id"])
    assert good["status"] == "in_review"
    service.review(good["id"], "accept", "@maintainers")
    service.promote(good["id"])
    assert yaml.safe_load((kb / "triggers/TRG-multisite-replication.yaml").read_text(encoding="utf-8"))["version"] == 2


def test_a_rejected_rule_is_not_published(service, kb):
    c = submit(service, new_rule())
    service.review(c["id"], "reject", "@maintainers", reason="Not a general rule")
    with pytest.raises(CandidateStateError):
        service.promote(c["id"])
    assert not (kb / "triggers/TRG-active-passive-failover.yaml").exists()


# --- vocabulary keys ------------------------------------------------------------------------------------------------


def test_a_new_key_is_reviewed_and_promoting_it_raises_the_vocabulary_version(service, kb):
    before = fact_module.load(kb / "vocabulary/facts.yaml")["version"]
    c = submit(service, KEY, asset_type="fact_key")
    assert c["status"] == "in_review" and "data.rpo_class" in schema_check(c)["detail"]
    service.review(c["id"], "accept", "@maintainers")
    service.promote(c["id"])
    voc = fact_module.load(kb / "vocabulary/facts.yaml")
    assert voc["version"] == before + 1 and voc["keys"]["data.rpo_class"]["values"] == ["zero", "minutes", "hours"]
    assert (kb / "vocabulary/facts.yaml").read_text(encoding="utf-8").startswith("# Vocabulary of architecture facts")  # the header survives
    assert set(voc["keys"]) >= {"topology.dc_count", "hosting.sovereignty"}  # nothing else changed


@pytest.mark.parametrize("doc,expected", [
    ({**KEY, "key": "topology.dc_count"}, "already exists"),
    ({**KEY, "type": "float"}, "type"),
    ({**KEY, "values": []}, "enum"),
    ({"key": "bad", "type": "int", "label": {"fr": "a", "en": "b"}}, "domain.name"),
])
def test_a_bad_key_is_refused(service, doc, expected):
    c = submit(service, doc, asset_type="fact_key")
    assert c["status"] == "checks_failed" and expected in schema_check(c)["detail"]


def test_a_key_cannot_change_type_by_amendment(service):
    c = submit(service, {**KEY, "key": "topology.dc_count", "type": "bool"}, asset_type="fact_key", kind="amendment", target_asset_id="topology.dc_count")
    assert c["status"] == "checks_failed" and "cannot change" in schema_check(c)["detail"]


def test_a_key_is_merged_into_an_existing_one_and_the_rules_that_cite_it_come_back_rewritten(monkeypatch, service, kb):
    from mcp_server.knowledge import tools

    monkeypatch.setattr(server_config, "kb_dir", kb)
    monkeypatch.setattr(tools, "_candidate_service", lambda: service)
    monkeypatch.setattr("mcp_server.core.auth.has_scope", lambda *a, **k: True)
    monkeypatch.setattr("mcp_server.core.auth.delegated_actor_email", lambda *a, **k: None)  # no acting person leaks in from another test
    key = submit(service, {**KEY, "key": "topology.site_count", "type": "int"}, asset_type="fact_key")
    rule = submit(service, new_rule(when=[{"key": "topology.site_count", "op": "gte", "value": 2}]))
    assert rule["status"] == "checks_failed"
    res = tools.merge_fact_key_candidate(key["id"], "topology.dc_count", "@maintainers", "same notion")
    assert res["status"] == "ok" and res["data"]["merged_into"] == "topology.dc_count"
    assert service.get(key["id"])["status"] == "rejected" and "merged into topology.dc_count" in service.get(key["id"])["review"]["reason"]
    affected = res["data"]["affected_rules"]
    assert [a["id"] for a in affected] == [rule["id"]] and "topology.dc_count" in affected[0]["suggested_content"]
    assert service.get(rule["id"])["status"] == "checks_failed"  # a rule is never changed or accepted as a side effect
    amended = service.review(rule["id"], "amend", "@maintainers", reason="key merged", amended_content=affected[0]["suggested_content"])
    assert amended["status"] == "accepted"
    assert tools.merge_fact_key_candidate(key["id"], "topology.dc_count", "@maintainers")["status"] != "ok"  # already closed
    assert tools.merge_fact_key_candidate(key["id"], "no.such_key", "@maintainers")["status"] == "invalid_argument"


# --- the extraction -------------------------------------------------------------------------------------------------


class FakeLlm:
    """Stands in for the local model: answers per element, records the prompts."""

    def __init__(self, answers):
        self.answers = answers
        self.prompts = []

    def __call__(self, url, payload):
        prompt = payload["messages"][0]["content"]
        self.prompts.append(prompt)
        for needle, rules in self.answers.items():
            if f"Element {needle} " in prompt and 'section "Trade-offs"' in prompt:
                return {"choices": [{"message": {"content": "Here you go:\n" + json.dumps({"rules": rules})}}]}
        return {"choices": [{"message": {"content": json.dumps({"rules": []})}}]}


def proposal(quote, **over):
    return {"slug": "mixed-core-dual-mode", "when": [{"key": "topology.mode", "op": "eq", "value": "active-active"}],
            "question": {"fr": "Comment arbitrer ?", "en": "How is it arbitrated?"}, "rationale": {"fr": "Parce que.", "en": "Because."},
            "initial_level": "L1_framed", "suggested_role": "architect", "mandatory": False, "source_quote": quote, "new_keys": [], **over}


def a_sentence(kb, asset, section):
    text = (next((kb / "patterns").glob(f"{asset}.md"))).read_text(encoding="utf-8")
    body = text.split(f"## {section}")[1].split("\n## ")[0].strip()
    return body.split(". ")[0].strip().rstrip(".") + "."


def test_without_an_endpoint_the_extraction_is_skipped(kb, service, monkeypatch):
    monkeypatch.delenv("LLM_ENDPOINT", raising=False)
    assert extract_triggers(kb, service)["skipped"] is True


def test_a_proposal_becomes_a_candidate_that_cites_its_passage(kb, service):
    quote = a_sentence(kb, "PAT-009", "Trade-offs")
    llm = FakeLlm({"PAT-009": [proposal(quote)]})
    report = extract_triggers(kb, service, asset_id="PAT-009", endpoint="http://llm", post=llm)
    assert report["skipped"] is False and len(report["submitted"]) == 1 and report["dropped"] == []
    c = service.get(report["submitted"][0]["candidate"])
    assert c["status"] == "in_review" and c["source"] == {**c["source"], "system": "kb-extraction", "production_mode": "llm-derived"}
    assert quote.strip().lower()[:40] in c["rationale"].lower() and "PAT-009" in c["rationale"]
    doc = yaml.safe_load(c["proposed_content"])
    assert doc["trigger_id"] == "TRG-mixed-core-dual-mode" and doc["asset"] == "PAT-009" and doc["version"] == 1
    assert "topology.mode: active-active" not in llm.prompts[0] and "- topology.dc_count: int" in llm.prompts[0]  # the vocabulary is in the prompt
    assert not (kb / "triggers/TRG-mixed-core-dual-mode.yaml").exists()  # nothing was published


def test_replaying_the_extraction_creates_nothing_that_exists(kb, service):
    llm = FakeLlm({"PAT-009": [proposal(a_sentence(kb, "PAT-009", "Trade-offs"))]})
    extract_triggers(kb, service, asset_id="PAT-009", endpoint="http://llm", post=llm)
    again = extract_triggers(kb, service, asset_id="PAT-009", endpoint="http://llm", post=llm)
    assert again["submitted"] == [] and len(again["unchanged"]) == 1 and len(service.find()) == 1


def test_a_passage_the_model_invented_is_dropped_and_reported(kb, service):
    llm = FakeLlm({"PAT-009": [proposal("Every site must keep a hot spare.")]})
    report = extract_triggers(kb, service, asset_id="PAT-009", endpoint="http://llm", post=llm)
    assert report["submitted"] == [] and "not a passage" in report["dropped"][0]["reason"] and service.find() == []


def test_an_unknown_key_without_a_definition_is_dropped(kb, service):
    bad = proposal(a_sentence(kb, "PAT-009", "Trade-offs"), when=[{"key": "ops.team_size", "op": "gte", "value": 3}])
    report = extract_triggers(kb, service, asset_id="PAT-009", endpoint="http://llm", post=FakeLlm({"PAT-009": [bad]}))
    assert report["submitted"] == [] and "without a definition" in report["dropped"][0]["reason"]


def test_an_unknown_key_with_a_definition_is_proposed_as_a_key_candidate_and_the_rule_waits_for_it(kb, service):
    rule = proposal(a_sentence(kb, "PAT-009", "Trade-offs"), when=[{"key": "data.rpo_class", "op": "eq", "value": "zero"}], new_keys=[KEY])
    report = extract_triggers(kb, service, asset_id="PAT-009", endpoint="http://llm", post=FakeLlm({"PAT-009": [rule]}))
    assert [k["key"] for k in report["key_candidates"]] == ["data.rpo_class"]
    key = service.get(report["key_candidates"][0]["id"])
    assert key["asset_type"] == "fact_key" and key["status"] == "in_review" and key["source"]["production_mode"] == "llm-derived"
    waiting = service.get(report["submitted"][0]["candidate"])
    assert waiting["status"] == "checks_failed" and "when[0].key [UNKNOWN_FACT_KEY]" in schema_check(waiting)["detail"]
    assert "fact_key" in waiting["rationale"]
    # accepting and promoting the key makes the rule valid when it is amended (a person's act)
    service.review(key["id"], "accept", "@maintainers")
    service.promote(key["id"])
    again = service.review(waiting["id"], "amend", "@maintainers", reason="the key now exists", amended_content=waiting["proposed_content"])
    assert again["status"] == "accepted"


def test_a_dry_run_submits_nothing(kb, service):
    llm = FakeLlm({"PAT-009": [proposal(a_sentence(kb, "PAT-009", "Trade-offs"))]})
    report = extract_triggers(kb, service, asset_id="PAT-009", endpoint="http://llm", post=llm, dry_run=True)
    assert report["submitted"][0]["dry_run"] is True and service.find() == []


# --- the review API: live validation and preview --------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch, kb, service):
    from mcp_server.knowledge import tools

    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setattr(server_config, "kb_dir", kb)
    monkeypatch.setattr(tools, "_candidate_service", lambda: service)
    from mcp_server.main import create_starlette_app

    return TestClient(create_starlette_app(), raise_server_exceptions=False)


H = {"Authorization": "Bearer demo-token"}


def test_live_validation_gives_the_path_of_each_problem(client):
    bad = new_rule(when=[{"key": "topology.sites", "op": "eq", "value": 2}, {"key": "topology.mode", "op": "gte", "value": "x"}])
    res = client.post("/api/knowledge/triggers/validate", headers=H, json={"content": dump(bad)})
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["valid"] is False
    assert {(p["path"], p["code"]) for p in data["problems"]} >= {("when[0].key", "UNKNOWN_FACT_KEY"), ("when[1].op", "OP_TYPE")}
    ok = client.post("/api/knowledge/triggers/validate", headers=H, json={"content": dump(new_rule())}).json()["data"]
    assert ok == {"valid": True, "problems": []}
    key = client.post("/api/knowledge/triggers/validate", headers=H, json={"content": dump(KEY), "asset_type": "fact_key"}).json()["data"]
    assert key["valid"] is True
    assert client.post("/api/knowledge/triggers/validate", headers=H, json={}).status_code == 400


def test_the_list_gives_rules_by_carrier_the_vocabulary_and_the_queue(client, service):
    submit(service, new_rule())
    res = client.get("/api/knowledge/triggers", headers=H)
    assert res.status_code == 200
    data = res.json()["data"]
    carriers = {a["id"]: [r["trigger_id"] for r in a["rules"]] for a in data["assets"]}
    assert "TRG-multisite-replication" in carriers["P-010"] and "TRG-nis2-business-continuity" in carriers["NIS2-ART21-2C"]
    assert {k["key"] for k in data["vocabulary"]["keys"]} >= {"topology.dc_count", "hosting.sovereignty"}
    assert data["candidates"] == []  # the queue is for reviewers: the demo token does not carry kb:review


def test_the_queue_is_listed_for_a_reviewer(monkeypatch, client, service):
    submit(service, new_rule())
    monkeypatch.setattr("mcp_server.core.auth.has_scope", lambda *a, **k: True)
    queue = client.get("/api/knowledge/triggers", headers=H).json()["data"]["candidates"]
    assert [(q["asset_type"], q["status"], q["production_mode"]) for q in queue] == [("trigger", "in_review", "llm-derived")]


def test_the_preview_opens_the_questions_the_engine_would_open(client):
    res = client.post("/api/knowledge/triggers/preview", headers=H, json={"facts": {"topology.dc_count": 2, "topology.mode": "active-active"}})
    assert res.status_code == 200
    data = res.json()["data"]
    assert {r["trigger_id"] for r in data["opens"]} == {"TRG-multisite-replication", "TRG-active-active-split-brain", "TRG-active-active-traffic-failover"}
    split = next(c for c in data["closed"] if c["trigger_id"] == "TRG-multisite-distribution")
    assert split["unsatisfied"] == [{"key": "topology.dc_count", "op": "gte", "value": 3, "current": 2}]


def test_the_preview_refuses_facts_the_vocabulary_does_not_know(client):
    res = client.post("/api/knowledge/triggers/preview", headers=H, json={"facts": {"topology.sites": 2}})
    assert res.status_code == 400 and res.json()["code"] == "UNKNOWN_FACT_KEY"
    assert client.post("/api/knowledge/triggers/preview", headers=H, json={"facts": {"topology.dc_count": "2"}}).json()["code"] == "FACT_TYPE"


def test_a_draft_rule_under_review_can_be_previewed_beside_the_reference_rules(client):
    draft = dump(new_rule())
    res = client.post("/api/knowledge/triggers/preview", headers=H, json={"facts": {"topology.mode": "active-passive"}, "rules": [draft, dump(new_rule(trigger_id="TRG-bad", asset="NOPE"))]})
    data = res.json()["data"]
    assert [(r["trigger_id"], r["scope"]) for r in data["opens"]] == [("TRG-active-passive-failover", "draft")]
    assert data["invalid_drafts"][0]["trigger_id"] == "TRG-bad"


def test_the_preview_and_the_cascade_engine_give_the_same_result(client, tmp_path, monkeypatch):
    """The acceptance criterion of K22: same facts, same rules, same questions opened by the preview and by the engine."""
    from mcp_server.core.db import get_engagement_path  # noqa: F401
    from pipelines.engagement.cascade import Cascade, effective_rules
    from tools.elicitation.repository import ElicitationRepository

    facts = {"topology.dc_count": 3, "topology.mode": "active-active", "hosting.sovereignty": "eu"}
    preview = client.post("/api/knowledge/triggers/preview", headers=H, json={"facts": facts}).json()["data"]
    snapshot = json.loads((ROOT / "data/snapshots/latest.json").read_text(encoding="utf-8"))
    rules, _ = effective_rules(snapshot, [])
    opened, _ = triggers.evaluate(list(rules.values()), facts)
    assert [r["trigger_id"] for r in opened] == [r["trigger_id"] for r in preview["opens"]]
    # and the engine itself, on an engagement whose asserted decision carries the same facts
    class Access:
        def get_pin(self, e): return {"snapshot_id": snapshot["snapshot_id"], "checksum": snapshot["payload_sha256"]}
        def audit(self, *a, **k): pass
    snaps = tmp_path / "snaps"
    snaps.mkdir()
    shutil.copy(ROOT / "data/snapshots/latest.json", snaps / "latest.json")
    repo = ElicitationRepository(db_path=tmp_path / "e.lbug")
    try:
        repo.save_subject("topo", engagement="e")
        repo.save_decision({"id": "D-1", "engagement": "e", "subject": "topo", "decision": "x", "rationale": "x", "status": "active",
                            "facts": [{"key": k, "value": v, "source_excerpt": "x"} for k, v in facts.items()], "author": "@a", "origin": "human"})
        Cascade(repo, Access(), "e", snaps, "@a").run()
        engine = {d["trigger_id"] for d in repo.list_derived_subjects("e")}
    finally:
        repo.close()
    assert engine == {r["trigger_id"] for r in preview["opens"]}


def test_a_candidate_cannot_be_submitted_without_a_rule_or_key_shape(service):
    with pytest.raises(CandidateError):
        service.submit({"kind": "new_asset", "asset_type": "invented", "title": "x", "proposed_content": "x", "source": {"system": "mcp"}})
    c = service.submit({"kind": "new_asset", "asset_type": "trigger", "title": "x", "proposed_content": "just words",
                        "source": {"system": "mcp"}})
    assert c["status"] == "checks_failed" and "YAML" in schema_check(c)["detail"]


def test_a_rule_text_with_an_ip_address_is_refused_like_any_candidate(service):
    c = submit(service, new_rule(rationale={"fr": "Voir 10.20.30.40", "en": "See 10.20.30.40"}))
    assert c["status"] == "checks_failed" and any(x["name"] == "anonymization" and x["status"] == "fail" for x in c["checks"])


def test_rule_candidates_helpers():
    assert rule_candidates.keys_of(dump(RULE)) == {"topology.dc_count"}
    assert "topology.mode" in rule_candidates.rewrite_key(dump(RULE), "topology.dc_count", "topology.mode")
