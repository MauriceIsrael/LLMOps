"""Tests de non-régression sémantique avec DeepEval (Faithfulness & Answer Relevancy)."""

import json
from pathlib import Path

import pytest
from deepeval import assert_test
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric
from deepeval.test_case import LLMTestCase

from mcp_server.tools.asset_tools import get_asset

pytestmark = pytest.mark.stochastic

DATASET_PATH = Path("tests/evals/datasets/adr_qa_dataset.json")


def load_qa_dataset():
    if not DATASET_PATH.exists():
        return []
    with open(DATASET_PATH, encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.skipif(not DATASET_PATH.exists(), reason="Dataset QA introuvable")
def test_semantic_faithfulness_and_relevancy():
    qa_items = load_qa_dataset()
    if not qa_items:
        pytest.skip("Aucun cas de test dans le dataset QA.")

    item = qa_items[0]
    asset = get_asset("TPL-mcp-spec")
    actual_output = str(asset.get("sections", {}))

    test_case = LLMTestCase(
        input=item["input"],
        actual_output=actual_output,
        expected_output=item["expected_output"],
        retrieval_context=[asset.get("raw_body", "")],
    )

    faithfulness_metric = FaithfulnessMetric(threshold=0.7)
    relevancy_metric = AnswerRelevancyMetric(threshold=0.7)

    assert_test(test_case, [faithfulness_metric, relevancy_metric])
