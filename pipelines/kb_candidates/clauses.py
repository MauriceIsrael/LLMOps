"""Decision on each check clause of the doctrine (contract 1.26, issues #101 and #105).

A clause becomes opposable (``status: validated``, it blocks an arbitration) only through an explicit decision on
*that* clause by a reviewer of the asset's domain: ``validate``, ``amend`` (validate a corrected clause) or ``reject``
(never evaluated again). Accepting a whole asset never validates its clauses (``carry_clause_decisions``).

Every decision rewrites the asset (new ``revision``) and is appended to ``data/kb/clause-decisions.jsonl``, the
versioned trail of who decided what. The next publication re-ingests the base, seals a snapshot and lists the
decisions in the CHANGELOG (``pending_decisions`` / ``mark_published``).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipelines.doctrine.checks import aggregate_checks_status, clause_status, validate_clause
from pipelines.kb_candidates.kb import join_frontmatter, load_assets, split_frontmatter
from pipelines.kb_candidates.model import CandidateError, CandidateNotFoundError
from pipelines.knowledge_ref import bump_revision

DECISIONS = ("validate", "amend", "reject")
TRAIL = "clause-decisions.jsonl"
RULE_KEYS = ("kind", "when", "expect", "message")
EXCERPT_CHARS = 1200


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _same_rule(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return all(a.get(k) == b.get(k) for k in RULE_KEYS)


def carry_clause_decisions(fm: dict[str, Any], previous: dict[str, Any] | None) -> None:
    """Statuses of the clauses of an asset being promoted (#101).

    A clause identical to the one of the asset it replaces keeps its status and review; any new or modified clause
    is a draft, whatever the proposed content says. ``checks_status`` becomes the aggregate of the clauses.
    """
    before = {c.get("id"): c for c in (previous or {}).get("checks") or [] if isinstance(c, dict)}
    before_status = (previous or {}).get("checks_status")
    for clause in fm.get("checks") or []:
        if not isinstance(clause, dict):
            continue
        old = before.get(clause.get("id"))
        if old is not None and _same_rule(old, clause):
            clause["status"] = clause_status(old, before_status)
            if old.get("review"):
                clause["review"] = old["review"]
            else:
                clause.pop("review", None)
        else:
            clause["status"] = "draft"
            clause.pop("review", None)
    fm["checks_status"] = aggregate_checks_status([c for c in fm.get("checks") or [] if isinstance(c, dict)])


def _excerpt(body: str) -> str:
    text = body.strip()
    return text if len(text) <= EXCERPT_CHARS else text[:EXCERPT_CHARS].rstrip() + "…"


def _row(asset: Any, clause: dict[str, Any]) -> dict[str, Any]:
    fm = asset.frontmatter
    domain = fm.get("domain") or []
    return {
        "asset_id": asset.id,
        "typed_id": f"{asset.type}:{asset.id}",
        "asset_type": asset.type,
        "asset_title": asset.title,
        "asset_title_fr": fm.get("title_fr"),
        "asset_status": fm.get("status"),
        "framework": fm.get("framework"),
        "severity": fm.get("severity"),
        "domain": [str(d) for d in (domain if isinstance(domain, list) else [domain])],
        "owner": fm.get("owner"),
        "source_ref": fm.get("source_ref"),
        "asset_excerpt": _excerpt(asset.body),
        "check_id": clause.get("id"),
        "kind": clause.get("kind"),
        "when": clause.get("when"),
        "expect": clause.get("expect"),
        "message": clause.get("message"),
        "status": clause_status(clause, fm.get("checks_status")),
        "review": clause.get("review"),
        "revision": fm.get("revision", 1),
    }


def list_clauses(kb_dir: str | Path, status: str | None = None, framework: str | None = None,
                 asset_type: str | None = None, asset_id: str | None = None) -> list[dict[str, Any]]:
    """Every check clause of the active doctrine, with its asset and its effective status."""
    rows = []
    for asset in load_assets(kb_dir):
        fm = asset.frontmatter
        if fm.get("status") != "active" or not isinstance(fm.get("checks"), list):
            continue
        if framework and str(fm.get("framework") or "").lower() != framework.lower():
            continue
        if asset_type and asset.type != asset_type:
            continue
        if asset_id and asset.id != asset_id:
            continue
        for clause in fm["checks"]:
            if isinstance(clause, dict):
                row = _row(asset, clause)
                if status is None or row["status"] == status:
                    rows.append(row)
    return rows


def mandatory_without_clause(kb_dir: str | Path, framework: str | None = None) -> list[dict[str, Any]]:
    """Active mandatory controls that carry no clause: nothing of them can block an arbitration."""
    out = []
    for asset in load_assets(kb_dir):
        fm = asset.frontmatter
        if asset.type != "control" or fm.get("status") != "active" or fm.get("severity") != "mandatory":
            continue
        if framework and str(fm.get("framework") or "").lower() != framework.lower():
            continue
        if not fm.get("checks"):
            out.append({"asset_id": asset.id, "asset_title": asset.title, "asset_title_fr": fm.get("title_fr"),
                        "framework": fm.get("framework"), "domain": fm.get("domain") or [],
                        "source_ref": fm.get("source_ref"), "asset_excerpt": _excerpt(asset.body)})
    return out


def find_asset(kb_dir: str | Path, asset_id: str) -> Any:
    asset = next((a for a in load_assets(kb_dir) if a.id == asset_id), None)
    if asset is None:
        raise CandidateNotFoundError(asset_id)
    return asset


def decide(kb_dir: str | Path, asset_id: str, check_id: str, decision: str, reviewer: str,
           comment: str | None = None, amended: dict[str, Any] | None = None) -> dict[str, Any]:
    """Record a decision on one clause; returns the clause row after the decision."""
    if decision not in DECISIONS:
        raise CandidateError("decision", f"'decision' must be one of {list(DECISIONS)}.")
    comment = (comment or "").strip() or None
    if decision in ("reject", "amend") and not comment:
        raise CandidateError("comment", f"a comment is required to {decision} a clause.")
    asset = find_asset(kb_dir, asset_id)
    text = asset.path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(text)
    if fm is None or not isinstance(fm.get("checks"), list):
        raise CandidateNotFoundError(f"{asset_id}/{check_id}")
    clauses = [c for c in fm["checks"] if isinstance(c, dict)]
    clause = next((c for c in clauses if c.get("id") == check_id), None)
    if clause is None:
        raise CandidateNotFoundError(f"{asset_id}/{check_id}")

    # Materialize the inherited statuses so that the asset no longer depends on its aggregate.
    for c in clauses:
        c["status"] = clause_status(c, fm.get("checks_status"))
    before = {k: clause.get(k) for k in (*RULE_KEYS, "status")}

    if decision == "amend":
        if not isinstance(amended, dict):
            raise CandidateError("clause", "'clause' (kind, when, expect, message) is required to amend.")
        candidate = {"id": check_id, **{k: amended.get(k, clause.get(k)) for k in RULE_KEYS}}
        if candidate.get("kind") == "forbids":
            candidate.pop("expect", None)
        candidate = {k: v for k, v in candidate.items() if v is not None}
        problems = validate_clause(candidate)
        if problems:
            raise CandidateError("clause", "; ".join(problems))
        for k in RULE_KEYS:
            clause.pop(k, None)
        clause.update({k: candidate[k] for k in RULE_KEYS if k in candidate})

    clause["status"] = "rejected" if decision == "reject" else "validated"
    clause["review"] = {"by": reviewer, "at": _now(), "decision": decision, **({"comment": comment} if comment else {})}
    fm["checks_status"] = aggregate_checks_status(clauses)
    fm["revision"] = bump_revision(text)
    fm["last_reviewed"] = datetime.now(UTC).date().isoformat()
    asset.path.write_text(join_frontmatter(fm, body), encoding="utf-8")

    entry = {"asset_id": asset_id, "check_id": check_id, "decision": decision, "by": reviewer,
             "at": clause["review"]["at"], "comment": comment, "revision": fm["revision"],
             "before": before, "after": {k: clause.get(k) for k in (*RULE_KEYS, "status")}, "published_in": None}
    trail = Path(kb_dir) / TRAIL
    with trail.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return _row(find_asset(kb_dir, asset_id), clause)


def _read_trail(kb_dir: str | Path) -> list[dict[str, Any]]:
    trail = Path(kb_dir) / TRAIL
    if not trail.exists():
        return []
    return [json.loads(line) for line in trail.read_text(encoding="utf-8").splitlines() if line.strip()]


def decisions(kb_dir: str | Path, asset_id: str | None = None) -> list[dict[str, Any]]:
    return [d for d in _read_trail(kb_dir) if asset_id is None or d["asset_id"] == asset_id]


def pending_decisions(kb_dir: str | Path) -> list[dict[str, Any]]:
    """Decisions written in the base but not yet in a published snapshot."""
    return [d for d in _read_trail(kb_dir) if not d.get("published_in")]


def mark_published(kb_dir: str | Path, snapshot_id: str | None) -> None:
    entries = _read_trail(kb_dir)
    if not entries:
        return
    for d in entries:
        if not d.get("published_in"):
            d["published_in"] = snapshot_id or "unsealed"
    (Path(kb_dir) / TRAIL).write_text(
        "".join(json.dumps(d, ensure_ascii=False, sort_keys=True) + "\n" for d in entries), encoding="utf-8")
