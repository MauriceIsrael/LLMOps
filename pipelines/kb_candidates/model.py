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
SOURCE_SYSTEMS = ("archinex", "document-studio", "architecture-studio", "requirements-intake", "hub-engagement", "mcp", "cli-ingestion", "kb-extraction")
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


METADATA_TARGET_PREFIXES = ("compliance_status:", "portability:")
TYPED_ASSET_PREFIXES = ("principle", "pattern", "decision", "control", "glossary", "trigger", "fact_key")
DOMAIN_ALIASES = {
    "general": "architecture",
}


def _normalize_target_asset_id(raw_target: Any) -> str | None:
    if not isinstance(raw_target, str) or not raw_target.strip():
        return None
    target = raw_target.strip()
    lower = target.lower()
    if any(lower.startswith(prefix) for prefix in METADATA_TARGET_PREFIXES):
        raise CandidateError(
            "target_asset_id",
            f"'{target}' is decision metadata, not a valid KB asset identifier.",
        )
    if ":" in target:
        prefix, rest = target.split(":", 1)
        if prefix.strip().lower() in TYPED_ASSET_PREFIXES and rest.strip():
            return rest.strip()
    return target


def _infer_asset_type(kind: str, target_asset_id: str | None) -> str | None:
    if kind == "new_asset":
        return "pattern"
    if kind == "amendment" and target_asset_id:
        upper = target_asset_id.upper()
        if upper.startswith("P-"):
            return "principle"
        if upper.startswith("PAT-"):
            return "pattern"
        if upper.startswith("ADR-"):
            return "decision"
        if upper.startswith("TRG-"):
            return "trigger"
        return "control"
    return None


def _synthesize_proposed_content(payload: dict[str, Any]) -> str | None:
    summary = str(payload.get("summary") or "").strip()
    suggested = str(payload.get("suggested_change") or "").strip()
    rationale = str(payload.get("rationale") or "").strip()
    if not summary and not suggested:
        return None
    parts = [p for p in (summary, suggested, rationale) if p]
    return "\n\n".join(parts)


def validate_submission(payload: Any) -> dict[str, Any]:
    """Validate a submission and return the normalized candidate fields (no id/status yet)."""
    if not isinstance(payload, dict):
        raise CandidateError("body", "The candidate must be a JSON object.")
    kind = payload.get("kind")
    if kind not in KINDS:
        raise CandidateError("kind", f"'kind' must be one of {list(KINDS)}.")

    has_structured_fields = any(
        isinstance(payload.get(k), str) and payload.get(k).strip()
        for k in ("summary", "suggested_change", "target_asset_ref")
    )
    raw_target = payload.get("target_asset_id")
    if not isinstance(raw_target, str) or not raw_target.strip():
        raw_target = payload.get("target_asset_ref")
    target = _normalize_target_asset_id(raw_target)

    asset_type = payload.get("asset_type")
    if asset_type is None and ("asset_type" not in payload or has_structured_fields):
        if has_structured_fields:
            asset_type = _infer_asset_type(kind, target)
    if asset_type is not None and asset_type not in ASSET_TYPES:
        raise CandidateError("asset_type", f"'asset_type' must be one of {list(ASSET_TYPES)}.")
    if asset_type is None and kind != "rex":
        raise CandidateError("asset_type", "'asset_type' is required (except for kind 'rex').")

    if not isinstance(payload.get("title"), str) or not payload["title"].strip():
        raise CandidateError("title", "'title' is required.")

    proposed_content = payload.get("proposed_content")
    if not isinstance(proposed_content, str) or not proposed_content.strip():
        proposed_content = _synthesize_proposed_content(payload)
    if not isinstance(proposed_content, str) or not proposed_content.strip():
        raise CandidateError("proposed_content", "'proposed_content' is required.")

    if kind == "amendment" and (not isinstance(target, str) or not target.strip()):
        raise CandidateError("target_asset_id", "'target_asset_id' is required for an amendment.")

    source = payload.get("source") or {}
    if not isinstance(source, dict):
        raise CandidateError("source", "'source' must be an object.")
    system = source.get("system")
    if system not in SOURCE_SYSTEMS:
        raise CandidateError("source.system", f"'source.system' must be one of {list(SOURCE_SYSTEMS)}.")
    mode = source.get("production_mode") or payload.get("production_mode") or "human-authored"
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
        if v in (None, "") and name in ("author", "contact"):
            v = payload.get(name)
        return str(v).strip() if v not in (None, "") else None

    engagement = opt("engagement")
    if not clean_evidence and engagement and has_structured_fields:
        clean_evidence = [{"kind": "engagement", "ref": engagement}]

    raw_domains = _str_list(payload.get("domain"), "domain")
    normalized_domains = [DOMAIN_ALIASES.get(d.lower(), d) for d in raw_domains]

    return {
        "kind": kind,
        "target_asset_id": target.strip() if isinstance(target, str) and target.strip() else None,
        "asset_type": asset_type,
        "domain": normalized_domains,
        "title": payload["title"].strip(),
        "rationale": str(payload.get("rationale") or "").strip(),
        "proposed_content": proposed_content.strip() + "\n",
        "source": {
            "system": system,
            "engagement": engagement,
            "decision_id": opt("decision_id"),
            "author": opt("author"),
            "contact": opt("contact"),
            "production_mode": mode,
            # K7: where a proposal published by a suite application comes from (sealed snapshot, candidate inside it)
            **{k: v for k in ("snapshot_id", "snapshot_checksum", "candidate_ref") if (v := opt(k)) is not None},
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
