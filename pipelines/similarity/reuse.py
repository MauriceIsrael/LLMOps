"""Confirmation of the reuse of validated knowledge (lot L12): the rules that make a false positive impossible to hide.

A similar subject is only a *proposal*. The reuse is acquired when a person has confirmed, one by one, the
hypotheses under which the earlier decision holds. The server enforces this; the user interface cannot skip it.
Records are append-only and attributed.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy import select

from pipelines.doctrine.text import normalize, normalize_phrase
from pipelines.governance.log import now_iso
from pipelines.governance.store import get_engine, reuse_confirmations
from pipelines.kb_candidates.checks import find_ip_addresses, load_denylist
from pipelines.kb_candidates.kb import KbAsset, load_assets

OUTCOMES = ("reused", "reused_with_exception", "rejected_not_same", "rejected_assumption_fails", "deferred")
REUSE_OUTCOMES = ("reused", "reused_with_exception")
ASSUMPTION_STATUSES = ("holds", "does_not_hold", "unknown")
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


class ReuseError(ValueError):
    """Invalid confirmation (400)."""

    def __init__(self, argument: str, reason: str) -> None:
        super().__init__(reason)
        self.argument, self.reason = argument, reason


class ReuseConflictError(ReuseError):
    """The confirmation contradicts the state of the asset (409)."""


def asset_assumptions(asset: KbAsset) -> list[str]:
    return [str(a).strip() for a in (asset.frontmatter.get("assumptions") or []) if str(a).strip()]


def assumptions_digest(assumptions: list[str]) -> str:
    """Order-insensitive fingerprint of a set of assumptions: a judgement made on other hypotheses is outdated."""
    canon = sorted({" ".join(a.lower().split()) for a in assumptions})
    return hashlib.sha256(json.dumps(canon, ensure_ascii=False).encode("utf-8")).hexdigest()


def _norm(text: str) -> str:
    return " ".join(str(text).lower().split())


def validate_confirmation(body: dict[str, Any], asset: KbAsset | None, kb_dir: str | Path) -> dict[str, Any]:
    """Normalised confirmation, or a ``ReuseError`` / ``ReuseConflictError``."""
    outcome = body.get("outcome")
    if outcome not in OUTCOMES:
        raise ReuseError("outcome", f"'outcome' must be one of {list(OUTCOMES)}.")
    fingerprint = str(body.get("subject_fingerprint") or "")
    if not _FINGERPRINT.match(fingerprint):
        raise ReuseError("subject_fingerprint", "'subject_fingerprint' must be the SHA-256 (64 hex) of the normalised subject.")
    label = str(body.get("subject_label") or "").strip()
    if not label or len(label) > 200:
        raise ReuseError("subject_label", "'subject_label' (short, anonymised) is required, at most 200 characters.")
    if find_ip_addresses(label) or _EMAIL.search(label) or any(
            normalize_phrase(t) and f" {normalize_phrase(t)} " in f" {normalize(label)} " for t in load_denylist(kb_dir)):
        raise ReuseError("subject_label", "'subject_label' must be anonymised: no client name, address or e-mail.")
    comment = str(body.get("comment") or "").strip() or None
    if asset is None:
        raise ReuseError("matched_ref", f"'{body.get('matched_ref')}' is not an asset of the knowledge base.")

    raw = body.get("assumptions") or []
    if not isinstance(raw, list):
        raise ReuseError("assumptions", "'assumptions' must be a list of {text, status, note?}.")
    judged: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict) or item.get("status") not in ASSUMPTION_STATUSES or not str(item.get("text") or "").strip():
            raise ReuseError("assumptions", f"each assumption needs a 'text' and a 'status' in {list(ASSUMPTION_STATUSES)}.")
        judged.append({"text": str(item["text"]).strip(), "status": item["status"],
                       "note": (str(item.get("note")).strip() or None) if item.get("note") else None})

    documented = asset_assumptions(asset)
    needs_assumptions = outcome in (*REUSE_OUTCOMES, "rejected_assumption_fails")
    if needs_assumptions:
        if not documented:
            raise ReuseConflictError(
                "assumptions", f"{asset.id} documents no assumption: a decision cannot be reused until its hypotheses "
                "are written down (submit an amendment with 'assumptions'), otherwise nobody can say whether they hold here.")
        if {_norm(j["text"]) for j in judged} != {_norm(a) for a in documented} or len(judged) != len(documented):
            raise ReuseConflictError(
                "assumptions", f"the judged assumptions are not those of {asset.id} as they stand now: judge each of "
                f"its {len(documented)} assumption(s) exactly (the asset may have changed since the proposal).")
    statuses = [j["status"] for j in judged]
    if outcome == "reused" and any(s != "holds" for s in statuses):
        raise ReuseConflictError("outcome", "'reused' requires every assumption to hold; use 'reused_with_exception' "
                                 "(with a motivated comment), 'rejected_assumption_fails' or 'deferred'.")
    if outcome == "reused_with_exception":
        if all(s == "holds" for s in statuses):
            raise ReuseConflictError("outcome", "every assumption holds: the outcome is 'reused', not an exception.")
        if not comment:
            raise ReuseError("comment", "'reused_with_exception' requires a motivated comment (which assumption, why it is acceptable).")
    if outcome == "rejected_assumption_fails" and "does_not_hold" not in statuses:
        raise ReuseConflictError("outcome", "'rejected_assumption_fails' requires at least one assumption that does not hold.")
    if outcome == "rejected_not_same" and not comment:
        raise ReuseError("comment", "'rejected_not_same' requires a comment: the reason is remembered for the next proposal.")
    if outcome in REUSE_OUTCOMES:
        status = str(asset.frontmatter.get("status") or "")
        if status != "active" or asset.frontmatter.get("superseded_by"):
            raise ReuseConflictError("matched_ref", f"{asset.id} is not an active asset (status '{status}'"
                                     + (f", superseded by {asset.frontmatter['superseded_by']}" if asset.frontmatter.get("superseded_by") else "")
                                     + "): it cannot be reused.")
    scores = body.get("scores") or {}
    return {"subject_fingerprint": fingerprint, "subject_label": label, "matched_ref": asset.id,
            "assumptions_digest": assumptions_digest(documented), "model": str(body.get("model") or "") or None,
            "scores": scores if isinstance(scores, dict) else {}, "assumptions": judged, "outcome": outcome,
            "comment": comment}


class ReuseStore:
    def __init__(self, url: str | None = None) -> None:
        self.engine = get_engine(url)

    def add(self, actor: str, record: dict[str, Any]) -> dict[str, Any]:
        values = {**record, "at": now_iso(), "actor": actor, "scores": json.dumps(record["scores"]),
                  "assumptions": json.dumps(record["assumptions"], ensure_ascii=False)}
        with self.engine.begin() as conn:
            res = conn.execute(reuse_confirmations.insert().values(**values))
            return self.get((res.inserted_primary_key or (0,))[0], conn)

    def get(self, confirmation_id: int, conn: Any = None) -> dict[str, Any]:
        def run(c: Any) -> Any:
            return c.execute(select(reuse_confirmations).where(reuse_confirmations.c.id == confirmation_id)).one()
        if conn is not None:
            row = run(conn)
        else:
            with self.engine.connect() as c:
                row = run(c)
        return _row(row)

    def history(self, matched_ref: str | None = None, outcome: str | None = None,
             subject_fingerprint: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        query = select(reuse_confirmations).order_by(reuse_confirmations.c.id.desc()).limit(min(max(limit, 1), 1000))
        if matched_ref:
            query = query.where(reuse_confirmations.c.matched_ref == matched_ref)
        if outcome:
            query = query.where(reuse_confirmations.c.outcome == outcome)
        if subject_fingerprint:
            query = query.where(reuse_confirmations.c.subject_fingerprint == subject_fingerprint)
        with self.engine.connect() as conn:
            return [_row(r) for r in conn.execute(query).all()]

    def judgements(self, subject_fingerprint: str, assets: dict[str, KbAsset]) -> dict[str, list[dict[str, Any]]]:
        """Previous judgements of this subject, by asset, newest first, each flagged when the asset's assumptions
        have changed since (the old confirmation then no longer stands and must be redone)."""
        out: dict[str, list[dict[str, Any]]] = {}
        for rec in self.history(subject_fingerprint=subject_fingerprint, limit=1000):
            asset = assets.get(rec["matched_ref"])
            changed = asset is not None and assumptions_digest(asset_assumptions(asset)) != rec["assumptions_digest"]
            out.setdefault(rec["matched_ref"], []).append({
                "id": rec["id"], "at": rec["at"], "actor": rec["actor"], "outcome": rec["outcome"],
                "comment": rec["comment"], "assumptions_changed_since": changed})
        return out

    def summary(self) -> dict[str, dict[str, int]]:
        """Outcomes per asset over all subjects: how often a decision was reused or turned down."""
        out: dict[str, dict[str, int]] = {}
        for rec in self.history(limit=1000):
            out.setdefault(rec["matched_ref"], {}).setdefault(rec["outcome"], 0)
            out[rec["matched_ref"]][rec["outcome"]] += 1
        return out


def _row(r: Any) -> dict[str, Any]:
    return {"id": r.id, "at": r.at, "actor": r.actor, "subject_fingerprint": r.subject_fingerprint,
            "subject_label": r.subject_label, "matched_ref": r.matched_ref, "assumptions_digest": r.assumptions_digest,
            "model": r.model, "scores": json.loads(r.scores), "assumptions": json.loads(r.assumptions),
            "outcome": r.outcome, "comment": r.comment}


def find_asset(kb_dir: str | Path, ref: str) -> KbAsset | None:
    return next((a for a in load_assets(kb_dir) if a.id == ref), None)
