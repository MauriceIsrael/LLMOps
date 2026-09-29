"""End-to-end offline framework ingestion (plan L3 §6.1) on the NIS2 test excerpt.

kb ingest-framework -> kb review-sheet -> (expert fills the sheet) -> kb apply-review ->
kb declare-coverage, on a temporary copy of the knowledge base.
"""

import csv
import json
import shutil
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from pipelines.compliance_mapper import compute_framework_coverage
from pipelines.frameworks.links import suggest_links
from pipelines.kb_cli import app

ROOT = Path(__file__).parent.parent.parent
EXCERPT = ROOT / "tests" / "fixtures" / "frameworks" / "nis2_excerpt.txt"
EXPERT = "@security-compliance-team"


@pytest.fixture
def env(tmp_path, monkeypatch):
    kb = tmp_path / "kb"
    shutil.copytree(ROOT / "data" / "kb", kb)
    monkeypatch.setenv("CANDIDATES_DIR", str(tmp_path / "candidates"))
    monkeypatch.delenv("LLM_ENDPOINT", raising=False)
    import mcp_server.core.notifier as notifier

    monkeypatch.setattr(notifier, "notify_owner", lambda owner, event, c: ["log"])
    return {"kb": kb, "staging": tmp_path / "staging", "runner": CliRunner()}


def _run(env, *args):
    result = env["runner"].invoke(app, [*args])
    assert result.exit_code == 0, result.output
    return result


def _fm(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8").split("---")[1])


def test_ingest_review_apply_declare(env):
    kb, staging = env["kb"], env["staging"]

    # 1. Ingestion: draft controls in staging, manifest in the KB.
    _run(env, "ingest-framework", "--framework", "NIS2", "--version", "2022/2555", "--source", str(EXCERPT),
         "--kb-dir", str(kb), "--staging-dir", str(staging))
    run_dir = staging / "NIS2" / "2022-2555"
    drafts = sorted(p.stem for p in run_dir.glob("*.md"))
    assert len(drafts) == 19 and "NIS2-ART21-2J" in drafts and not any("ART22" in d for d in drafts)
    draft = _fm(run_dir / "NIS2-ART23-4.md")
    assert draft["status"] == "draft" and draft["validated_by"] == [] and draft["framework"] == "NIS2"
    assert "early warning within 24 hours" in (run_dir / "NIS2-ART23-4.md").read_text()
    manifest = yaml.safe_load((kb / "controls" / "NIS2" / "_manifest.yaml").read_text())
    assert manifest["expected_requirements"] == drafts_in_order(run_dir)
    assert len(manifest["source_sha256"]) == 64 and manifest["coverage_declared_by"] is None

    cov = compute_framework_coverage(["NIS2"], kb)["NIS2"]
    assert cov["status"] == "partial" and cov["expected"] == 19 and cov["present"] == 10 and cov["validated"] == 0
    refused = env["runner"].invoke(app, ["declare-coverage", "--framework", "NIS2", "--by", EXPERT, "--kb-dir", str(kb)])
    assert refused.exit_code == 1 and "cannot be declared covered" in refused.output

    # 2. Link suggestion is skipped without LLM_ENDPOINT.
    assert "skipped" in _run(env, "suggest-links", "--framework", "NIS2", "--kb-dir", str(kb),
                             "--staging-dir", str(staging)).output

    # 3. Review sheet, filled in by the expert (accept all, one amendment with links).
    _run(env, "review-sheet", "--framework", "NIS2", "--kb-dir", str(kb), "--staging-dir", str(staging))
    sheet = run_dir / "review_sheet.csv"
    with sheet.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 19 and {r["in_kb"] for r in rows} == {"yes", "no"}
    for r in rows:
        r.update(decision="accept", reviewer=EXPERT, comment="Verbatim text checked against the OJ")
        if r["requirement_id"] == "NIS2-ART23-4":
            r.update(decision="amend", links="P-008",
                     acceptance_criteria="Incident notification pipeline meets the 24h/72h/1-month deadlines")
    with sheet.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    # 4. Apply: framework_ingestion candidates, reviewed, promoted (existing controls amended in place).
    out = _run(env, "apply-review", str(sheet), "--kb-dir", str(kb))
    assert "promoted: 19" in out.output
    new = _fm(kb / "controls" / "NIS2" / "NIS2-ART23-4.md")
    assert new["status"] == "active" and new["validated_by"] == [EXPERT]
    assert new["satisfied_by"] == ["P-008"] and new["links_production_mode"] == "human-authored"
    assert "24h/72h/1-month" in (kb / "controls" / "NIS2" / "NIS2-ART23-4.md").read_text()
    existing = kb / "controls" / "NIS2" / "NIS2-ART21-2A.md"
    assert "Formal risk identification" in existing.read_text()  # curated content kept
    assert _fm(existing)["validated_by"] == [EXPERT]

    # 5. Coverage declaration by the expert.
    _run(env, "declare-coverage", "--framework", "NIS2", "--by", EXPERT, "--kb-dir", str(kb))
    cov = compute_framework_coverage(["NIS2", "RGPD", "UNKNOWN-FW"], kb)
    assert cov["NIS2"]["status"] == "covered" and cov["NIS2"]["declared_by"] == EXPERT
    assert cov["UNKNOWN-FW"]["status"] == "missing"
    assert cov["RGPD"]["status"] == "partial"

    # 6. Re-ingesting another source version resets the declaration.
    other = staging.parent / "nis2_v2.txt"
    other.write_text(EXCERPT.read_text() + "\n")
    out = _run(env, "ingest-framework", "--framework", "NIS2", "--version", "2022/2555-rev", "--source", str(other),
               "--kb-dir", str(kb), "--staging-dir", str(staging))
    assert "reset" in out.output
    assert compute_framework_coverage(["NIS2"], kb)["NIS2"]["status"] == "partial"


def drafts_in_order(run_dir: Path) -> list[str]:
    return yaml.safe_load((run_dir / "_ingestion.yaml").read_text())["requirements"]


def test_declare_coverage_requires_a_known_owner(env):
    _run(env, "ingest-framework", "--framework", "NIS2", "--version", "2022/2555", "--source", str(EXCERPT),
         "--kb-dir", str(env["kb"]), "--staging-dir", str(env["staging"]))
    res = env["runner"].invoke(app, ["declare-coverage", "--framework", "NIS2", "--by", "@nobody",
                                     "--kb-dir", str(env["kb"])])
    assert res.exit_code == 1 and "not an owner" in res.output


def test_suggest_links_marks_proposals_as_llm_derived(env):
    _run(env, "ingest-framework", "--framework", "NIS2", "--version", "2022/2555", "--source", str(EXCERPT),
         "--kb-dir", str(env["kb"]), "--staging-dir", str(env["staging"]))
    run_dir = env["staging"] / "NIS2" / "2022-2555"
    calls = []

    def fake_post(url, payload):
        calls.append((url, payload["model"]))
        content = json.dumps({"satisfied_by": ["P-002", "NOT-AN-ASSET"], "acceptance_criteria": ["Approvals are recorded."]})
        return {"choices": [{"message": {"content": f"Here you go:\n{content}"}}]}

    res = suggest_links(run_dir, env["kb"], endpoint="http://llm.local:11434", model="test-model", post=fake_post)
    assert res == {"skipped": False, "updated": 19, "model": "test-model"}
    assert calls[0] == ("http://llm.local:11434/v1/chat/completions", "test-model")
    fm = _fm(run_dir / "NIS2-ART21-2B.md")
    assert fm["proposed_links"] == ["P-002"]  # unknown ids are dropped
    assert fm["links_production_mode"] == "llm-derived"
