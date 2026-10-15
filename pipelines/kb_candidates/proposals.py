"""The channel of proposals from the suite to the Hub (K7, ADR-KH-01 amendment KH-1).

A suite application never calls the Hub: it **publishes** a sealed snapshot of proposals and the Hub **reads** it
(``schemas/proposal_snapshot.schema.json``, the suite envelope sealed with the canonical-json v1 profile). Every proposal becomes
a candidate of the existing cycle (automatic checks, anonymisation, review by the owner of the domain, double validation): the
channel adds provenance (emitter, ``snapshotId``, checksum, the candidate inside the snapshot) and nothing else. Nothing becomes
active without a human review; a tampered snapshot is refused whole; importing a snapshot twice creates nothing twice.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import jsonschema

from pipelines import canonical
from pipelines.bundle.verify import Problem
from pipelines.kb_candidates.model import CandidateError

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "proposal_snapshot.schema.json"


class ProposalSnapshotError(ValueError):
    """The snapshot is refused as a whole; ``problems`` say why (same shape as the other sealed snapshots)."""

    def __init__(self, problems: list[Problem]) -> None:
        super().__init__("; ".join(f"{p.code} {p.path}: {p.message}" for p in problems[:3]))
        self.problems = problems


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def verify(envelope: Any) -> list[Problem]:
    """Everything that makes a snapshot unfit to read: shape, seal, duplicate candidates, amendments without target."""
    problems: list[Problem] = []
    validator = jsonschema.Draft7Validator(load_schema())
    for err in sorted(validator.iter_errors(envelope), key=lambda e: list(e.path)):
        problems.append(Problem("SCHEMA", "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in err.path), err.message[:200]))
    if problems:
        return problems
    try:
        checksum = canonical.sha256(envelope["data"])
    except canonical.CanonicalError as err:
        return [Problem("CANONICAL", "$.data", str(err))]
    if envelope["checksum"] != checksum:
        problems.append(Problem("SEAL", "$.checksum", "the checksum is not the sha256 of data at the canonical-json v1 profile: the snapshot was altered"))
    ids = [c["id"] for c in envelope["data"]["candidates"]]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        problems.append(Problem("DUPLICATE_ID", "$.data.candidates", f"candidate '{dup}' appears twice"))
    for i, c in enumerate(envelope["data"]["candidates"]):
        proposal = c["proposal"]
        if proposal["kind"] == "amendment" and not proposal.get("target_asset_id"):
            problems.append(Problem("AMENDMENT_WITHOUT_TARGET", f"$.data.candidates[{i}]", f"{c['id']} amends an asset without naming it"))
        if proposal["kind"] != "rex" and not proposal.get("asset_type"):
            problems.append(Problem("ASSET_TYPE", f"$.data.candidates[{i}]", f"{c['id']}: 'asset_type' is required (except for kind 'rex')"))
    return problems


def seal(candidates: list[dict[str, Any]], source_system: str, snapshot_id: str, created_at: str) -> dict[str, Any]:
    """The envelope of a snapshot of proposals (what a suite application publishes; the Hub also uses it for its tests and example)."""
    data = {"candidates": candidates}
    return {"schemaVersion": "1.0", "snapshotId": snapshot_id, "sourceSystem": source_system, "createdAt": created_at,
            "checksum": canonical.sha256(data), "data": data}


def payloads(envelope: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """``(ref, candidate payload)`` for each proposal, with the provenance of the channel."""
    out = []
    for c in envelope["data"]["candidates"]:
        p = c["proposal"]
        payload = {
            "kind": p["kind"], "asset_type": p.get("asset_type"), "title": p["title"], "rationale": p.get("rationale") or "",
            "proposed_content": p["proposed_content"], "target_asset_id": p.get("target_asset_id"), "domain": p.get("domain") or [],
            "source": {"system": envelope["sourceSystem"], "snapshot_id": envelope["snapshotId"],
                       "snapshot_checksum": envelope["checksum"], "candidate_ref": c["id"],
                       # a proposal extracted by a model stays "llm-derived" unless the emitter says otherwise
                       "production_mode": p.get("production_mode") or "llm-derived"},
        }
        out.append((c["id"], payload))
    return out


def import_snapshot(service: Any, envelope: Any, actor: str, dry_run: bool = False,
                    existing: Callable[[], list[dict[str, Any]]] | None = None) -> dict[str, Any]:
    """Read a sealed snapshot of proposals into candidates. Refused whole when it does not verify; idempotent by candidate."""
    problems = verify(envelope)
    if problems:
        raise ProposalSnapshotError(problems)
    known = {(c.get("source") or {}).get("candidate_ref"): c for c in (existing() if existing else service.find())
             if (c.get("source") or {}).get("snapshot_id") == envelope["snapshotId"]}
    imported: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []
    for ref, payload in payloads(envelope):
        if ref in known:
            skipped.append({"candidate_ref": ref, "id": known[ref]["id"], "status": known[ref]["status"]})
            continue
        try:
            if dry_run:
                result = service.dry_run(payload, actor=actor)
                imported.append({"candidate_ref": ref, "would_be_status": result["would_be_status"], "checks": result["checks"]})
            else:
                created = service.submit(payload, actor=actor)
                imported.append({"candidate_ref": ref, "id": created["id"], "status": created["status"]})
        except CandidateError as exc:
            refused.append({"candidate_ref": ref, "argument": exc.argument, "reason": exc.reason})
    return {"snapshot": {"snapshotId": envelope["snapshotId"], "sourceSystem": envelope["sourceSystem"], "checksum": envelope["checksum"]},
            "dry_run": dry_run, "imported": imported, "skipped": skipped, "refused": refused}
