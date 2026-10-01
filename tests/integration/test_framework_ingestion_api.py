"""Framework ingestion through the API (contract 1.7): the L3 offline chain replayed row by row."""

import shutil
from pathlib import Path

import pytest
import yaml
from starlette.testclient import TestClient

from mcp_server.core.config import server_config

ROOT = Path(__file__).parent.parent.parent
EXCERPT = ROOT / "tests" / "fixtures" / "frameworks" / "nis2_excerpt.txt"
CLIENT = {"Authorization": "Bearer archinex-token"}
SEC, MAINT, OTHER = "sec@example.org", "maint@example.org", "bob@example.org"
BASE = "/api/frameworks/ingestions"


def _as(email: str) -> dict:
    return {**CLIENT, "X-Actor-Email": email}


@pytest.fixture
def env(tmp_path, monkeypatch):
    kb = tmp_path / "kb"
    shutil.copytree(ROOT / "data" / "kb", kb)
    owners = yaml.safe_load((kb / "owners.yaml").read_text())
    owners["owners"]["@security-compliance-team"]["email"] = SEC
    owners["owners"]["@ciso-office"]["email"] = OTHER
    owners["owners"]["@maintainers"] = {"email": MAINT, "roles": ["kb:maintain"]}
    (kb / "owners.yaml").write_text(yaml.safe_dump(owners), encoding="utf-8")
    monkeypatch.setattr(server_config, "kb_dir", kb)
    monkeypatch.setenv("CANDIDATES_DIR", str(tmp_path / "candidates"))
    monkeypatch.setenv("SERVER_TOKEN", "demo-token")
    monkeypatch.setenv("ENGAGEMENT_TOKENS", "archinex-token:kb:review,kb:delegate")
    monkeypatch.setenv("CANDIDATES_BACKEND", "sql")
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path / 'gov.db'}")
    monkeypatch.delenv("LLM_ENDPOINT", raising=False)
    import mcp_server.core.notifier as notifier

    monkeypatch.setattr(notifier, "notify_owner", lambda owner, event, c: ["log"])
    monkeypatch.setattr(notifier, "notify_consumers", lambda event, payload: ["log"])
    from pipelines.governance.migrate import migrate_governance
    from pipelines.governance.store import dispose_engines

    dispose_engines()
    migrate_governance(kb, tmp_path / "none", eval_dataset=None)
    from mcp_server.main import create_starlette_app

    yield {"client": TestClient(create_starlette_app()), "kb": kb}
    dispose_engines()


def _upload(client, email=MAINT, **fields):
    data = {"framework": "NIS2", "version": "2022/2555", **fields}
    return client.post(BASE, headers=_as(email), data=data,
                       files={"file": ("nis2_excerpt.txt", EXCERPT.read_bytes(), "text/plain")})


def test_upload_review_apply_declare(env):
    client, kb = env["client"], env["kb"]

    # Upload: maintainers only; the source is split into 19 draft requirements.
    assert _upload(client, email=SEC).status_code == 403
    assert _upload(client, email="eve@example.org").status_code == 403
    assert client.post(BASE, headers=_as(MAINT), data={"framework": "NIS2", "version": "1"}).status_code == 400  # no file
    assert _upload(client, framework="UNKNOWN").status_code == 400
    bad_type = client.post(BASE, headers=_as(MAINT), data={"framework": "NIS2", "version": "1"},
                           files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert bad_type.status_code == 400
    res = _upload(client)
    assert res.status_code == 201, res.text
    ing = res.json()["data"]
    assert ing["total"] == 19 and ing["status"] == "reviewing" and ing["created_by"] == "@maintainers"
    assert ing["source_sha256"] and len(ing["source_sha256"]) == 64
    iid = ing["id"]
    listed = client.get(BASE, headers=CLIENT).json()["data"]
    assert [i["id"] for i in listed["ingestions"]] == [iid] and "NIS2" in listed["splitters"]

    detail = client.get(f"{BASE}/{iid}", headers=CLIENT).json()["data"]
    row = next(r for r in detail["requirements"] if r["requirement_id"] == "NIS2-ART23-4")
    assert "early warning within 24 hours" in row["legal_text"] and row["decision"] == "" and "draft" not in row
    assert client.get(f"{BASE}/999", headers=CLIENT).status_code == 404

    # Proposals from the client's LLM: stored as llm-derived, unknown ids dropped, nothing decided by them.
    prop = client.post(f"{BASE}/{iid}/link-proposals", headers=_as(MAINT), json={"model": "local-llm", "proposals": [
        {"requirement_id": "NIS2-ART21-2B", "satisfied_by": ["P-002", "NOT-AN-ASSET"], "acceptance_criteria": ["Approvals are recorded."]},
        {"requirement_id": "NIS2-NOPE", "satisfied_by": []}]})
    assert prop.json()["data"] == {"updated": 1, "dropped_unknown_links": 1, "unknown_requirements": ["NIS2-NOPE"]}
    assert client.post(f"{BASE}/{iid}/link-proposals", headers=_as(SEC), json={"proposals": []}).status_code == 403

    # Decisions: the reviewer is the acting expert, who must own the domain; unknown links are refused.
    def decide(req, email, body):
        return client.patch(f"{BASE}/{iid}/rows/{req}", headers=_as(email), json=body)

    assert decide("NIS2-ART23-4", OTHER, {"decision": "accept"}).status_code == 403  # does not own security-governance
    assert decide("NIS2-ART23-4", SEC, {"decision": "bogus"}).status_code == 400
    assert decide("NIS2-ART23-4", SEC, {"decision": "amend", "links": ["P-999"], "acceptance_criteria": ["x"]}).status_code == 400
    assert decide("NIS2-ART23-4", SEC, {"decision": "amend"}).status_code == 400
    assert decide("NIS2-NOPE", SEC, {"decision": "accept"}).status_code == 404
    for r in detail["requirements"]:
        if r["requirement_id"] == "NIS2-ART23-4":
            ok = decide(r["requirement_id"], SEC, {
                "decision": "amend", "links": ["P-008"], "comment": "Verified against the OJ",
                "acceptance_criteria": ["Incident notification pipeline meets the 24h/72h/1-month deadlines"]})
            assert ok.status_code == 200 and ok.json()["data"]["reviewer"] == "@security-compliance-team"
        else:
            assert decide(r["requirement_id"], SEC, {"decision": "accept", "comment": "Verified"}).status_code == 200
    assert client.get(f"{BASE}/{iid}", headers=CLIENT).json()["data"]["decided"] == 19

    # Coverage cannot be declared before the requirements are validated.
    refused = client.post("/api/frameworks/NIS2/coverage-declaration", headers=_as(SEC))
    assert refused.status_code == 409 and "cannot be declared covered" in str(refused.json())

    # Apply: maintainers only; same outcome as `kb apply-review`.
    assert client.post(f"{BASE}/{iid}/apply", headers=_as(SEC)).status_code == 403
    applied = client.post(f"{BASE}/{iid}/apply", headers=_as(MAINT))
    assert applied.status_code == 200, applied.text
    out = applied.json()["data"]
    assert len(out["promoted"]) == 19 and out["failed"] == [] and out["status"] == "applied"
    control = (kb / "controls" / "NIS2" / "NIS2-ART23-4.md").read_text(encoding="utf-8")
    fm = yaml.safe_load(control.split("---")[1])
    assert fm["status"] == "active" and fm["validated_by"] == ["@security-compliance-team"]
    assert fm["satisfied_by"] == ["P-008"] and fm["links_production_mode"] == "human-authored"
    llm = yaml.safe_load((kb / "controls" / "NIS2" / "NIS2-ART21-2B.md").read_text().split("---")[1])
    assert llm["links_production_mode"] == "llm-proposed-human-approved" and "P-002" in llm["satisfied_by"]
    assert client.patch(f"{BASE}/{iid}/rows/NIS2-ART23-4", headers=_as(SEC), json={"decision": "accept"}).status_code == 400

    # Coverage declaration by the expert, then the event feed shows the coverage changes.
    declared = client.post("/api/frameworks/NIS2/coverage-declaration", headers=_as(SEC))
    assert declared.status_code == 200 and declared.json()["data"]["status"] == "covered"
    assert declared.json()["data"]["declared_by"] == "@security-compliance-team"
    types = [(e["type"], e["payload"].get("reason")) for e in client.get("/api/knowledge/events", headers=CLIENT).json()["data"]["events"]
             if e["type"] == "coverage.changed"]
    assert types == [("coverage.changed", "ingested"), ("coverage.changed", "declared")]


def test_partial_apply_and_reupload_resets_the_declaration(env):
    client = env["client"]
    iid = _upload(client).json()["data"]["id"]
    assert client.post(f"{BASE}/{iid}/apply", headers=_as(MAINT)).status_code == 400  # nothing decided
    assert client.patch(f"{BASE}/{iid}/rows/NIS2-ART23-4", headers=_as(SEC), json={"decision": "reject", "comment": "Out of scope"}).status_code == 200
    assert client.patch(f"{BASE}/{iid}/rows/NIS2-ART23-4", headers=_as(SEC), json={"decision": ""}).status_code == 200  # cleared
    assert client.patch(f"{BASE}/{iid}/rows/NIS2-ART21-2A", headers=_as(SEC), json={"decision": "accept"}).status_code == 200
    out = client.post(f"{BASE}/{iid}/apply", headers=_as(MAINT)).json()["data"]
    assert out["promoted"] == ["NIS2-ART21-2A"] and out["status"] == "partially_applied"
    # A new version of the source is a new ingestion; the previous one stays readable.
    second = _upload(client, version="2022/2555-rev")
    assert second.status_code == 201 and second.json()["data"]["id"] != iid
    assert len(client.get(BASE, headers=CLIENT).json()["data"]["ingestions"]) == 2


def test_needs_the_governance_database(env, monkeypatch, tmp_path):
    monkeypatch.delenv("GOVERNANCE_DATABASE_URL")
    monkeypatch.setenv("CANDIDATES_BACKEND", "file")
    monkeypatch.setenv("CANDIDATES_DIR", str(tmp_path / "file-queue"))
    assert env["client"].get(BASE, headers=CLIENT).status_code == 503


def test_bilingual_terms_and_french_title_are_proposed_then_applied_by_the_expert(env):
    from pipelines.compliance_mapper import load_all_controls, match_text_to_controls

    client, kb = env["client"], env["kb"]
    iid = _upload(client).json()["data"]["id"]
    curated = yaml.safe_load((kb / "controls" / "NIS2" / "NIS2-ART21-2B.md").read_text().split("---")[1])
    props = client.post(f"{BASE}/{iid}/link-proposals", headers=_as(MAINT), json={"model": "local-llm", "proposals": [
        {"requirement_id": "NIS2-ART23-4", "title_fr": "Obligations de notification des incidents",
         "terms": ["early warning", "alerte précoce", "notification d'incident", "Early  Warning"]},
        {"requirement_id": "NIS2-ART21-2B", "title_fr": "Titre français proposé par le modèle", "terms": ["gestion des incidents"]},
        {"requirement_id": "NIS2-ART20-1", "terms": [f"t{i}" for i in range(25)]}]})
    assert props.status_code == 400  # too many terms
    ok = client.post(f"{BASE}/{iid}/link-proposals", headers=_as(MAINT), json={"model": "local-llm", "proposals": [
        {"requirement_id": "NIS2-ART23-4", "title_fr": "Obligations de notification des incidents",
         "terms": ["early warning", "alerte précoce", "notification d'incident", "Early  Warning"]},
        {"requirement_id": "NIS2-ART21-2B", "title_fr": "Titre français proposé par le modèle", "terms": ["gestion des incidents"]}]})
    assert ok.status_code == 200 and ok.json()["data"]["updated"] == 2
    row = next(r for r in client.get(f"{BASE}/{iid}", headers=CLIENT).json()["data"]["requirements"]
               if r["requirement_id"] == "NIS2-ART23-4")
    assert row["proposed_terms"] == ["early warning", "alerte précoce", "notification d'incident"]  # deduplicated, lower-cased
    assert row["proposed_title_fr"] == "Obligations de notification des incidents" and row["terms"] == []

    def decide(req, body):
        return client.patch(f"{BASE}/{iid}/rows/{req}", headers=_as(SEC), json=body)

    assert decide("NIS2-ART23-4", {"decision": "accept"}).status_code == 200  # the proposal is accepted as it is
    assert decide("NIS2-ART21-2B", {"decision": "amend", "terms": ["traitement des incidents"], "title_fr": "Gestion des incidents"}).status_code == 200
    assert decide("NIS2-ART21-2A", {"decision": "amend"}).status_code == 400  # nothing to amend
    assert decide("NIS2-ART21-2A", {"decision": "amend", "terms": ["x" * 70]}).status_code == 400
    assert client.post(f"{BASE}/{iid}/apply", headers=_as(MAINT)).status_code == 200

    new = yaml.safe_load((kb / "controls" / "NIS2" / "NIS2-ART23-4.md").read_text().split("---")[1])
    assert new["title_fr"] == "Obligations de notification des incidents"
    assert new["terms"] == ["early warning", "alerte précoce", "notification d'incident"]
    assert new["terms_production_mode"] == "llm-proposed-human-approved"  # a model proposed it, a person approved it
    amended = yaml.safe_load((kb / "controls" / "NIS2" / "NIS2-ART21-2B.md").read_text().split("---")[1])
    assert set(curated.get("terms") or []) <= set(amended["terms"]) and "traitement des incidents" in amended["terms"]
    assert "gestion des incidents" not in amended["terms"]  # the expert's own terms replaced the model's proposal
    assert amended["terms_production_mode"] == "human-authored"
    assert amended["title_fr"] == "Gestion des incidents"  # the expert's title; never the model's over a curated one
    assert curated["title_fr"] == "Traitement des incidents"

    # The French terms make the control findable from a French requirement (lexical matching, no model needed).
    controls = load_all_controls(kb / "controls")
    ids = [m.control_id for m in match_text_to_controls(
        "Incidents", "Le titulaire émet une alerte précoce sous 24 heures.", controls=controls, threshold=0.30)]
    assert "NIS2-ART23-4" in ids


def test_a_model_proposed_french_title_never_replaces_a_curated_one(env):
    client, kb = env["client"], env["kb"]
    iid = _upload(client).json()["data"]["id"]
    before = yaml.safe_load((kb / "controls" / "NIS2" / "NIS2-ART21-2C.md").read_text().split("---")[1])
    assert before.get("title_fr")
    client.post(f"{BASE}/{iid}/link-proposals", headers=_as(MAINT), json={"proposals": [
        {"requirement_id": "NIS2-ART21-2C", "title_fr": "Un autre titre", "terms": ["continuité d'activité"]}]})
    client.patch(f"{BASE}/{iid}/rows/NIS2-ART21-2C", headers=_as(SEC), json={"decision": "accept"})
    assert client.post(f"{BASE}/{iid}/apply", headers=_as(MAINT)).status_code == 200
    after = yaml.safe_load((kb / "controls" / "NIS2" / "NIS2-ART21-2C.md").read_text().split("---")[1])
    assert after["title_fr"] == before["title_fr"] and "continuité d'activité" in after["terms"]
