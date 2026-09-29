"""The KB proposals of data/proposals/ pass the automatic checks (they wait for human review)."""

import json
from pathlib import Path

import pytest

from pipelines.kb_candidates.repository import FileCandidateRepository
from pipelines.kb_candidates.service import CandidateService

ROOT = Path(__file__).parent.parent.parent
PROPOSALS = sorted((ROOT / "data" / "proposals").glob("*.jsonl"))


@pytest.mark.parametrize("path", PROPOSALS, ids=[p.name for p in PROPOSALS])
def test_proposals_pass_checks(path, tmp_path):
    service = CandidateService(
        repository=FileCandidateRepository(tmp_path),
        kb_dir=ROOT / "data" / "kb",
        notify_owner=lambda owner, event, candidate: ["log"],
    )
    for line in path.read_text(encoding="utf-8").splitlines():
        payload = json.loads(line)
        assert payload["source"]["production_mode"] == "llm-derived"
        candidate = service.submit(payload, actor="test")
        failed = [c for c in candidate["checks"] if c["status"] == "fail"]
        assert not failed, (candidate["title"], failed)
        assert candidate["status"] == "in_review"
        assert candidate["assigned_owner"] == "@infrastructure-architecture-wg"
        assert any(c["name"] == "llm_unreviewed" and c["status"] == "warn" for c in candidate["checks"])
