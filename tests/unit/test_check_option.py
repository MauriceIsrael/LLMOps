"""Unit tests — doctrine engine: check clauses, option judge and doctrine context.

Synthetic, in-memory doctrine only (no graph, no project data).
"""

import pytest

from pipelines.doctrine.checks import evaluate_clause, parse_checks, validate_clause
from pipelines.doctrine.context import build_doctrine_context, rank, truncate
from pipelines.doctrine.index import DoctrineEntry, DoctrineIndex
from pipelines.doctrine.judge import METHOD, check_option, option_text
from pipelines.doctrine.text import (
    Vocabulary,
    match_terms,
    normalize,
    normalize_phrase,
    query_concepts,
)

REQUIRES = {
    "id": "P-100-C1",
    "kind": "requires",
    "when": {"terms_any": ["closed-loop", "auto-remediation"]},
    "expect": {"terms_any": ["human-approval", "supervised"]},
    "message": "Closed loops stay supervised.",
}
FORBIDS = {
    "id": "P-101-C1",
    "kind": "forbids",
    "when": {"terms_any": ["public llm api"]},
    "message": "Inference stays inside the trust boundary.",
}


def _vocab() -> Vocabulary:
    v = Vocabulary()
    v.add_group(["human approval", "validation humaine", "manual approval"])
    v.add_group(["container orchestration", "orchestration de conteneurs", "kubernetes"])
    return v


def _entry(eid, etype, title, body="", domain=(), checks=None, framework="", status="active", phase=(), terms=()):
    return DoctrineEntry(
        id=eid, type=etype, title=title, status=status, confidence="verified", domain=list(domain),
        phase=list(phase), source_ref=f"kb/{eid}.md", body=body, framework=framework, terms=list(terms),
        checks=parse_checks(checks or [], "draft"),
    )


@pytest.fixture
def index() -> DoctrineIndex:
    return DoctrineIndex(
        entries=[
            _entry("P-100", "principle", "Human in the loop",
                   "## Statement\nEvery closed loop remediation needs a human approval.\n## Why\nConfidence.",
                   domain=["network-automation"], checks=[REQUIRES]),
            _entry("P-101", "principle", "Model inside the trust boundary",
                   "## Statement\nInference runs on project infrastructure.", domain=["ai-assistance"],
                   checks=[FORBIDS]),
            _entry("P-102", "principle", "Retired principle", "## Statement\nclosed loop", status="superseded",
                   checks=[{**FORBIDS, "id": "P-102-C1", "when": {"terms_any": ["closed loop"]}}]),
            _entry("PAT-100", "pattern", "Supervised closed loop", "## Solution\nApproval node before execution.",
                   domain=["network-automation/remediation"]),
            _entry("DEC-100", "decision", "Container orchestration platform",
                   "## Decision\nKubernetes is the container orchestration platform.", domain=["it-infrastructure/paas"],
                   phase=["BUILD"]),
            _entry("FW1-01", "control", "Incident handling",
                   "## Legal Requirement\nHandle incidents.\n## Architecture Acceptance Criteria\nTraceable remediation.",
                   framework="FW1"),
            _entry("FW1-02", "control", "Cryptography", "## Legal Requirement\nUse encryption.", framework="FW1"),
            _entry("FW2-01", "control", "Closed loop audit", "## Legal Requirement\nAudit every closed loop.",
                   framework="FW2"),
        ],
        vocabulary=_vocab(),
    )


# ---------------------------------------------------------------------------
# Clauses
# ---------------------------------------------------------------------------

def test_validate_clause_accepts_valid_clauses():
    assert validate_clause(REQUIRES) == []
    assert validate_clause(FORBIDS) == []


@pytest.mark.parametrize("bad, problem", [
    ({**REQUIRES, "kind": "prefers"}, "'kind'"),
    ({k: v for k, v in REQUIRES.items() if k != "expect"}, "missing 'expect'"),
    ({**REQUIRES, "when": {"terms_any": []}}, "'when'"),
    ({**REQUIRES, "when": {"terms_any": "closed-loop"}}, "'when.terms_any'"),
    ({**FORBIDS, "expect": {"terms_any": ["x"]}}, "'expect' is only meaningful"),
    ({k: v for k, v in FORBIDS.items() if k != "id"}, "missing string 'id'"),
])
def test_validate_clause_reports_problems(bad, problem):
    assert any(problem in p for p in validate_clause(bad))


def test_parse_checks_skips_invalid_clauses_and_reads_status():
    clauses = parse_checks([REQUIRES, {"id": "broken"}], checks_status="validated")
    assert [c.id for c in clauses] == ["P-100-C1"]
    assert clauses[0].status == "validated"
    assert parse_checks([REQUIRES])[0].status == "draft"
    assert parse_checks("not a list") == []


def _eval(raw, text):
    return evaluate_clause(parse_checks([raw])[0], normalize(text), _vocab())


def test_requires_supports_when_expectation_is_met():
    res = _eval(REQUIRES, "Closed-loop remediation, each action supervised by the NOC")
    assert res.verdict == "supports"
    assert res.matched_terms == ["closed-loop", "supervised"]


def test_requires_violates_when_expectation_is_missing():
    res = _eval(REQUIRES, "Auto-remediation of alarms")
    assert res.verdict == "violates"
    assert res.matched_terms == ["auto-remediation"]


def test_clause_does_not_apply_when_condition_does_not_match():
    assert _eval(REQUIRES, "Manual runbooks executed by operators") is None
    assert _eval(FORBIDS, "Self-hosted inference") is None


def test_forbids_violates_when_condition_matches():
    res = _eval(FORBIDS, "Summaries generated through a Public LLM API")
    assert res.verdict == "violates"


def test_synonyms_and_accents_are_matched():
    res = _eval(REQUIRES, "Boucle: closed loop avec validation humaine préalable")
    assert res.verdict == "supports"
    assert "human-approval" in res.matched_terms


def test_negated_expectation_does_not_count():
    res = _eval(REQUIRES, "Closed-loop remediation without human approval")
    assert res.verdict == "violates"


def test_terms_all_requires_every_term():
    raw = {"id": "X-1", "kind": "forbids", "when": {"terms_all": ["assistant", "write access"]}}
    assert _eval(raw, "An assistant with write access to production").verdict == "violates"
    assert _eval(raw, "An assistant, read-only") is None


def test_match_terms_reports_one_term_per_synonym_group():
    text = normalize("manual approval required")
    assert match_terms(text, ["human approval", "validation humaine", "manual approval"], _vocab()) == ["manual approval"]


def test_query_concepts_recognise_vocabulary_phrases():
    concepts = query_concepts("Orchestration de conteneurs pour la PaaS", _vocab())
    # Phrases are stored normalized (lower case, no accents, light plural folding).
    assert any(normalize_phrase("kubernetes") in c for c in concepts)
    assert any(normalize_phrase("PaaS") in c for c in concepts)
    assert len(concepts) == 2  # the vocabulary phrase is one concept; stop words are dropped


# ---------------------------------------------------------------------------
# Judge
# ---------------------------------------------------------------------------

def test_option_text_includes_statements():
    text = option_text({"title": "T", "description": "D", "statements": [{"subject": "s", "predicate": "p", "value": "v"}]})
    assert text.split("\n") == ["T", "D", "s", "p", "v"]


def test_check_option_reports_violations_first_with_citations(index):
    res = check_option(index, {"title": "Closed-loop auto-remediation", "description": "Alarms trigger playbooks."},
                       subject="network remediation")
    first = res["verdicts"][0]
    assert first == {
        "typed_id": "principle:P-100",
        "check_id": "P-100-C1",
        "verdict": "violates",
        "message": "Closed loops stay supervised.",
        "matched_terms": ["closed-loop", "auto-remediation"],
        "excerpt": first["excerpt"],
        "source_ref": "kb/P-100.md",
        "check_status": "draft",
    }
    assert "closed loop" in first["excerpt"]
    assert res["method"] == METHOD
    assert res["summary"]["violates"] == 1


def test_inactive_doctrine_is_never_used(index):
    res = check_option(index, {"title": "closed loop"})
    assert all(v["typed_id"] != "principle:P-102" for v in res["verdicts"])


def test_required_framework_controls_are_always_returned(index):
    res = check_option(index, {"title": "Self-hosted inference platform"}, frameworks=["FW1"])
    by_id = {v["typed_id"]: v for v in res["verdicts"]}
    assert by_id["control:FW1-01"]["verdict"] == "unassessed"
    assert by_id["control:FW1-02"]["verdict"] == "unassessed"
    assert by_id["control:FW1-01"]["check_id"] is None
    assert "control:FW2-01" not in by_id


def test_summary_counts_match_verdicts(index):
    res = check_option(index, {"title": "Closed loop with human approval, public LLM API"}, frameworks=["FW1"])
    counts = {k: sum(1 for v in res["verdicts"] if v["verdict"] == k) for k in ("supports", "violates", "unassessed")}
    assert res["summary"] == counts
    assert counts["supports"] == 1 and counts["violates"] == 1


def test_check_option_is_deterministic(index):
    option = {"title": "Closed loop with human approval", "statements": [{"subject": "llm", "predicate": "uses", "value": "public LLM API"}]}
    runs = [check_option(index, option, subject="remediation", frameworks=["FW1", "FW2"]) for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]


# ---------------------------------------------------------------------------
# Doctrine context
# ---------------------------------------------------------------------------

def test_context_orders_by_type_priority(index):
    ctx = build_doctrine_context(index, "closed loop remediation", frameworks=["FW1"])
    types = [(i["type"], i.get("required")) for i in ctx["items"]]
    assert types[0] == ("principle", False)
    first_pattern = types.index(("pattern", False))
    assert all(t == ("control", True) for t in types[1:first_pattern])
    required = {i["id"] for i in ctx["items"] if i.get("required")}
    assert required == {"FW1-01", "FW1-02"}
    # A control of a non-required framework appears only on relevance, after patterns and ADRs.
    assert types[-1] == ("control", False) and ctx["items"][-1]["id"] == "FW2-01"


def test_context_serves_only_active_assets(index):
    ctx = build_doctrine_context(index, "closed loop")
    assert all(i["status"] == "active" for i in ctx["items"])
    assert "P-102" not in {i["id"] for i in ctx["items"]}


def test_context_domain_filter_matches_sub_domains(index):
    ctx = build_doctrine_context(index, "closed loop supervised", domains=["network-automation"])
    assert {i["id"] for i in ctx["items"]} == {"P-100", "PAT-100"}


def test_context_phase_filter(index):
    assert build_doctrine_context(index, "kubernetes", phase="RUN")["items"] == []
    assert [i["id"] for i in build_doctrine_context(index, "kubernetes", phase="BUILD")["items"]] == ["DEC-100"]


def test_context_synonyms_bridge_languages(index):
    ctx = build_doctrine_context(index, "Orchestration de conteneurs")
    assert [i["id"] for i in ctx["items"]] == ["DEC-100"]
    assert ctx["items"][0]["relevance"] > 0.5


def test_context_respects_max_items_and_budget(index):
    ctx = build_doctrine_context(index, "closed loop remediation", frameworks=["FW1"], max_items=2, max_chars=200)
    assert len(ctx["items"]) == 2
    assert ctx["truncated"] is True
    assert sum(len(i["excerpt"]) for i in ctx["items"]) <= 200


def test_context_item_fields(index):
    item = build_doctrine_context(index, "human approval closed loop")["items"][0]
    assert item["typed_id"] == "principle:P-100"
    assert item["has_checks"] is True
    assert item["source_ref"] == "kb/P-100.md"
    assert 0 < item["relevance"] <= 1
    assert "human approval" in item["excerpt"]


def test_rank_is_deterministic(index):
    a = [(s.entry.id, s.relevance) for s in rank(index, "closed loop", frameworks=["FW2"])]
    b = [(s.entry.id, s.relevance) for s in rank(index, "closed loop", frameworks=["FW2"])]
    assert a == b


def test_truncate_cuts_cleanly():
    text = "First sentence is here. Second sentence is much longer than the limit allows."
    cut, was_cut = truncate(text, 40)
    assert was_cut and cut == "First sentence is here."
    cut, was_cut = truncate("word " * 50, 30)
    assert was_cut and cut.endswith("…") and len(cut) <= 30
    assert truncate("short", 30) == ("short", False)
