"""#156: la forme de ``POST /api/prose/suggest-batch`` (contrat §3.13), rejouée sur des vecteurs.

Ce que le Hub lit (``blockId``, ``instructions``, les libellés d'``anchoredItems``), ce qu'il ignore (``anchorIds``, le reste du contexte) et
ce qu'il refuse (corps non JSON, ``requests`` qui n'est pas une liste).
"""

import copy
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from mcp_server.main import create_starlette_app

VECTORS = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "suite" / "prose-suggest-batch.vectors.json").read_text(encoding="utf-8"))
HEADERS = {"Authorization": "Bearer secret-test-token"}


@pytest.fixture(scope="module")
def client():
    with patch.dict(os.environ, {"LLMOPS_AUTH_TOKEN": "secret-test-token"}):
        yield TestClient(create_starlette_app())


def _post(client, requests):
    res = client.post("/api/prose/suggest-batch", json={"requests": requests}, headers=HEADERS)
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"drafts", "warnings", "basedOnModelHash", "generatedAt"}
    return body


@pytest.mark.parametrize("vector", VECTORS["vectors"], ids=lambda v: v["name"])
def test_each_vector_gives_the_announced_outcome(client, vector):
    body = _post(client, [vector["request"]])
    block = vector["request"].get("blockId")
    if vector["expect"] == "draft":
        assert block in body["drafts"] and not body["warnings"]
        assert "ne démontrent pas" in body["drafts"][block]
    elif vector["expect"] == "warning":
        assert block not in body["drafts"] and [w["blockId"] for w in body["warnings"]] == [block]
        assert body["warnings"][0]["message"]
    else:
        assert body["drafts"] == {} and body["warnings"] == []


def test_a_block_is_never_both_a_draft_and_a_warning(client):
    body = _post(client, [v["request"] for v in VECTORS["vectors"]])
    assert not set(body["drafts"]) & {w["blockId"] for w in body["warnings"]}


def test_anchor_ids_and_the_rest_of_the_context_are_received_but_ignored(client):
    base = VECTORS["vectors"][0]["request"]
    other = copy.deepcopy(base)
    other["anchorIds"] = ["something-else", "and-more"]
    other["context"]["somethingElse"] = {"secret": "never read"}
    other["context"]["anchoredItems"][0]["attributes"]["description"] = "never read either"
    assert _post(client, [base])["drafts"] == _post(client, [other])["drafts"]


def test_a_draft_never_states_a_validation_it_did_not_make(client):
    draft = _post(client, [VECTORS["vectors"][0]["request"]])["drafts"]["block-gitops"]
    assert "validée" not in draft.lower().replace("à valider", "")


def test_a_body_that_is_not_a_request_list_is_refused(client):
    assert client.post("/api/prose/suggest-batch", content=b"not json", headers=HEADERS).status_code == 400
    assert client.post("/api/prose/suggest-batch", json=["x"], headers=HEADERS).status_code == 400
    assert client.post("/api/prose/suggest-batch", json={"requests": "x"}, headers=HEADERS).status_code == 400
