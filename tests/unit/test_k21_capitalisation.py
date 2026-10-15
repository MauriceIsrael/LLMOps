# ruff: noqa: F811  (the K21 harness fixture is imported, then used as a parameter)
"""K21 point 4: a useful local rule is proposed to the reference base through the proposals channel (K7), without any anchor (K13)."""

import copy
import shutil
from pathlib import Path

import yaml

from pipelines.kb_candidates.proposals import import_snapshot, verify
from pipelines.kb_candidates.repository import FileCandidateRepository
from pipelines.kb_candidates.service import CandidateService
from tests.unit.test_k21_rule_adjustments import (  # noqa: F401, F811 - the K21 harness (fixtures)
    BASE,
    ENG,
    LOCAL,
    as_,
    client,
    decide,
)

ROOT = Path(__file__).resolve().parents[2]


def asserted(client, **over):
    decide(client)
    rule = {**copy.deepcopy(LOCAL), **over}
    assert client.post(f"{BASE}/rules", headers=as_("decider"), json=rule).status_code == 201
    assert client.post(f"{BASE}/rules/{rule['trigger_id']}/assert", headers=as_("admin")).status_code == 200
    return rule


def capitalise(client, rule, role="decider", asset="PAT-001"):
    return client.post(f"{BASE}/rules/{rule['trigger_id']}/capitalise", headers=as_(role), json={"asset": asset})


def test_an_asserted_local_rule_gives_a_sealed_snapshot_of_proposals_without_anchor(client):
    rule = asserted(client)
    res = capitalise(client, rule)
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    env = data["snapshot"]
    assert verify(env) == [] and env["sourceSystem"] == "hub-engagement" and data["proposed_as"] == "TRG-ptp-holdover"
    proposal = env["data"]["candidates"][0]["proposal"]
    assert proposal["asset_type"] == "trigger" and proposal["production_mode"] == "human-authored"
    doc = yaml.safe_load(proposal["proposed_content"])
    assert doc["trigger_id"] == "TRG-ptp-holdover"  # the programme's name for it ("local") is gone
    text = str(env)
    assert ENG not in text and not any(h in text for h in ("@dan", "@carl", "@ada", "example.org"))
    assert capitalise(client, rule).json()["data"]["snapshot"] == env  # same rule, same snapshot: reading it twice creates one candidate


def test_a_reference_rule_needs_a_carrier(client):
    rule = asserted(client)
    res = client.post(f"{BASE}/rules/{rule['trigger_id']}/capitalise", headers=as_("decider"), json={})
    assert res.status_code == 400 and res.json()["code"] == "asset_required"
    assert capitalise(client, rule, asset="NOT-AN-ASSET").json()["error"] == "UNKNOWN_ASSET"


def test_only_an_asserted_rule_is_proposed_and_only_by_a_decider(client):
    decide(client)
    client.post(f"{BASE}/rules", headers=as_("decider"), json=LOCAL)
    refused = capitalise(client, LOCAL)
    assert refused.status_code == 409 and refused.json()["error"] == "not_asserted"
    client.post(f"{BASE}/rules/{LOCAL['trigger_id']}/assert", headers=as_("admin"))
    assert capitalise(client, LOCAL, role="contributor").status_code == 403
    assert capitalise(client, LOCAL, role="reader").status_code == 403
    assert capitalise(client, LOCAL).status_code == 200
    events = client.get(f"{BASE}/audit", headers=as_("admin")).json()["data"]["events"]
    assert any(e["action"] == "rule_capitalise" for e in events)


def test_a_programme_anchor_in_the_text_is_refused_and_named(client):  # mutation, as in K13
    for text, kind in ((f"Required by {ENG}.", "engagement identifier"), ("Decided with @dan.", "member handle"),
                       ("Ask jane.doe@client-corp.example.", "e-mail")):
        client.post(f"{BASE}/rules/TRG-local-ptp-holdover/withdraw", headers=as_("admin"))
        mutated = {**LOCAL, "rationale": {"fr": text, "en": text}}
        assert client.post(f"{BASE}/rules", headers=as_("decider"), json=mutated).status_code == 201
        client.post(f"{BASE}/rules/{LOCAL['trigger_id']}/assert", headers=as_("admin"))
        refused = capitalise(client, LOCAL)
        assert refused.status_code == 409 and refused.json()["error"] == "anchors_found", refused.text
        assert kind in refused.json()["reason"]


def test_the_snapshot_enters_the_candidate_cycle_and_waits_for_a_person(client, tmp_path):
    rule = asserted(client)
    env = capitalise(client, rule).json()["data"]["snapshot"]
    kb = tmp_path / "kb"
    shutil.copytree(ROOT / "data/kb", kb)
    service = CandidateService(repository=FileCandidateRepository(tmp_path / "candidates"), kb_dir=kb,
                               notify_owner=lambda *a: [], notify_consumers=lambda *a: [])
    res = import_snapshot(service, env, actor="@maintainer")
    candidate = service.get(res["imported"][0]["id"])
    assert candidate["asset_type"] == "trigger" and candidate["status"] in ("in_review", "checks_failed")
    checks = {c["name"]: c["status"] for c in candidate["checks"]}
    assert checks["anonymization"] == "pass" and checks["schema"] == "pass"
    assert candidate["source"]["system"] == "hub-engagement"
