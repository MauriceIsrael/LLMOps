"""Integration tests — doctrine context and option judge (contract 1.1) on the knowledge base.

Covers the MCP tools (get_doctrine_context, check_option), the REST routes
(GET /api/knowledge/context, POST /api/knowledge/check), their JSON schemas and
their determinism.
"""

import json
import os
from pathlib import Path
from unittest.mock import patch

import jsonschema
import pytest
from starlette.testclient import TestClient

from mcp_server.knowledge.tools import check_option, get_doctrine_context
from mcp_server.main import create_starlette_app

SCHEMAS = Path(__file__).parent.parent.parent / "schemas"
TOKEN = "check-api-test-token"

OPTION = {
    "title": "Closed-loop auto-remediation of network incidents",
    "description": "Remediation playbooks are triggered by alarms, without human approval.",
    "statements": [{"subject": "remediation", "predicate": "has_property", "value": "fully autonomous remediation"}],
}


def _schema(name: str) -> dict:
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def client():
    with patch.dict(os.environ, {"SERVER_TOKEN": TOKEN}):
        yield TestClient(create_starlette_app())


def _auth():
    return {"Authorization": f"Bearer {TOKEN}"}


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

def test_get_doctrine_context_matches_schema():
    res = get_doctrine_context("closed loop remediation of network incidents", frameworks=["NIS2"])
    jsonschema.validate(res, _schema("doctrine_context.schema.json"))
    assert res["count"] == len(res["data"]["items"]) > 0


def test_get_doctrine_context_includes_required_controls():
    res = get_doctrine_context("closed loop remediation", frameworks=["NIS2"], max_items=50)
    required = {i["id"] for i in res["data"]["items"] if i.get("required")}
    assert {"NIS2-ART21-2A", "NIS2-ART21-2B"} <= required
    assert all(i["status"] == "active" for i in res["data"]["items"])


def test_get_doctrine_context_returns_the_supervision_doctrine():
    items = get_doctrine_context("supervised closed loop remediation")["data"]["items"]
    by_id = {i["typed_id"]: i for i in items}
    assert by_id["principle:P-002"]["has_checks"] is True
    assert by_id["principle:P-002"]["source_ref"].endswith("principles/P-002.md")
    # Principles come first; the best pattern is the supervised closed loop.
    assert items[0]["type"] == "principle"
    patterns = [i for i in items if i["type"] == "pattern"]
    assert patterns[0]["typed_id"] == "pattern:PAT-001"


def test_get_doctrine_context_budget():
    res = get_doctrine_context("closed loop remediation", frameworks=["NIS2", "ISO27001"], max_items=30, max_chars=600)
    assert sum(len(i["excerpt"]) for i in res["data"]["items"]) <= 600
    assert res["data"]["truncated"] is True


@pytest.mark.parametrize("kwargs, argument", [
    ({"subject": ""}, "subject"),
    ({"subject": "x", "max_items": 0}, "max_items"),
    ({"subject": "x", "max_chars": 10}, "max_chars"),
    ({"subject": "x", "domains": [1, 2]}, "domains"),
])
def test_get_doctrine_context_invalid_arguments(kwargs, argument):
    res = get_doctrine_context(**kwargs)
    assert res["status"] == "invalid_argument"
    assert res["argument"] == argument


def test_check_option_matches_schema_and_flags_the_violation():
    res = check_option(OPTION, subject="Network incident remediation", frameworks=["NIS2"])
    jsonschema.validate(res, _schema("check_result.schema.json"))
    verdicts = res["data"]["verdicts"]
    violated = {(v["typed_id"], v["check_id"]) for v in verdicts if v["verdict"] == "violates"}
    assert ("principle:P-002", "P-002-C1") in violated
    assert ("principle:P-002", "P-002-C2") in violated
    assert res["data"]["method"] == "deterministic-checks-v1"
    nis2 = {v["typed_id"] for v in verdicts if v["typed_id"].startswith("control:NIS2-")}
    assert len(nis2) >= 10, "every active NIS2 control must be reported"


def test_check_option_supports_a_supervised_option():
    option = {"title": "Supervised closed loop", "description": "Auto-remediation gated by a human approval in the ITSM."}
    verdicts = check_option(option)["data"]["verdicts"]
    p002 = [v for v in verdicts if v["check_id"] == "P-002-C1"]
    assert p002 and p002[0]["verdict"] == "supports"


@pytest.mark.parametrize("option, argument", [
    ("not an object", "option"),
    ({"description": "no title"}, "option.title"),
    ({"title": "t", "statements": "x"}, "option.statements"),
])
def test_check_option_invalid_arguments(option, argument):
    res = check_option(option)
    assert res["status"] == "invalid_argument"
    assert res["argument"] == argument


def test_tools_are_deterministic():
    a = check_option(OPTION, subject="remediation", frameworks=["NIS2", "SecNumCloud"])
    b = check_option(OPTION, subject="remediation", frameworks=["NIS2", "SecNumCloud"])
    assert a == b
    c = get_doctrine_context("closed loop", frameworks=["NIS2"])
    d = get_doctrine_context("closed loop", frameworks=["NIS2"])
    assert c == d


# ---------------------------------------------------------------------------
# REST routes
# ---------------------------------------------------------------------------

def test_rest_context_route(client):
    res = client.get(
        "/api/knowledge/context?subject=closed%20loop%20remediation&frameworks=NIS2&frameworks=SecNumCloud&max_items=40",
        headers=_auth(),
    )
    assert res.status_code == 200
    body = res.json()
    jsonschema.validate(body, _schema("doctrine_context.schema.json"))
    frameworks = {i["framework"] for i in body["data"]["items"] if i.get("required")}
    assert frameworks == {"NIS2", "SecNumCloud"}
    # Comma-separated form is equivalent.
    res2 = client.get(
        "/api/knowledge/context?subject=closed%20loop%20remediation&frameworks=NIS2,SecNumCloud&max_items=40",
        headers=_auth(),
    )
    assert res2.json() == body


def test_rest_context_route_errors(client):
    assert client.get("/api/knowledge/context", headers=_auth()).status_code == 400
    assert client.get("/api/knowledge/context?subject=x&max_items=abc", headers=_auth()).status_code == 400
    assert client.get("/api/knowledge/context?subject=x").status_code == 401


def test_rest_check_route(client):
    payload = {"option": OPTION, "subject": "Network incident remediation", "frameworks": ["NIS2"]}
    res = client.post("/api/knowledge/check", json=payload, headers=_auth())
    assert res.status_code == 200
    body = res.json()
    jsonschema.validate(body, _schema("check_result.schema.json"))
    assert body == client.post("/api/knowledge/check", json=payload, headers=_auth()).json()
    assert body == check_option(OPTION, subject="Network incident remediation", frameworks=["NIS2"])


def test_rest_check_route_errors(client):
    assert client.post("/api/knowledge/check", content=b"not json", headers=_auth()).status_code == 400
    res = client.post("/api/knowledge/check", json={"option": {}}, headers=_auth())
    assert res.status_code == 400
    assert res.json()["argument"] == "option.title"
    assert client.post("/api/knowledge/check", json={"option": OPTION}).status_code == 401
