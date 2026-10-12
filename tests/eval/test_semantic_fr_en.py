"""FR→EN evaluation of the local semantic search with the real model (issue #94, lot E5). Opt-in.

Runs only with ``KB_SEMANTIC_EVAL=1`` and the model fetched (``kb models fetch``)::

    KB_SEMANTIC_EVAL=1 poetry run pytest tests/eval/test_semantic_fr_en.py -m semantic_eval

Criteria: recall at 5 >= 0.8 in hybrid mode (and above the lexical baseline), no regression on the English queries,
the same order on two runs, no outgoing network call during the queries.
"""

import os
import socket
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "tests" / "fixtures" / "similarity" / "fr-en-doctrine.yaml"

pytestmark = [
    pytest.mark.semantic_eval,
    pytest.mark.skipif(os.getenv("KB_SEMANTIC_EVAL", "").strip() not in ("1", "true", "on"),
                       reason="opt-in: set KB_SEMANTIC_EVAL=1 (needs the model: kb models fetch)"),
]


@pytest.fixture(scope="module")
def setup():
    mp = pytest.MonkeyPatch()
    mp.setenv("KB_EMBEDDINGS", "on")
    mp.delenv("KB_EMBEDDING_MODEL", raising=False)
    from mcp_server.core.config import server_config
    from mcp_server.knowledge.tools import _doctrine_index
    from pipelines.doctrine.semantic_eval import load_cases
    from pipelines.similarity.encoder import reference_encoder, reset_cache
    from pipelines.similarity.semantic import scorer_for

    reset_cache()
    encoder, status = reference_encoder()
    if encoder is None:
        mp.undo()
        pytest.skip(f"embedding model {status['status']}: {status.get('reason')}")
    scorer = scorer_for(encoder)

    def semantic(subject):
        return {ref: s["semantic"] for ref, s in scorer.scores(server_config.kb_dir, subject).items()}

    yield {"index": _doctrine_index(), "cases": load_cases(CASES), "semantic": semantic, "status": status}
    reset_cache()
    mp.undo()


def test_the_set_is_large_enough_and_anonymised(setup):
    from pipelines.kb_candidates.checks import load_denylist

    cases = setup["cases"]
    assert sum(1 for c in cases if c.get("language", "fr") == "fr") >= 40
    denylist = [t.lower() for t in load_denylist(ROOT / "data" / "kb")]
    project = [t.strip().lower() for t in (ROOT / ".project-names-denylist").read_text(encoding="utf-8").splitlines()
               if t.strip() and not t.startswith("#")]
    text = CASES.read_text(encoding="utf-8").lower()
    assert not [t for t in denylist + project if t and t in text]
    known = {e.id for e in setup["index"].active()}
    assert not [x for c in cases for x in c["expected"] if x not in known]


def test_hybrid_recall_at_5_beats_the_lexical_baseline(setup):
    from pipelines.doctrine.context import DEFAULT_HYBRID_WEIGHT, MIN_SEMANTIC
    from pipelines.doctrine.semantic_eval import evaluate

    hybrid = evaluate(setup["index"], setup["cases"], setup["semantic"], DEFAULT_HYBRID_WEIGHT, MIN_SEMANTIC)
    lexical = evaluate(setup["index"], setup["cases"], None, min_semantic=MIN_SEMANTIC)
    assert hybrid["recall_at_5"] >= 0.8, hybrid["recall_at_5"]
    assert hybrid["recall_at_5"] > lexical["recall_at_5"]
    assert hybrid["recall_at_5_by_language"]["en"] >= lexical["recall_at_5_by_language"]["en"]  # no regression


def test_two_runs_give_the_same_order(setup):
    from pipelines.doctrine.semantic_eval import evaluate

    a = evaluate(setup["index"], setup["cases"], setup["semantic"])
    b = evaluate(setup["index"], setup["cases"], setup["semantic"])
    assert [c["top"] for c in a["per_case"]] == [c["top"] for c in b["per_case"]]


def test_no_network_during_a_query(setup, monkeypatch):
    from mcp_server.knowledge.tools import get_doctrine_context

    def refuse(*args, **kwargs):
        raise AssertionError("outgoing network call during a query")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    res = get_doctrine_context("Équipe habilitée BUILD/RUN 24/7 : modèle de dotation, souveraineté et coût",
                               frameworks=["NIS2"])
    assert res["data"]["relevance_method"] == "hybrid" and res["data"]["embedding"]["local"] is True
    required = [i for i in res["data"]["items"] if i["required"]]
    assert required[0]["id"] == "NIS2-ART21-2I" and required[0]["relevant"] is True
