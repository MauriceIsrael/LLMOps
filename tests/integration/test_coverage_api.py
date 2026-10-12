"""Regulatory coverage (contract 1.3): MCP tool and optional field of the applicable frameworks route."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import jsonschema
from starlette.testclient import TestClient

from mcp_server.knowledge.tools import get_framework_coverage
from mcp_server.main import create_starlette_app

SCHEMA = json.loads((Path(__file__).parent.parent.parent / "schemas" / "framework_coverage.schema.json").read_text())


def test_get_framework_coverage_tool():
    res = get_framework_coverage(["NIS2", "ISO27001", "NOT-A-FRAMEWORK"])
    jsonschema.validate(res, SCHEMA)
    data = res["data"]
    assert data["NOT-A-FRAMEWORK"]["status"] == "missing"
    # NIS2: all requirements published and coverage declared by the maintainers
    assert data["NIS2"]["status"] == "covered" and data["NIS2"]["declared_by"] == "@maintainers"
    assert data["NIS2"]["expected"] == data["NIS2"]["present"] == 19 and data["NIS2"]["missing_ids"] == []
    assert data["ISO27001"]["status"] == "partial"  # provisional manifest: never covered
    assert data["ISO27001"]["expected"] == len(data["ISO27001"]["missing_ids"]) + data["ISO27001"]["present"]
    assert data["ISO27001"]["expected"] == 93
    assert get_framework_coverage([])["status"] == "invalid_argument"
    assert get_framework_coverage("NIS2,RGPD")["count"] == 2


def test_applicable_frameworks_route_gains_coverage(request):
    meta = Path("data/engagements") / "coverage-api-test.meta.json"
    request.addfinalizer(lambda: meta.unlink(missing_ok=True))
    with patch.dict(os.environ, {"SERVER_TOKEN": "coverage-token"}):
        client = TestClient(create_starlette_app())
        headers = {"Authorization": "Bearer coverage-token", "X-Engagement-Id": "coverage-api-test"}
        client.put("/api/compliance/frameworks/applicable", headers=headers, json={"frameworks": ["NIS2", "SecNumCloud"]})
        body = client.get("/api/compliance/frameworks/applicable", headers=headers).json()
    assert {"status", "engagement", "applicable_frameworks", "count"} <= set(body)
    assert body["applicable_frameworks"] == ["NIS2", "SecNumCloud"]
    assert set(body["coverage"]) == {"NIS2", "SecNumCloud"}
    assert body["coverage"]["SecNumCloud"]["expected"] is None
