"""Expert review of an ingested framework: ``kb review-sheet`` and ``kb apply-review``.

``review-sheet`` writes a CSV (to fill in) and a Markdown view: one row per requirement,
with the proposed links and acceptance criteria. The expert fills ``decision``
(``accept`` | ``amend`` | ``reject``), ``reviewer`` (an owner handle), ``comment`` and,
for ``amend``, ``links`` / ``acceptance_criteria`` (items separated by ``;``).

``apply-review`` turns each decided row into a ``framework_ingestion`` candidate, runs the
automatic checks, records the expert's review and promotes accepted rows into
``data/kb/controls/<FW>/`` (``status: active``, ``validated_by``). An existing control is
amended in place: its curated text is kept, the reviewed links (``satisfied_by``) and the
source fingerprint are updated.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

import yaml

from pipelines.frameworks.ingest import INGESTION_FILE
from pipelines.kb_candidates.kb import join_frontmatter, split_frontmatter
from pipelines.kb_candidates.service import CandidateService

SHEET_COLUMNS = [
    "requirement_id", "title", "source_ref", "in_kb", "proposed_links", "proposed_acceptance_criteria",
    "links_production_mode", "legal_text", "decision", "links", "acceptance_criteria", "reviewer", "comment",
]
DECISIONS = ("accept", "amend", "reject")


def _items(value: str | None) -> list[str]:
    return [x.strip() for x in (value or "").split(";") if x.strip()]


def _legal_text(body: str) -> str:
    match = re.search(r"## Legal Requirement\n(.*?)(?:\n## |\Z)", body, re.DOTALL)
    return " ".join((match.group(1) if match else "").split())


def _control_path(kb_dir: Path, framework: str, control_id: str) -> Path:
    return kb_dir / "controls" / framework / f"{control_id}.md"


def write_review_sheet(staging: str | Path, kb_dir: str | Path = "data/kb") -> dict[str, str]:
    staging = Path(staging)
    kb_dir = Path(kb_dir)
    meta = yaml.safe_load((staging / INGESTION_FILE).read_text(encoding="utf-8"))
    rows = []
    for req_id in meta["requirements"]:
        fm, body = split_frontmatter((staging / f"{req_id}.md").read_text(encoding="utf-8"))
        fm = fm or {}
        rows.append({
            "requirement_id": req_id,
            "title": fm.get("title", ""),
            "source_ref": fm.get("source_ref", ""),
            "in_kb": "yes" if _control_path(kb_dir, meta["framework"], req_id).exists() else "no",
            "proposed_links": "; ".join(fm.get("proposed_links") or []),
            "proposed_acceptance_criteria": "; ".join(fm.get("proposed_acceptance_criteria") or []),
            "links_production_mode": fm.get("links_production_mode", ""),
            "legal_text": _legal_text(body),
            "decision": "", "links": "", "acceptance_criteria": "", "reviewer": "", "comment": "",
        })
    csv_path = staging / "review_sheet.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    md = [
        f"# Review sheet — {meta['framework']} {meta['version']}",
        "",
        f"Source: `{meta['source']['file']}` (SHA-256 `{meta['source']['sha256']}`). Fill in `review_sheet.csv` "
        "(`decision`: accept | amend | reject, `reviewer`: owner handle, `comment`; for amend, `links` and "
        "`acceptance_criteria` separated by `;`), then run `kb apply-review`.",
        "",
        "| Requirement | In KB | Proposed links | Proposed acceptance criteria | Mode |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        md.append(f"| {r['requirement_id']} — {r['title']} | {r['in_kb']} | {r['proposed_links'] or '—'} | "
                  f"{r['proposed_acceptance_criteria'] or '—'} | {r['links_production_mode'] or '—'} |")
    md_path = staging / "review_sheet.md"
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return {"csv": str(csv_path), "markdown": str(md_path), "rows": str(len(rows))}


def _with_criteria(body: str, criteria: list[str]) -> str:
    section = "## Architecture Acceptance Criteria\n" + "\n".join(f"- {c}" for c in criteria) + "\n"
    pattern = re.compile(r"## Architecture Acceptance Criteria\n.*?(?=\n## |\Z)", re.DOTALL)
    if pattern.search(body):
        return pattern.sub(section.rstrip("\n"), body)
    return body.rstrip() + "\n\n" + section


def _content_for(row: dict[str, str], staging: Path, kb_dir: Path, meta: dict[str, Any]) -> tuple[str, str | None, bool]:
    """(proposed content, target asset id when the control exists, links came from an LLM)."""
    req_id = row["requirement_id"]
    draft_fm, draft_body = split_frontmatter((staging / f"{req_id}.md").read_text(encoding="utf-8"))
    draft_fm = draft_fm or {}
    amend = row["decision"] == "amend"
    links = _items(row.get("links")) if amend and row.get("links") else list(draft_fm.get("proposed_links") or [])
    criteria = (_items(row.get("acceptance_criteria")) if amend and row.get("acceptance_criteria")
                else list(draft_fm.get("proposed_acceptance_criteria") or []))
    llm_links = (not amend or not row.get("links")) and draft_fm.get("links_production_mode") == "llm-derived" and bool(links)

    existing = _control_path(kb_dir, meta["framework"], req_id)
    if existing.exists():
        fm, body = split_frontmatter(existing.read_text(encoding="utf-8"))
        fm = fm or {}
        target: str | None = req_id
        if amend and row.get("acceptance_criteria"):
            body = _with_criteria(body, criteria)
    else:
        fm, body, target = dict(draft_fm), draft_body, None
        if criteria:
            body = _with_criteria(body, criteria)
    proposed_terms = [str(x) for x in draft_fm.get("proposed_terms") or []]
    proposed_title_fr = str(draft_fm.get("proposed_title_fr") or "")
    terms_mode = draft_fm.get("terms_production_mode")
    title_override = bool(draft_fm.get("title_fr_override"))
    for key in ("proposed_links", "proposed_acceptance_criteria", "links_model", "links_production_mode",
                "proposed_terms", "proposed_title_fr", "terms_production_mode", "title_fr_override"):
        fm.pop(key, None)
    if proposed_terms:
        # Search terms are merged with those of an existing (curated) control, never replaced.
        fm["terms"] = list(dict.fromkeys([*[str(x) for x in fm.get("terms") or []], *proposed_terms]))
        fm["terms_production_mode"] = terms_mode or "human-authored"
    if proposed_title_fr and (title_override or not fm.get("title_fr")):  # a proposal never overwrites a curated title
        fm["title_fr"] = proposed_title_fr
    if links:
        fm["satisfied_by"] = links
        fm["links_production_mode"] = "llm-proposed-human-approved" if llm_links else "human-authored"
    fm["version"] = meta["version"]
    fm["source_sha256"] = meta["source"]["sha256"]
    fm.setdefault("source_ref", draft_fm.get("source_ref"))
    return join_frontmatter(fm, body), target, llm_links


def apply_review(
    sheet: str | Path,
    service: CandidateService,
    staging: str | Path | None = None,
) -> dict[str, Any]:
    sheet = Path(sheet)
    staging = Path(staging) if staging else sheet.parent
    meta = yaml.safe_load((staging / INGESTION_FILE).read_text(encoding="utf-8"))
    kb_dir = service.kb_dir
    results: dict[str, Any] = {"promoted": [], "rejected": [], "failed": [], "skipped": []}
    with sheet.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        req_id = row.get("requirement_id", "")
        decision = (row.get("decision") or "").strip().lower()
        if decision not in DECISIONS:
            results["skipped"].append(req_id)
            continue
        reviewer = (row.get("reviewer") or "").strip()
        if not reviewer:
            results["failed"].append({"requirement": req_id, "reason": "missing reviewer"})
            continue
        row = {**row, "decision": decision}
        content, target, llm_links = _content_for(row, staging, kb_dir, meta)
        fm, _ = split_frontmatter(content)
        payload = {
            "kind": "framework_ingestion",
            "asset_type": "control",
            "target_asset_id": target,
            "domain": list((fm or {}).get("domain") or []),
            "title": str((fm or {}).get("title") or req_id),
            "rationale": f"{meta['framework']} {meta['version']} ingestion — review sheet {sheet.name}",
            "proposed_content": content,
            "source": {"system": "cli-ingestion", "author": reviewer,
                       "production_mode": "llm-proposed-human-approved" if llm_links else "human-authored"},
            "evidence": [{"kind": "audit",
                          "ref": f"expert review sheet {sheet.name} ({reviewer}); source sha256:{meta['source']['sha256']}"}],
        }
        try:
            candidate = service.submit(payload, actor=f"kb apply-review:{reviewer}")
            if candidate["status"] == "checks_failed":
                failed = [f"{c['name']}: {c['detail']}" for c in candidate["checks"] if c["status"] == "fail"]
                results["failed"].append({"requirement": req_id, "candidate": candidate["id"], "reason": "; ".join(failed)})
                continue
            reason = (row.get("comment") or "").strip() or f"{decision} in review sheet {sheet.name}"
            if decision == "reject":
                service.review(candidate["id"], "reject", reviewer, reason=reason, actor="kb apply-review")
                results["rejected"].append(req_id)
                continue
            reviewed = service.review(candidate["id"], "accept", reviewer, reason=reason, actor="kb apply-review")
            if reviewed["status"] != "accepted":
                results["failed"].append({"requirement": req_id, "candidate": candidate["id"],
                                          "reason": f"status {reviewed['status']} (second review required)"})
                continue
            service.promote(candidate["id"], actor="kb apply-review")
            results["promoted"].append(req_id)
        except Exception as exc:  # report per row, keep going
            results["failed"].append({"requirement": req_id, "reason": str(exc)})
    return results
