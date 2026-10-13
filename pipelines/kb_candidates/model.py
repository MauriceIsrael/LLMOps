"""KB candidate model (``schemas/kb_candidate.schema.json``).

A candidate is a proposed change to the knowledge base (new asset, amendment,
return of experience, framework ingestion). It goes through automatic checks, human
review, promotion into ``data/kb/`` and publication; nothing reaches the doctrine
without that cycle.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

KINDS = ("new_asset", "amendment", "rex", "framework_ingestion")
ASSET_TYPES = ("principle", "pattern", "decision", "control", "glossary", "trigger", "fact_key")  # K22: rules and vocabulary keys
SOURCE_SYSTEMS = ("archinex", "document-studio", "mcp", "cli-ingestion", "kb-extraction")
PRODUCTION_MODES = ("human-authored", "llm-proposed-human-approved", "llm-derived")
EVIDENCE_KINDS = ("measure", "audit", "engagement", "vendor-doc")
STATUSES = ("proposed", "checks_failed", "in_review", "accepted", "rejected", "published")
REVIEW_ACTIONS = ("accept", "amend", "reject")
CHECK_STATUSES = ("pass", "fail", "warn")


class CandidateError(ValueError):
    """Invalid candidate input or transition; ``argument`` names the offending field."""

    def __init__(self, argument: str, reason: str) -> None:
        super().__init__(reason)
        self.argument = argument
        self.reason = reason


class CandidateNotFoundError(LookupError):
    def __init__(self, candidate_id: str) -> None:
        super().__init__(candidate_id)
        self.candidate_id = candidate_id


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _str_list(value: Any, argument: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return [v.strip() for v in value if v.strip()]
    raise CandidateError(argument, f"'{argument}' must be a list of strings.")


def validate_submission(payload: Any) -> dict[str, Any]:
    """Validate a submission and return the normalized candidate fields (no id/status yet)."""
    if not isinstance(payload, dict):
        raise CandidateError("body", "The candidate must be a JSON object.")
    kind = payload.get("kind")
    if kind not in KINDS:
        raise CandidateError("kind", f"'kind' must be one of {list(KINDS)}.")
    asset_type = payload.get("asset_type")
    if asset_type is not None and asset_type not in ASSET_TYPES:
        raise CandidateError("asset_type", f"'asset_type' must be one of {list(ASSET_TYPES)}.")
    if asset_type is None and kind != "rex":
        raise CandidateError("asset_type", "'asset_type' is required (except for kind 'rex').")
    for field in ("title", "proposed_content"):
        if not isinstance(payload.get(field), str) or not payload[field].strip():
            raise CandidateError(field, f"'{field}' is required.")
    target = payload.get("target_asset_id")
    if kind == "amendment" and (not isinstance(target, str) or not target.strip()):
        raise CandidateError("target_asset_id", "'target_asset_id' is required for an amendment.")

    source = payload.get("source") or {}
    if not isinstance(source, dict):
        raise CandidateError("source", "'source' must be an object.")
    system = source.get("system")
    if system not in SOURCE_SYSTEMS:
        raise CandidateError("source.system", f"'source.system' must be one of {list(SOURCE_SYSTEMS)}.")
    mode = source.get("production_mode", "human-authored")
    if mode not in PRODUCTION_MODES:
        raise CandidateError("source.production_mode", f"'source.production_mode' must be one of {list(PRODUCTION_MODES)}.")

    evidence = payload.get("evidence") or []
    if not isinstance(evidence, list):
        raise CandidateError("evidence", "'evidence' must be a list.")
    clean_evidence = []
    for ev in evidence:
        if not isinstance(ev, dict) or ev.get("kind") not in EVIDENCE_KINDS or not str(ev.get("ref") or "").strip():
            raise CandidateError("evidence", f"each evidence needs 'kind' in {list(EVIDENCE_KINDS)} and a non-empty 'ref'.")
        clean_evidence.append({"kind": ev["kind"], "ref": str(ev["ref"]).strip()})

    def opt(name: str) -> str | None:
        v = source.get(name)
        return str(v).strip() if v not in (None, "") else None

    return {
        "kind": kind,
        "target_asset_id": target.strip() if isinstance(target, str) and target.strip() else None,
        "asset_type": asset_type,
        "domain": _str_list(payload.get("domain"), "domain"),
        "title": payload["title"].strip(),
        "rationale": str(payload.get("rationale") or "").strip(),
        "proposed_content": payload["proposed_content"].strip() + "\n",
        "source": {
            "system": system,
            "engagement": opt("engagement"),
            "decision_id": opt("decision_id"),
            "author": opt("author"),
            "contact": opt("contact"),
            "production_mode": mode,
        },
        "evidence": clean_evidence,
    }


def new_candidate(candidate_id: str, fields: dict[str, Any], actor: str) -> dict[str, Any]:
    at = now_iso()
    return {
        "id": candidate_id,
        **fields,
        "status": "proposed",
        "checks": [],
        "review": None,
        "second_review_required": False,
        "second_review": None,
        "assigned_owner": None,
        "history": [{"at": at, "actor": actor, "event": "submitted"}],
        "created_at": at,
        "updated_at": at,
    }


def add_history(candidate: dict[str, Any], actor: str, event: str, **details: Any) -> None:
    entry: dict[str, Any] = {"at": now_iso(), "actor": actor, "event": event}
    entry.update({k: v for k, v in details.items() if v is not None})
    candidate.setdefault("history", []).append(entry)
    candidate["updated_at"] = entry["at"]
