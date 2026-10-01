"""Framework ingestion through the API (lot L8): the CLI chain of L3, driven row by row.

The source is extracted in a bounded subprocess (``kb ingest-framework``), the drafts and
the expert's decisions live in the governance database (table ``framework_ingestions`` /
``ingestion_rows``) instead of a CSV sheet, and ``apply`` replays the same ``apply_review`` as
``kb apply-review`` on a temporary sheet. Nothing here calls an LLM: proposals of links come
from the client (``llm-derived``) and are validated against the existing assets.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select

from pipelines.frameworks.ingest import INGESTION_FILE, latest_staging, load_manifest
from pipelines.frameworks.review import DECISIONS, SHEET_COLUMNS, _legal_text, apply_review
from pipelines.frameworks.splitter import SPLITTERS_DIR
from pipelines.governance.log import now_iso
from pipelines.governance.store import framework_ingestions, get_engine, ingestion_rows
from pipelines.kb_candidates.kb import load_assets, split_frontmatter
from pipelines.kb_candidates.service import CandidateService

MAX_SOURCE_BYTES = 20 * 1024 * 1024
EXTRACTION_TIMEOUT_SECONDS = 120
ALLOWED_SUFFIXES = (".pdf", ".html", ".htm", ".txt", ".md", ".docx")
LINKABLE_TYPES = ("principle", "pattern", "decision")


class IngestionError(ValueError):
    def __init__(self, argument: str, reason: str) -> None:
        super().__init__(reason)
        self.argument, self.reason = argument, reason


class IngestionNotFoundError(LookupError):
    pass


def supported_frameworks() -> list[str]:
    return sorted(p.stem.upper() for p in SPLITTERS_DIR.glob("*.yaml"))


def _list(value: Any, argument: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise IngestionError(argument, f"'{argument}' must be a list of strings.")
    return [v.strip() for v in value if v.strip()]


class IngestionService:
    def __init__(self, kb_dir: str | Path, service: CandidateService | None = None, url: str | None = None) -> None:
        self.kb_dir = Path(kb_dir)
        self.service = service
        self.engine = get_engine(url)

    # ----------------------------------------------------------------- storage

    def _rows(self, ingestion_id: int) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(ingestion_rows).where(ingestion_rows.c.ingestion_id == ingestion_id)
                                .order_by(ingestion_rows.c.position)).all()
        return [{"requirement_id": r.requirement_id, **json.loads(r.doc)} for r in rows]

    def _save_row(self, ingestion_id: int, row: dict[str, Any], position: int | None = None) -> None:
        doc = {k: v for k, v in row.items() if k != "requirement_id"}
        with self.engine.begin() as conn:
            conn.execute(ingestion_rows.update().where(
                (ingestion_rows.c.ingestion_id == ingestion_id)
                & (ingestion_rows.c.requirement_id == row["requirement_id"])).values(doc=json.dumps(doc, ensure_ascii=False)))

    def _header(self, ingestion_id: int) -> dict[str, Any]:
        with self.engine.connect() as conn:
            r = conn.execute(select(framework_ingestions).where(framework_ingestions.c.id == ingestion_id)).first()
        if r is None:
            raise IngestionNotFoundError(f"ingestions/{ingestion_id}")
        return dict(r._mapping)

    def list(self) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(framework_ingestions).order_by(framework_ingestions.c.id.desc())).all()
        return [dict(r._mapping) for r in rows]

    def get(self, ingestion_id: int) -> dict[str, Any]:
        header = self._header(ingestion_id)
        rows = self._rows(ingestion_id)
        light = [{k: v for k, v in r.items() if k != "draft"} for r in rows]
        decided = sum(1 for r in rows if r.get("decision"))
        return {**header, "requirements": light, "decided": decided, "total": len(rows)}

    # ------------------------------------------------------------------ upload

    def create(self, framework: str, version: str, tag: str, filename: str, data: bytes, created_by: str) -> dict[str, Any]:
        framework, version, tag = framework.strip(), version.strip(), (tag or "").strip()
        if not framework or not version:
            raise IngestionError("framework", "'framework' and 'version' are required.")
        if framework.upper() not in supported_frameworks():
            raise IngestionError("framework", f"no splitter for '{framework}' (available: {supported_frameworks()}); "
                                 "a maintainer must write pipelines/frameworks/splitters/<framework>.yaml first.")
        name = Path(filename or "").name
        if Path(name).suffix.lower() not in ALLOWED_SUFFIXES:
            raise IngestionError("file", f"the source must be one of {list(ALLOWED_SUFFIXES)}.")
        if not data or len(data) > MAX_SOURCE_BYTES:
            raise IngestionError("file", f"the source must be between 1 byte and {MAX_SOURCE_BYTES // (1024 * 1024)} MB.")
        before = (load_manifest(self.kb_dir, framework) or {}).get("coverage_declared_by")
        with tempfile.TemporaryDirectory(prefix="llmops-ingest-") as tmp:
            source = Path(tmp) / name
            source.write_bytes(data)
            staging = Path(tmp) / "staging"
            cmd = [sys.executable, "-m", "pipelines.kb_cli", "ingest-framework", "--framework", framework,
                   "--version", version, "--source", str(source), "--kb-dir", str(self.kb_dir),
                   "--staging-dir", str(staging)]
            if tag:
                cmd += ["--tag", tag]
            try:
                import os
                sub_env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    env=sub_env,
                    timeout=EXTRACTION_TIMEOUT_SECONDS,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise IngestionError("file", f"extraction exceeded {EXTRACTION_TIMEOUT_SECONDS} s.") from exc
            if proc.returncode != 0:
                detail = (proc.stdout + proc.stderr).strip().splitlines()
                raise IngestionError("file", (detail[-1] if detail else "extraction failed")[:300])
            run_dir = latest_staging(staging, framework)
            meta = yaml.safe_load((run_dir / INGESTION_FILE).read_text(encoding="utf-8"))
            rows = []
            for req_id in meta["requirements"]:
                text = (run_dir / f"{req_id}.md").read_text(encoding="utf-8")
                fm, body = split_frontmatter(text)
                fm = fm or {}
                rows.append({"requirement_id": req_id, "title": fm.get("title", ""), "source_ref": fm.get("source_ref", ""),
                             "domain": list(fm.get("domain") or []),
                             "in_kb": (self.kb_dir / "controls" / meta["framework"] / f"{req_id}.md").exists(),
                             "legal_text": _legal_text(body), "draft": text,
                             "proposed_links": [], "proposed_acceptance_criteria": [], "links_production_mode": "",
                             "decision": "", "links": [], "acceptance_criteria": [], "reviewer": "", "comment": "",
                             "status": "pending", "result": None})
        after = (load_manifest(self.kb_dir, framework) or {}).get("coverage_declared_by")
        with self.engine.begin() as conn:
            res = conn.execute(framework_ingestions.insert().values(
                framework=meta["framework"], version=version, tag=tag or None, source_name=name,
                source_sha256=meta["source"]["sha256"], status="reviewing", created_by=created_by, created_at=now_iso(),
                declaration_reset=bool(before) and not after))
            ingestion_id = int((res.inserted_primary_key or (0,))[0])
            for position, row in enumerate(rows):
                conn.execute(ingestion_rows.insert().values(
                    ingestion_id=ingestion_id, requirement_id=row["requirement_id"], position=position,
                    doc=json.dumps({k: v for k, v in row.items() if k != "requirement_id"}, ensure_ascii=False)))
        return self.get(ingestion_id)

    # -------------------------------------------------------------- row review

    def _row(self, ingestion_id: int, requirement_id: str) -> dict[str, Any]:
        self._header(ingestion_id)
        row = next((r for r in self._rows(ingestion_id) if r["requirement_id"] == requirement_id), None)
        if row is None:
            raise IngestionNotFoundError(f"ingestions/{ingestion_id}/rows/{requirement_id}")
        return row

    def decide(self, ingestion_id: int, requirement_id: str, reviewer: str, body: dict[str, Any]) -> dict[str, Any]:
        """Decision of the expert (the reviewer is the acting expert, never a field of the body)."""
        header, row = self._header(ingestion_id), self._row(ingestion_id, requirement_id)
        if header["status"] == "applied":
            raise IngestionError("status", "the ingestion is fully applied.")
        if row["status"] == "applied":
            raise IngestionError("status", "this requirement was already applied.")
        decision = str(body.get("decision") or "").strip().lower()
        if decision and decision not in DECISIONS:
            raise IngestionError("decision", f"'decision' must be one of {list(DECISIONS)} (empty clears it).")
        links = _list(body.get("links"), "links")
        criteria = _list(body.get("acceptance_criteria"), "acceptance_criteria")
        unknown = sorted(set(links) - {a.id for a in load_assets(self.kb_dir)})
        if unknown:
            raise IngestionError("links", f"unknown asset(s): {unknown}.")
        if decision == "amend" and not (links or criteria):
            raise IngestionError("decision", "'amend' needs links and/or acceptance_criteria.")
        row.update(decision=decision, links=links, acceptance_criteria=criteria,
                   reviewer=reviewer if decision else "", comment=str(body.get("comment") or "").strip(),
                   status="decided" if decision else "pending", result=None)
        self._save_row(ingestion_id, row)
        return {k: v for k, v in row.items() if k != "draft"}

    def add_link_proposals(self, ingestion_id: int, proposals: Any, model: str | None) -> dict[str, Any]:
        """Proposals made by the client's own LLM: stored as ``llm-derived``, validated against active assets."""
        self._header(ingestion_id)
        if not isinstance(proposals, list) or not proposals:
            raise IngestionError("proposals", "'proposals' must be a non-empty list.")
        known = {a.id for a in load_assets(self.kb_dir) if a.type in LINKABLE_TYPES and a.frontmatter.get("status") == "active"}
        rows = {r["requirement_id"]: r for r in self._rows(ingestion_id)}
        updated, dropped, unknown_reqs = 0, 0, []
        for item in proposals:
            req = str((item or {}).get("requirement_id") or "")
            if req not in rows:
                unknown_reqs.append(req)
                continue
            links = [x for x in _list(item.get("satisfied_by"), "satisfied_by") if x in known]
            dropped += len(_list(item.get("satisfied_by"), "satisfied_by")) - len(links)
            rows[req].update(proposed_links=links, proposed_acceptance_criteria=_list(item.get("acceptance_criteria"),
                                                                                    "acceptance_criteria"),
                             links_production_mode="llm-derived", links_model=model)
            self._save_row(ingestion_id, rows[req])
            updated += 1
        return {"updated": updated, "dropped_unknown_links": dropped, "unknown_requirements": unknown_reqs}

    # ------------------------------------------------------------------- apply

    def apply(self, ingestion_id: int, actor: str) -> dict[str, Any]:
        """Same as ``kb apply-review``: reviewed candidates, then promotion of the accepted ones."""
        if self.service is None:
            raise RuntimeError("apply needs a CandidateService")
        header, rows = self._header(ingestion_id), self._rows(ingestion_id)
        decided = [r for r in rows if r["decision"] and r["status"] != "applied"]
        if not decided:
            raise IngestionError("decisions", "no decided requirement to apply.")
        with tempfile.TemporaryDirectory(prefix="llmops-apply-") as tmp:
            staging = Path(tmp)
            for r in rows:
                (staging / f"{r['requirement_id']}.md").write_text(self._draft_with_proposals(r), encoding="utf-8")
            (staging / INGESTION_FILE).write_text(yaml.safe_dump({
                "framework": header["framework"], "version": header["version"],
                "source": {"file": header["source_name"], "sha256": header["source_sha256"]},
                "requirements": [r["requirement_id"] for r in rows]}), encoding="utf-8")
            sheet = staging / f"ingestion-{ingestion_id}.csv"
            with sheet.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=SHEET_COLUMNS)
                writer.writeheader()
                for r in decided:
                    writer.writerow({
                        "requirement_id": r["requirement_id"], "decision": r["decision"], "reviewer": r["reviewer"],
                        "links": "; ".join(r["links"]), "acceptance_criteria": "; ".join(r["acceptance_criteria"]),
                        "comment": r["comment"]})
            results = apply_review(sheet, self.service, staging=staging)
        failed = {f["requirement"]: f["reason"] for f in results["failed"]}
        for r in decided:
            rid = r["requirement_id"]
            if rid in failed:
                r.update(status="failed", result=failed[rid])
            else:
                r.update(status="applied", result="promoted" if rid in results["promoted"] else "rejected")
            self._save_row(ingestion_id, r)
        now = self._rows(ingestion_id)
        if all(x["status"] == "applied" for x in now):
            status = "applied"
        elif any(x["status"] in ("applied", "failed") for x in now):
            status = "partially_applied"
        else:
            status = "reviewing"
        with self.engine.begin() as conn:
            conn.execute(framework_ingestions.update().where(framework_ingestions.c.id == ingestion_id).values(status=status))
        return {**results, "status": status, "applied_by": actor}

    @staticmethod
    def _draft_with_proposals(row: dict[str, Any]) -> str:
        text: str = row["draft"]
        if not row.get("proposed_links") and not row.get("proposed_acceptance_criteria"):
            return text
        from pipelines.kb_candidates.kb import join_frontmatter

        fm, body = split_frontmatter(text)
        fm = fm or {}
        fm["proposed_links"] = row.get("proposed_links") or []
        fm["proposed_acceptance_criteria"] = row.get("proposed_acceptance_criteria") or []
        fm["links_production_mode"] = row.get("links_production_mode") or "llm-derived"
        return join_frontmatter(fm, body)

