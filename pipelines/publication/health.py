"""Health indicators of the knowledge base (``GET /api/knowledge/health``)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipelines.frameworks.coverage import compute_framework_coverage
from pipelines.kb_candidates.kb import load_assets
from pipelines.kb_candidates.service import (
    REMINDER_BUSINESS_DAYS,
    CandidateService,
    business_days_between,
)
from pipelines.publication.local_publisher import storage_status

DOCTRINE_TYPES = ("principle", "pattern", "decision", "control")


def _last_snapshot(snapshot_dir: Path) -> dict[str, Any] | None:
    latest = snapshot_dir / "latest.json"
    if not latest.is_file():
        return None
    try:
        data = json.loads(latest.read_text(encoding="utf-8"))
    except ValueError:
        return None
    return {"snapshot_id": data.get("snapshot_id"), "generated_at": data.get("created_at")}


def _queue(service: CandidateService, now: datetime) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    per_owner: dict[str, dict[str, Any]] = {}
    overdue = []
    for c in service.repo.all():
        by_status[c["status"]] = by_status.get(c["status"], 0) + 1
        if c["status"] != "in_review":
            continue
        history = c.get("history") or []
        entered = next((h["at"] for h in reversed(history) if h.get("event") in (
            "in_review", "first_review_accepted", "assigned")), c["created_at"])
        waited = business_days_between(datetime.strptime(entered, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC), now)
        entry = per_owner.setdefault(c.get("assigned_owner") or "unassigned", {"waiting": 0, "oldest_business_days": 0})
        entry["waiting"] += 1
        entry["oldest_business_days"] = max(entry["oldest_business_days"], waited)
        if waited >= REMINDER_BUSINESS_DAYS:
            overdue.append({"candidate_id": c["id"], "owner": c.get("assigned_owner"), "business_days": waited})
    return {"by_status": by_status, "per_owner": dict(sorted(per_owner.items())),
            "overdue": sorted(overdue, key=lambda o: -o["business_days"])}


def kb_health(service: CandidateService, kb_dir: Path, snapshot_dir: Path, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    assets = [a for a in load_assets(kb_dir) if a.type in DOCTRINE_TYPES and a.frontmatter.get("status") == "active"]
    by_type: dict[str, int] = {}
    by_domain: dict[str, int] = {}
    unvalidated = []
    clauses = draft_clauses = 0
    for a in assets:
        by_type[a.type] = by_type.get(a.type, 0) + 1
        domains = a.frontmatter.get("domain") or []
        for d in (domains if isinstance(domains, list) else [domains]):
            by_domain[str(d)] = by_domain.get(str(d), 0) + 1
        if not a.frontmatter.get("validated_by"):
            unvalidated.append(a.id)
        checks = a.frontmatter.get("checks") or []
        if isinstance(checks, list) and checks:
            clauses += len(checks)
            if str(a.frontmatter.get("checks_status") or "draft") != "validated":
                draft_clauses += len(checks)
    frameworks = sorted(d.name for d in (kb_dir / "controls").iterdir() if d.is_dir()) if (kb_dir / "controls").is_dir() else []
    coverage = compute_framework_coverage(frameworks, kb_dir)

    evaluation: dict[str, Any] | None = None
    unassessed_share = None
    from pipelines.governance.store import database_url

    if database_url():
        from pipelines.governance.evals import EvalStore

        store = EvalStore()
        if store.has_dataset("check_option_v1"):
            cases = store.cases("check_option_v1")
            runs = store.runs("check_option_v1")
            last = store.run("check_option_v1", runs[0]["id"]) if runs else None
            counts = (last or {}).get("verdict_counts") or {}
            total = sum(counts.values())
            unassessed_share = round(counts.get("unassessed", 0) / total, 4) if total else None
            evaluation = {"cases": len(cases), "validated_cases": sum(1 for c in cases if c["annotation_status"] == "validated"),
                          "last_run": None if last is None else {k: last.get(k) for k in (
                              "id", "at", "run_by", "violation_recall", "supports_recall", "cases")}}
    return {
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "assets": {"active": len(assets), "by_type": dict(sorted(by_type.items())), "by_domain": dict(sorted(by_domain.items())),
                   "unvalidated": {"count": len(unvalidated), "ids": unvalidated[:50]}},
        "clauses": {"total": clauses, "draft": draft_clauses, "unassessed_verdict_share": unassessed_share},
        "coverage": {fw: {"status": c["status"], "expected": c["expected"], "present": c["present"],
                          "validated": c["validated"], "provisional": c["provisional"]} for fw, c in coverage.items()},
        "queue": _queue(service, now),
        "evaluation": evaluation,
        "last_snapshot": _last_snapshot(snapshot_dir),
        "storage": storage_status(),
    }
