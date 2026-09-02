"""Contract tests for MCP Compliance & Regulatory Tools under ADR-0015."""

import pytest
from mcp_server.knowledge.tools import (
    list_frameworks,
    list_controls,
    get_compliance_trail,
    get_compliance_matrix,
)


def test_list_frameworks_contract():
    res = list_frameworks()
    assert res["status"] == "ok"
    assert res["count"] >= 2
    fws = {f["framework"] for f in res["data"]}
    assert "NIS2" in fws
    assert "3GPP" in fws
    for f in res["data"]:
        assert "title" in f
        assert "version" in f
        assert "control_count" in f
        assert f["control_count"] > 0


def test_list_controls_filtering():
    res_all = list_controls()
    assert res_all["status"] == "ok"
    assert res_all["count"] >= 15

    res_nis2 = list_controls(framework="NIS2")
    assert res_nis2["status"] == "ok"
    assert res_nis2["count"] == 10
    for c in res_nis2["data"]:
        assert c["framework"] == "NIS2"
        assert "implemented_by" in c

    res_3gpp = list_controls(framework="3GPP")
    assert res_3gpp["status"] == "ok"
    assert res_3gpp["count"] == 5


def test_get_compliance_trail():
    res = get_compliance_trail("NIS2-ART21-2C")
    assert res["status"] == "ok"
    data = res["data"]
    assert data["control"]["id"] == "NIS2-ART21-2C"
    assert data["control"]["framework"] == "NIS2"
    pat_ids = [p["id"] for p in data["implementing_patterns"]]
    assert "PAT-003" in pat_ids or "PAT-004" in pat_ids
    assert data["total_coverage"] > 0

    # Non-existent control
    res_404 = get_compliance_trail("DOES-NOT-EXIST-404")
    assert res_404["status"] == "not_found"


def test_get_compliance_matrix():
    res = get_compliance_matrix("nordwave-mcx-2027", "NIS2")
    assert res["status"] == "ok"
    data = res["data"]
    assert data["engagement"] == "nordwave-mcx-2027"
    assert data["framework"] == "NIS2"
    assert data["total_controls"] == 10
    assert "matrix" in data
    assert len(data["matrix"]) == 10
