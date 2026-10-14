"""K13 (ADR-KH-01 A10-d-3): no programme anchor in the knowledge base, in the candidate cycle or in the reuse journal."""

import re
import shutil
from pathlib import Path

import pytest

from mcp_server.core.config import server_config
from pipelines.kb_candidates import anchors
from pipelines.kb_candidates.repository import FileCandidateRepository
from pipelines.kb_candidates.service import CandidateService
from pipelines.similarity.reuse import ReuseError, validate_confirmation

ROOT = Path(__file__).resolve().parents[2]
PATTERN = (ROOT / "data/kb/patterns/PAT-001.md").read_text(encoding="utf-8")
ENGAGEMENT = "acme-core-2027"


@pytest.fixture
def kb(tmp_path):
    target = tmp_path / "kb"
    shutil.copytree(ROOT / "data/kb", target)
    return target


@pytest.fixture
def service(kb, tmp_path):
    return CandidateService(repository=FileCandidateRepository(tmp_path / "candidates"), kb_dir=kb,
                            notify_owner=lambda *a: [], notify_consumers=lambda *a: [])


def anonymization(service, content=PATTERN, rationale="", **source):
    payload = {"kind": "new_asset", "asset_type": "pattern", "title": "Supervised loop", "rationale": rationale,
               "proposed_content": content, "source": {"system": "archinex", "production_mode": "human-authored", **source}}
    checks = service.dry_run(payload, actor="a.architect")["checks"]
    return next(c for c in checks if c["name"] == "anonymization")


def test_a_clean_candidate_passes(service):
    assert anonymization(service, engagement=ENGAGEMENT)["status"] == "pass"


def test_the_identifier_of_the_engagement_it_comes_from_is_refused_with_a_precise_message(service):
    result = anonymization(service, rationale=f"We learned this on {ENGAGEMENT}.", engagement=ENGAGEMENT)
    assert result["status"] == "fail"
    assert "engagement identifier(s)" in result["detail"] and ENGAGEMENT in result["detail"]


def test_an_email_is_refused_and_masked_in_the_result(service):
    result = anonymization(service, rationale="Ask jane.doe@client-corp.example about it.")
    assert result["status"] == "fail" and "e-mail address(es)" in result["detail"]
    assert "jane.doe" not in result["detail"] and "j***@client-corp.example" in result["detail"]


def test_a_member_handle_an_address_and_a_programme_field_are_refused(service):
    assert "member handle(s): ['@ada']" in anonymization(service, rationale="Decided by @ada.")["detail"]
    assert "IP address(es)" in anonymization(service, rationale="Gateway at 10.20.30.40.")["detail"]
    content = PATTERN.replace("owner: core-owner-architecture", "owner: core-owner-architecture\nsource_engagement: some-programme")
    result = anonymization(service, content=content)
    assert result["status"] == "fail" and "programme field(s): ['source_engagement']" in result["detail"]


def test_a_refused_candidate_never_reaches_review(service):
    payload = {"kind": "new_asset", "asset_type": "pattern", "title": "Supervised loop", "proposed_content": PATTERN,
               "rationale": f"Observed on {ENGAGEMENT}", "source": {"system": "archinex", "engagement": ENGAGEMENT, "production_mode": "human-authored"}}
    assert service.submit(payload, actor="a.architect")["status"] == "checks_failed"


def test_the_reuse_journal_refuses_the_same_anchors_and_stays_unchanged(kb):
    known = sorted(anchors.known_engagement_ids())
    assert known, "the repository ships working bases whose identifiers must stay out of the journal"
    body = {"outcome": "deferred", "subject_fingerprint": "a" * 64, "subject_label": f"HA of {known[0]}", "matched_ref": "PAT-001"}
    with pytest.raises(ReuseError, match="engagement identifier"):
        validate_confirmation(body, None, kb)
    with pytest.raises(ReuseError, match="handle"):
        validate_confirmation({**body, "subject_label": "Chosen by @ada"}, None, kb)


def test_no_asset_of_the_knowledge_base_carries_an_engagement_identifier():
    """The base is agnostic of programmes: scan every asset for the engagements this repository knows (working bases, examples)."""
    ids = anchors.known_engagement_ids() | {p.name for p in (ROOT / "examples").iterdir() if p.is_dir()}
    assert ids
    offenders = []
    for path in sorted(server_config.kb_dir.rglob("*")):
        if path.suffix not in (".md", ".yaml", ".yml") or path.name in ("CHANGELOG.md", "anonymization_denylist.txt"):
            continue
        text = path.read_text(encoding="utf-8").lower()
        offenders += [f"{path.relative_to(server_config.kb_dir)}: {i}" for i in sorted(ids)
                      if re.search(rf"(?<![\w-]){re.escape(i.lower())}(?![\w-])", text)]
    assert offenders == []
