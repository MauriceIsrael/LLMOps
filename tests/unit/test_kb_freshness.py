"""Tests for KB regulatory and doctrine freshness checking (Issue #131)."""

from datetime import date, timedelta
from pathlib import Path

from starlette.testclient import TestClient

from mcp_server.core.auth import set_current_caller
from mcp_server.main import create_starlette_app
from pipelines.governance.freshness import (
    check_kb_freshness,
    render_freshness_report,
)

KB = Path(__file__).parent.parent.parent / "data" / "kb"


def test_check_kb_freshness_structure():
    report = check_kb_freshness(KB)
    assert "overdue_reviews" in report
    assert "source_drifts" in report
    assert "doctrine_dependencies" in report
    assert "alerts_by_owner" in report
    assert "summary" in report

    summary = report["summary"]
    assert "total_controls" in summary
    assert "total_standards" in summary
    assert "overdue_count" in summary
    assert "source_drift_count" in summary
    assert "affected_doctrine_count" in summary


def test_render_freshness_report():
    report = check_kb_freshness(KB)
    rendered = render_freshness_report(report)
    assert "# Rapport de veille et fraîcheur documentaire (Normes & Doctrines)" in rendered
    assert "Date de vérification" in rendered


def test_freshness_drift_and_overdue_detection(tmp_path: Path):
    kb_dir = tmp_path / "kb"
    standards_dir = kb_dir / "standards"
    controls_dir = kb_dir / "controls"
    principles_dir = kb_dir / "principles"
    standards_dir.mkdir(parents=True)
    controls_dir.mkdir(parents=True)
    principles_dir.mkdir(parents=True)

    # Standard v2.0
    (standards_dir / "STD-TEST.md").write_text(
        """---
id: STD-TEST
type: standard
status: active
title: Test Standard
version: "2.0"
domain:
  - security
---
# Test Standard
""",
        encoding="utf-8",
    )

    # Control based on STD-TEST v1.0 (drift) and last verified 200 days ago (overdue)
    old_date = (date.today() - timedelta(days=200)).isoformat()
    (controls_dir / "SEC-CTRL-01.md").write_text(
        f"""---
id: SEC-CTRL-01
type: control
status: active
title: Secure Channel
domain:
  - security
owner: "@alice"
source_version: "1.0"
last_verified_at: "{old_date}"
review_cycle_days: 90
upstream_standard_ref: "standards/STD-TEST.md"
---
# Secure Channel
""",
        encoding="utf-8",
    )

    report = check_kb_freshness(kb_dir, default_review_cycle_days=90)
    assert report["summary"]["total_standards"] == 1
    assert report["summary"]["total_controls"] == 1
    assert report["summary"]["source_drift_count"] == 1
    assert report["summary"]["overdue_count"] == 1

    drift = report["source_drifts"][0]
    assert drift["control_id"] == "SEC-CTRL-01"
    assert drift["current_version"] == "1.0"
    assert drift["upstream_latest_version"] == "2.0"

    overdue = report["overdue_reviews"][0]
    assert overdue["id"] == "SEC-CTRL-01"
    assert overdue["days_overdue"] > 0
    assert overdue["review_cycle_days"] == 90

    assert "@alice" in report["alerts_by_owner"]
    assert report["alerts_by_owner"]["@alice"]["overdue_count"] == 1
    assert report["alerts_by_owner"]["@alice"]["drift_count"] == 1


def test_mcp_get_kb_freshness_tool(monkeypatch):
    from mcp_server.knowledge.tools import get_kb_freshness

    monkeypatch.setenv("ENGAGEMENT_TOKENS", "reviewer-tok:kb:review;other-tok:eng-1")

    # Unauthorized without scope
    set_current_caller("other-tok")
    unauth = get_kb_freshness()
    assert unauth.get("status") == "unauthorized"

    # Authorized with kb:review
    set_current_caller("reviewer-tok")
    res = get_kb_freshness()
    assert res.get("status") == "ok"
    assert "data" in res
    assert "summary" in res["data"]


def test_api_kb_freshness_endpoint(monkeypatch):
    monkeypatch.setenv("ENGAGEMENT_TOKENS", "reviewer-tok:kb:review;other-tok:eng-1")
    client = TestClient(create_starlette_app(), raise_server_exceptions=False)

    # Without token -> 401 (unauthenticated)
    r = client.get("/api/knowledge/freshness")
    assert r.status_code == 401

    # With other token (no kb:review) -> 403
    r = client.get("/api/knowledge/freshness", headers={"Authorization": "Bearer other-tok"})
    assert r.status_code == 403

    # With reviewer token
    r = client.get("/api/knowledge/freshness", headers={"Authorization": "Bearer reviewer-tok"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    assert "summary" in data.get("data", {})
