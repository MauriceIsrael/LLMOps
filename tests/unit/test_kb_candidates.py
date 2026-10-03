"""Unit tests — KB candidate cycle: checks, confidence, owners, service transitions.

Everything runs on a synthetic knowledge base written in tmp_path.
"""

from datetime import UTC, date, datetime
from pathlib import Path

import pytest
import yaml

from pipelines.doctrine.checks import parse_checks
from pipelines.doctrine.index import DoctrineEntry, DoctrineIndex
from pipelines.doctrine.text import Vocabulary
from pipelines.kb_candidates.checks import (
    build_context,
    check_anonymization,
    check_doctrine_conflict,
    check_duplicate,
    check_llm_unreviewed,
    check_previously_rejected,
    check_references,
    check_schema,
    find_ip_addresses,
)
from pipelines.kb_candidates.confidence import NotPublishableError, compute_confidence
from pipelines.kb_candidates.model import CandidateError, validate_submission
from pipelines.kb_candidates.owners import load_owners
from pipelines.kb_candidates.repository import FileCandidateRepository, get_repository
from pipelines.kb_candidates.service import (
    CandidateService,
    CandidateStateError,
    business_days_between,
    redact,
)

PRINCIPLE = """---
id: P-001
title: Everything as code
type: principle
status: active
confidence: verified
phase: [BUILD]
domain: [automation]
owner: arch
last_reviewed: 2026-01-01
checks_status: draft
checks:
  - id: P-001-C1
    kind: forbids
    when: {terms_any: [manual change in production]}
    message: No manual change.
---

# P-001 — Everything as code

## Statement
Configurations are versioned.

## How to verify
Check the repository.
"""

CONTROL = """---
id: FW-01
title: Incident handling
type: control
framework: FW
version: "1"
severity: mandatory
status: active
confidence: verified
domain: [security]
---

# FW-01

## Legal Requirement
Handle incidents.

## Architecture Acceptance Criteria
Traceability.
"""

OWNERS = {
    "default_owner": "@maintainers",
    "owners": {h: {"email": None} for h in ("@maintainers", "@arch", "@sec", "@auto")},
    "domains": {"automation": "@auto", "security": "@sec", "it": "@arch"},
}


def new_pattern(pid="PAT-010", extra_fm="", body_extra="", title="Blue green deployment"):
    return f"""---
id: {pid}
title: {title}
type: pattern
phase: [BUILD]
domain: [automation]
related: [P-001]
{extra_fm}---

# {pid} — {title}

## Problem
Releases interrupt the service.

## Solution
Run two environments and switch traffic.

## Trade-offs
Double capacity.

## When not to use this
Stateful monoliths.
{body_extra}"""


@pytest.fixture
def kb(tmp_path: Path) -> Path:
    kb = tmp_path / "kb"
    (kb / "principles").mkdir(parents=True)
    (kb / "controls" / "FW").mkdir(parents=True)
    (kb / "schema").mkdir()
    (kb / "principles" / "P-001.md").write_text(PRINCIPLE)
    (kb / "controls" / "FW" / "FW-01.md").write_text(CONTROL)
    schema = Path("data/kb/schema/frontmatter.schema.json").read_text()
    (kb / "schema" / "frontmatter.schema.json").write_text(schema)
    (kb / "owners.yaml").write_text(yaml.safe_dump(OWNERS))
    (kb / "anonymization_denylist.txt").write_text("# clients\nAcme Telecom\n")
    return kb


def doctrine() -> DoctrineIndex:
    entry = DoctrineEntry(
        id="P-001", type="principle", title="Everything as code", status="active", confidence="verified",
        domain=["automation"], phase=[], source_ref="kb/P-001.md", body="Configurations are versioned.",
        checks=parse_checks([{"id": "P-001-C1", "kind": "forbids", "when": {"terms_any": ["manual change in production"]}}]),
    )
    return DoctrineIndex(entries=[entry], vocabulary=Vocabulary())


def cand(content, kind="new_asset", asset_type="pattern", **extra):
    base = {
        "id": "CAND-20260101-0001", "kind": kind, "asset_type": asset_type, "title": extra.pop("title", "Blue green deployment"),
        "rationale": "", "proposed_content": content, "domain": ["automation"],
        "source": {"system": "archinex", "production_mode": extra.pop("mode", "human-authored")},
        "target_asset_id": extra.pop("target", None), "evidence": [],
    }
    base.update(extra)
    return base


class Recorder:
    def __init__(self):
        self.owner_calls = []
        self.consumer_calls = []

    def owner(self, owner, event, candidate):
        self.owner_calls.append((owner["handle"], event, candidate["id"]))
        return ["log"]

    def consumers(self, event, payload):
        self.consumer_calls.append((event, payload))
        return ["log"]


@pytest.fixture
def recorder():
    return Recorder()


@pytest.fixture
def service(kb, tmp_path, recorder) -> CandidateService:
    return CandidateService(
        repository=FileCandidateRepository(tmp_path / "candidates"),
        kb_dir=kb,
        doctrine_index_loader=doctrine,
        notify_owner=recorder.owner,
        notify_consumers=recorder.consumers,
    )


def submission(content, **overrides):
    payload = {
        "kind": "new_asset", "asset_type": "pattern", "title": "Blue green deployment", "proposed_content": content,
        "source": {"system": "archinex", "author": "a.architect", "production_mode": "human-authored"},
        "evidence": [{"kind": "engagement", "ref": "eng-1"}],
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Submission validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("override, argument", [
    ({"kind": "idea"}, "kind"),
    ({"asset_type": None}, "asset_type"),
    ({"title": " "}, "title"),
    ({"source": {"system": "email"}}, "source.system"),
    ({"source": {"system": "mcp", "production_mode": "magic"}}, "source.production_mode"),
    ({"evidence": [{"kind": "rumour", "ref": "x"}]}, "evidence"),
    ({"kind": "amendment"}, "target_asset_id"),
])
def test_validate_submission_rejects_invalid_input(override, argument):
    with pytest.raises(CandidateError) as exc:
        validate_submission(submission(new_pattern(), **override))
    assert exc.value.argument == argument


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def test_schema_check(kb):
    ctx = build_context(kb)
    assert check_schema(cand(new_pattern()), ctx)["status"] == "pass"
    missing_fm = check_schema(cand("# no front matter"), ctx)
    assert missing_fm["status"] == "fail"
    rex = check_schema(cand("free text", kind="rex", asset_type=None), ctx)
    assert rex["status"] == "warn" and "free-form" in rex["detail"]
    bad_type = check_schema(cand(new_pattern().replace("type: pattern", "type: principle")), ctx)
    assert bad_type["status"] == "fail"
    unknown_domain = check_schema(cand(new_pattern().replace("[automation]", "[quantum-teleportation]")), ctx)
    assert unknown_domain["status"] == "fail" and "unknown domain" in unknown_domain["detail"]
    exists = check_schema(cand(new_pattern(pid="P-001").replace("type: pattern", "type: pattern")), ctx)
    assert exists["status"] == "fail"
    no_section = check_schema(cand(new_pattern().replace("## Trade-offs", "## Costs")), ctx)
    assert no_section["status"] == "warn"
    bad_clause = check_schema(cand(new_pattern(extra_fm="checks:\n  - {id: X, kind: requires, when: {terms_any: [a]}}\n")), ctx)
    assert bad_clause["status"] == "fail" and "checks[0]" in bad_clause["detail"]


def test_schema_check_for_amendment_and_glossary(kb):
    ctx = build_context(kb)
    amended = PRINCIPLE.replace("Configurations are versioned.", "Everything is versioned.")
    assert check_schema(cand(amended, kind="amendment", asset_type="principle", target="P-001"), ctx)["status"] == "pass"
    wrong_target = check_schema(cand(amended, kind="amendment", asset_type="principle", target="P-777"), ctx)
    assert wrong_target["status"] == "fail"
    assert check_schema(cand("**Blast radius** — scope of impact.", asset_type="glossary"), ctx)["status"] == "pass"
    assert check_schema(cand("Blast radius: scope", asset_type="glossary"), ctx)["status"] == "fail"


def test_references_check(kb):
    ctx = build_context(kb)
    assert check_references(cand(new_pattern()), ctx)["status"] == "pass"
    dangling = check_references(cand(new_pattern(body_extra="\nSee principle:P-404 and " + "ADR-" + "0999.")), ctx)
    assert dangling["status"] == "fail"
    assert "P-404" in dangling["detail"] and ("ADR-" + "0999") in dangling["detail"]
    assert check_references(cand(new_pattern(body_extra="\nImplements control:FW-01.")), ctx)["status"] == "pass"


def test_duplicate_check(kb):
    ctx = build_context(kb)
    assert check_duplicate(cand(new_pattern()), ctx)["status"] == "pass"
    dup = check_duplicate(cand(PRINCIPLE.replace("P-001", "P-002"), asset_type="principle", title="Everything as code"), ctx)
    assert dup["status"] == "warn" and "P-001" in dup["detail"] and "amendment" in dup["detail"]
    # An amendment of the asset itself is not a duplicate.
    assert check_duplicate(cand(PRINCIPLE, kind="amendment", target="P-001", title="Everything as code"), ctx)["status"] == "pass"


@pytest.mark.parametrize("text, blocked", [
    ("Management VLAN on 10.20.30.40", True),
    ("The gateway is 10.12.0.1.", True),
    ("Allocate 172.16.0.0/12 to the platform", True),
    ("Peer with fd00:1234::1 over IPv6", True),
    ("Example address 192.0.2.10 (documentation range)", False),
    ("Example 2001:db8::1 (documentation range)", False),
    ("Version 1.2.3 of the tool", False),
    ("Deployed at Acme Telecom last year", True),
    ("Deployed at a national operator last year", False),
])
def test_anonymization_check(kb, text, blocked):
    res = check_anonymization(cand(new_pattern(body_extra="\n" + text)), build_context(kb))
    assert (res["status"] == "fail") is blocked, res


def test_anonymization_warns_on_identifying_volumes(kb):
    res = check_anonymization(cand(new_pattern(body_extra="\nServes 1 250 000 subscribers.")), build_context(kb))
    assert res["status"] == "warn"


def test_find_ip_addresses_ignores_invalid_octets():
    assert find_ip_addresses("999.1.1.1 and 10.0.0.1/8") == ["10.0.0.1/8"]


def test_doctrine_conflict_check(kb):
    ctx = build_context(kb, doctrine_index_loader=doctrine)
    assert check_doctrine_conflict(cand(new_pattern()), ctx)["status"] == "pass"
    res = check_doctrine_conflict(cand(new_pattern(body_extra="\nOperators make a manual change in production.")), ctx)
    assert res["status"] == "warn" and "principle:P-001" in res["detail"]
    superseding = new_pattern(extra_fm="supersedes: [P-001]\n", body_extra="\nA manual change in production is fine.")
    assert check_doctrine_conflict(cand(superseding), ctx)["status"] == "pass"
    assert check_doctrine_conflict(cand(new_pattern()), build_context(kb))["status"] == "warn"  # no index


def test_llm_and_rejection_checks(kb):
    ctx = build_context(kb)
    assert check_llm_unreviewed(cand(new_pattern(), mode="llm-derived"), ctx)["status"] == "warn"
    assert check_llm_unreviewed(cand(new_pattern()), ctx)["status"] == "pass"
    rejected = cand(new_pattern(), id="CAND-20250101-0001")
    ctx = build_context(kb, rejected=[rejected])
    res = check_previously_rejected(cand(new_pattern()), ctx)
    assert res["status"] == "warn" and "CAND-20250101-0001" in res["detail"]


# ---------------------------------------------------------------------------
# Confidence table
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("evidence, mode, expected", [
    ([{"kind": "measure", "ref": "bench-2026"}], "human-authored", "verified"),
    ([{"kind": "audit", "ref": "audit-7"}], "human-authored", "verified"),
    ([{"kind": "engagement", "ref": "a"}, {"kind": "engagement", "ref": "b"}], "human-authored", "verified"),
    ([{"kind": "engagement", "ref": "a"}, {"kind": "engagement", "ref": "a"}], "human-authored", "assumed"),
    ([{"kind": "vendor-doc", "ref": "datasheet"}], "human-authored", "vendor-stated"),
    ([{"kind": "engagement", "ref": "a"}], "human-authored", "assumed"),
    ([], "human-authored", "assumed"),
    ([{"kind": "measure", "ref": "x"}], "llm-proposed-human-approved", "verified"),
])
def test_confidence_table(evidence, mode, expected):
    assert compute_confidence(evidence, mode) == expected


def test_unreviewed_llm_content_is_not_publishable():
    with pytest.raises(NotPublishableError):
        compute_confidence([{"kind": "measure", "ref": "x"}], "llm-derived")


# ---------------------------------------------------------------------------
# Owners and repository
# ---------------------------------------------------------------------------

def test_owner_routing_inherits_parent_domain(kb):
    owners = load_owners(kb)
    assert owners.owner_for_domains(["it/paas"]).handle == "@arch"
    assert owners.owner_for_domains(["unknown", "security"]).handle == "@sec"
    assert owners.owner_for_domains([]).handle == "@maintainers"


def test_file_repository_roundtrip(tmp_path):
    repo = FileCandidateRepository(tmp_path)
    first = repo.next_id()
    assert first.endswith("-0001")
    repo.save({"id": first, "status": "in_review", "source": {"system": "mcp"}, "domain": ["it/paas"]})
    assert repo.next_id().endswith("-0002")
    assert repo.get(first)["status"] == "in_review"
    assert [c["id"] for c in repo.find(domain="it")] == [first]
    assert repo.find(status="rejected") == []


def test_repository_backend_selection(monkeypatch, tmp_path):
    monkeypatch.setenv("CANDIDATES_BACKEND", "file")
    monkeypatch.setenv("CANDIDATES_DIR", str(tmp_path))
    assert isinstance(get_repository(), FileCandidateRepository)
    monkeypatch.setenv("CANDIDATES_BACKEND", "gcs")
    with pytest.raises(ValueError):  # the never-implemented gcs backend was removed (contract 1.4)
        get_repository()


# ---------------------------------------------------------------------------
# Service transitions
# ---------------------------------------------------------------------------

def test_submit_routes_to_domain_owner(service, recorder):
    c = service.submit(submission(new_pattern()), actor="tester")
    assert c["status"] == "in_review"
    assert c["assigned_owner"] == "@auto"
    assert recorder.owner_calls == [("@auto", "in_review", c["id"])]
    assert [h["event"] for h in c["history"]] == ["submitted", "in_review", "owner_notified"]
    assert c["second_review_required"] is False


def test_failed_checks_block_the_candidate(service, recorder):
    c = service.submit(submission(new_pattern(body_extra="\nGateway 192.168.1.1")))
    assert c["status"] == "checks_failed"
    assert recorder.owner_calls == []
    assert redact(c)["proposed_content"].startswith("[redacted")
    with pytest.raises(CandidateStateError):
        service.review(c["id"], "accept", "@auto")


def test_review_requires_known_owner_and_reason(service):
    c = service.submit(submission(new_pattern()))
    with pytest.raises(CandidateError, match="not an owner"):
        service.review(c["id"], "accept", "@nobody")
    with pytest.raises(CandidateError, match="reason"):
        service.review(c["id"], "reject", "@auto")
    rejected = service.review(c["id"], "reject", "@auto", reason="Not generic enough")
    assert rejected["status"] == "rejected" and rejected["review"]["reason"] == "Not generic enough"
    with pytest.raises(CandidateStateError):
        service.review(c["id"], "accept", "@auto")


def test_principle_requires_a_second_review_by_another_owner(service, recorder):
    content = PRINCIPLE.replace("P-001", "P-002").replace("Everything as code", "Small blast radius") \
        .replace("Configurations are versioned.", "Every action touches a single asset.")
    c = service.submit(submission(content, asset_type="principle", title="Small blast radius"))
    assert c["second_review_required"] is True
    first = service.review(c["id"], "accept", "@auto")
    assert first["status"] == "in_review" and first["review"]["reviewer"] == "@auto"
    assert ("@maintainers", "second_review", c["id"]) in recorder.owner_calls
    with pytest.raises(CandidateError, match="another owner"):
        service.review(c["id"], "accept", "@auto")
    second = service.review(c["id"], "accept", "@maintainers")
    assert second["status"] == "accepted" and second["second_review"]["reviewer"] == "@maintainers"


def test_amend_reruns_checks_and_accepts(service):
    c = service.submit(submission("Use blue/green for releases.", kind="rex", asset_type=None, title="Blue green"))
    assert c["status"] == "in_review"
    with pytest.raises(CandidateError, match="reason"):
        service.review(c["id"], "amend", "@maintainers", amended_content=new_pattern())
    amended = service.review(c["id"], "amend", "@maintainers", reason="Rewritten as a pattern", amended_content=new_pattern())
    assert amended["status"] == "accepted"
    assert amended["asset_type"] == "pattern"
    assert all(ch["status"] != "fail" for ch in amended["checks"])


def test_doctrine_conflict_needs_a_motivated_exception(service):
    content = new_pattern(body_extra="\nOperators make a manual change in production during incidents.")
    c = service.submit(submission(content))
    assert any(ch["name"] == "doctrine_conflict" and ch["status"] == "warn" for ch in c["checks"])
    with pytest.raises(CandidateError, match="doctrine"):
        service.review(c["id"], "accept", "@auto")
    assert service.review(c["id"], "accept", "@auto", reason="Break-glass exception")["status"] == "accepted"


def test_llm_derived_content_becomes_human_approved_on_acceptance(service):
    payload = submission(new_pattern())
    payload["source"]["production_mode"] = "llm-derived"
    c = service.submit(payload)
    assert any(ch["name"] == "llm_unreviewed" and ch["status"] == "warn" for ch in c["checks"])
    accepted = service.review(c["id"], "accept", "@auto")
    assert accepted["source"]["production_mode"] == "llm-proposed-human-approved"


def test_promote_and_publish(service, kb, recorder, tmp_path):
    payload = submission(new_pattern())
    payload["evidence"] = [{"kind": "engagement", "ref": "eng-1"}, {"kind": "engagement", "ref": "eng-2"}]
    c = service.submit(payload)
    with pytest.raises(CandidateStateError):
        service.promote(c["id"])
    service.review(c["id"], "accept", "@auto")
    promoted = service.promote(c["id"], today=date(2026, 10, 1))
    path = Path(promoted["promoted"]["path"])
    assert path == kb / "patterns" / "PAT-010.md"
    fm = yaml.safe_load(path.read_text().split("---")[1])
    assert fm["status"] == "active" and fm["confidence"] == "verified"
    assert fm["validated_by"] == ["@auto"] and str(fm["last_reviewed"]) == "2026-10-01"
    assert fm["revision"] == 1  # K3: a new element starts at revision 1
    with pytest.raises(CandidateStateError):
        service.promote(c["id"])

    calls = []
    result = service.publish(ingest=lambda: calls.append("ingest"),
                             snapshot=lambda: calls.append("snapshot") or {"snapshot_id": "snapshot-test"})
    assert calls == ["ingest", "snapshot"]
    assert result["published"] == [c["id"]] and result["snapshot_id"] == "snapshot-test"
    assert service.get(c["id"])["status"] == "published"
    changelog = (kb / "CHANGELOG.md").read_text()
    assert "snapshot-test" in changelog and "PAT-010" in changelog
    assert recorder.consumer_calls[0][0] == "kb_published"
    assert service.publish(ingest=lambda: None, snapshot=lambda: {})["published"] == []


def test_promote_amendment_rewrites_the_target(service, kb):
    amended = PRINCIPLE.replace("Configurations are versioned.", "Configurations and runbooks are versioned.")
    c = service.submit(submission(amended, kind="amendment", asset_type="principle", target_asset_id="P-001",
                                  title="Everything as code"))
    service.review(c["id"], "accept", "@auto")
    service.review(c["id"], "accept", "@maintainers")
    service.promote(c["id"])
    text = (kb / "principles" / "P-001.md").read_text()
    assert "runbooks are versioned" in text
    assert "checks_status: validated" in text
    assert "revision: 2" in text  # K3: an accepted amendment raises the revision (the synthetic base had none: 1 -> 2)


def test_two_accepted_amendments_raise_the_revision_twice(service, kb):
    for n, wording in enumerate(("Configurations and runbooks are versioned.", "Configurations, runbooks and policies are versioned.")):
        base = (kb / "principles" / "P-001.md").read_text()
        amended = base.replace(
            "Configurations are versioned." if n == 0 else "Configurations and runbooks are versioned.", wording
        )
        c = service.submit(submission(amended, kind="amendment", asset_type="principle", target_asset_id="P-001",
                                      title="Everything as code"))
        service.review(c["id"], "accept", "@auto")
        service.review(c["id"], "accept", "@maintainers")
        service.promote(c["id"])
    assert "revision: 3" in (kb / "principles" / "P-001.md").read_text()


def test_promote_glossary_entry(service, kb):
    (kb / "glossary").mkdir()
    (kb / "glossary" / "glossary.md").write_text("---\nid: TPL-glossary\n---\n\n**Drift** — difference.\n")
    c = service.submit(submission("**Blast radius** — scope of impact of an action.", asset_type="glossary",
                                  title="Blast radius"))
    service.review(c["id"], "accept", "@maintainers")
    service.promote(c["id"])
    text = (kb / "glossary" / "glossary.md").read_text()
    assert "**Drift**" in text and "**Blast radius** — scope of impact" in text


def test_business_days_and_reminders(service, recorder):
    monday = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
    assert business_days_between(monday, datetime(2026, 10, 12, 9, 0, tzinfo=UTC)) == 5
    assert business_days_between(datetime(2026, 10, 9, 9, 0, tzinfo=UTC), datetime(2026, 10, 12, 9, 0, tzinfo=UTC)) == 1
    c = service.submit(submission(new_pattern()))
    entered = next(h for h in c["history"] if h["event"] == "in_review")["at"]
    start = datetime.strptime(entered, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    from datetime import timedelta

    assert service.remind(now=start + timedelta(days=1)) == []
    later = start + timedelta(days=9)
    reminded = service.remind(now=later)
    assert [r["id"] for r in reminded] == [c["id"]]
    assert recorder.owner_calls[-1] == ("@auto", "reminder", c["id"])
    assert service.remind(now=later) == []  # at most one reminder per business day
