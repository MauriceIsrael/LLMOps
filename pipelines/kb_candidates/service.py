"""KB candidate cycle: submission -> automatic checks -> human review -> promotion -> publication.

Nothing becomes doctrine without a human: an accepted candidate is written into
``data/kb/`` by ``kb promote`` (run by a maintainer) and published by ``kb publish``
(re-ingestion, sealed snapshot, changelog, consumer notification). The git commit of
the knowledge base stays a maintainer's action.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from pipelines.kb_candidates.checks import build_context, has_failure, run_checks
from pipelines.kb_candidates.confidence import compute_confidence
from pipelines.kb_candidates.kb import (
    asset_path,
    join_frontmatter,
    load_assets,
    split_frontmatter,
)
from pipelines.kb_candidates.model import (
    ASSET_TYPES,
    REVIEW_ACTIONS,
    CandidateError,
    add_history,
    new_candidate,
    now_iso,
    validate_submission,
)
from pipelines.kb_candidates.owners import OwnersRegistry, load_owners
from pipelines.kb_candidates.repository import CandidateRepository, get_repository

REVIEW_SCOPE = "kb:review"
REMINDER_BUSINESS_DAYS = 5
REDACTED = "[redacted: the anonymization check failed — visible to reviewers only]"

NotifyOwner = Callable[[dict[str, Any], str, dict[str, Any]], list[str]]
NotifyConsumers = Callable[[str, dict[str, Any]], list[str]]


class CandidateStateError(CandidateError):
    """The requested transition is not allowed in the candidate's current status."""


def _default_notify_owner(owner: dict[str, Any], event: str, candidate: dict[str, Any]) -> list[str]:
    from mcp_server.core.notifier import notify_owner

    return notify_owner(owner, event, candidate)


def _default_notify_consumers(event: str, payload: dict[str, Any]) -> list[str]:
    from mcp_server.core.notifier import notify_consumers

    return notify_consumers(event, payload)


def business_days_between(start: datetime, end: datetime) -> int:
    """Number of full business days (Mon-Fri) elapsed between two instants."""
    if end <= start:
        return 0
    days = 0
    cursor = start
    while cursor + timedelta(days=1) <= end:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5:
            days += 1
    return days


def _parse_at(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)


def redact(candidate: dict[str, Any]) -> dict[str, Any]:
    """Hide the content of a candidate that failed anonymization (for non-reviewers)."""
    if any(c.get("name") == "anonymization" and c.get("status") == "fail" for c in candidate.get("checks") or []):
        candidate = {**candidate, "proposed_content": REDACTED, "rationale": REDACTED}
    return candidate


class CandidateService:
    def __init__(
        self,
        repository: CandidateRepository | None = None,
        kb_dir: str | Path = "data/kb",
        doctrine_index_loader: Callable[[], Any] | None = None,
        notify_owner: NotifyOwner | None = None,
        notify_consumers: NotifyConsumers | None = None,
    ) -> None:
        self.repo = repository or get_repository()
        self.kb_dir = Path(kb_dir)
        self.doctrine_index_loader = doctrine_index_loader
        self.notify_owner = notify_owner or _default_notify_owner
        self.notify_consumers = notify_consumers or _default_notify_consumers

    # ------------------------------------------------------------------ queries

    def get(self, candidate_id: str) -> dict[str, Any]:
        return self.repo.get(candidate_id)

    def find(self, **filters: str | None) -> list[dict[str, Any]]:
        return self.repo.find(**filters)

    def owners(self) -> OwnersRegistry:
        return load_owners(self.kb_dir)

    # --------------------------------------------------------------- submission

    def _check(self, candidate: dict[str, Any]) -> None:
        ctx = build_context(self.kb_dir, self.repo.find(status="rejected"), self.doctrine_index_loader)
        candidate["checks"] = run_checks(candidate, ctx)
        fm, _ = split_frontmatter(candidate.get("proposed_content", ""))
        target = next((a for a in ctx.assets if a.id == candidate.get("target_asset_id")), None)
        candidate["second_review_required"] = bool(
            candidate.get("asset_type") == "principle"
            or (target is not None and target.type == "principle")
            or (fm or {}).get("supersedes")
        )

    def _route(self, candidate: dict[str, Any], actor: str) -> None:
        """Move a checked candidate to ``checks_failed`` or ``in_review`` (owner notified)."""
        if has_failure(candidate["checks"]):
            candidate["status"] = "checks_failed"
            failed = [c["name"] for c in candidate["checks"] if c["status"] == "fail"]
            add_history(candidate, actor, "checks_failed", checks=failed)
            return
        candidate["status"] = "in_review"
        owner = self.owners().owner_for_domains(candidate.get("domain") or [])
        candidate["assigned_owner"] = owner.handle
        add_history(candidate, actor, "in_review", owner=owner.handle)
        channels = self.notify_owner(owner.as_dict(), "in_review", candidate)
        add_history(candidate, "system", "owner_notified", owner=owner.handle, channels=channels)

    def submit(self, payload: Any, actor: str = "anonymous") -> dict[str, Any]:
        fields = validate_submission(payload)
        fm, _ = split_frontmatter(fields["proposed_content"])
        if fields["asset_type"] is None and fm and fm.get("type") in ASSET_TYPES:
            fields["asset_type"] = fm["type"]
        if not fields["domain"] and fm and fm.get("domain"):
            dom = fm["domain"]
            fields["domain"] = [str(d) for d in (dom if isinstance(dom, list) else [dom])]
        candidate = new_candidate(self.repo.next_id(), fields, actor)
        self._check(candidate)
        self._route(candidate, actor)
        self.repo.save(candidate)
        return candidate

    # ------------------------------------------------------------------- review

    def review(
        self,
        candidate_id: str,
        action: str,
        reviewer: str,
        reason: str | None = None,
        amended_content: str | None = None,
        actor: str = "reviewer",
    ) -> dict[str, Any]:
        candidate = self.repo.get(candidate_id)
        if action not in REVIEW_ACTIONS:
            raise CandidateError("action", f"'action' must be one of {list(REVIEW_ACTIONS)}.")
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise CandidateError("reviewer", "'reviewer' is required.")
        reviewer = reviewer.strip()
        registry = self.owners()
        if reviewer not in registry.owners:
            raise CandidateError("reviewer", f"'{reviewer}' is not an owner declared in data/kb/owners.yaml.")
        reason = (reason or "").strip() or None
        status = candidate["status"]
        allowed = {"in_review": REVIEW_ACTIONS, "checks_failed": ("amend", "reject")}
        if action not in allowed.get(status, ()):
            raise CandidateStateError("action", f"cannot '{action}' a candidate in status '{status}'.")
        if action in ("reject", "amend") and not reason:
            raise CandidateError("reason", f"a reason is required to {action}.")

        entry = {"reviewer": reviewer, "action": action, "reason": reason, "at": now_iso()}
        if action == "reject":
            if candidate.get("review") and candidate["review"].get("action") != "reject":
                candidate["second_review"] = entry
            else:
                candidate["review"] = entry
            candidate["status"] = "rejected"
            add_history(candidate, actor, "rejected", reviewer=reviewer, reason=reason)
            self.repo.save(candidate)
            return candidate

        if action == "amend":
            if not isinstance(amended_content, str) or not amended_content.strip():
                raise CandidateError("amended_content", "'amended_content' is required to amend.")
            candidate["proposed_content"] = amended_content.strip() + "\n"
            fm, _ = split_frontmatter(candidate["proposed_content"])
            if candidate.get("asset_type") is None and fm and fm.get("type") in ASSET_TYPES:
                candidate["asset_type"] = fm["type"]
            if fm and fm.get("domain") and not candidate.get("domain"):
                dom = fm["domain"]
                candidate["domain"] = [str(d) for d in (dom if isinstance(dom, list) else [dom])]
            add_history(candidate, actor, "amended", reviewer=reviewer, reason=reason)
            self._check(candidate)
            if has_failure(candidate["checks"]):
                candidate["status"] = "checks_failed"
                add_history(candidate, "system", "checks_failed",
                            checks=[c["name"] for c in candidate["checks"] if c["status"] == "fail"])
                self.repo.save(candidate)
                return candidate
            if candidate.get("asset_type") is None or next(
                (c for c in candidate["checks"] if c["name"] == "schema" and c["status"] != "pass"
                 and "free-form" in c["detail"]), None
            ):
                raise CandidateError("amended_content", "the amended content must be a complete asset (front matter).")
            if status == "checks_failed" and not candidate.get("assigned_owner"):
                owner = registry.owner_for_domains(candidate.get("domain") or [])
                candidate["assigned_owner"] = owner.handle
            # An amendment by the reviewer is an acceptance of the amended content.

        # accept (or amend = accept with modified content)
        if has_failure(candidate["checks"]):
            raise CandidateStateError("action", "cannot accept a candidate with failed checks.")
        conflict = next((c for c in candidate["checks"] if c["name"] == "doctrine_conflict" and c["status"] == "warn"
                         and c["detail"].startswith("violates")), None)
        fm, _ = split_frontmatter(candidate.get("proposed_content", ""))
        if conflict and not reason and not (fm or {}).get("supersedes"):
            raise CandidateError(
                "reason",
                "the content conflicts with the doctrine: accept with 'supersedes' in the content or a motivated exception as 'reason'.",
            )

        first = candidate.get("review")
        if candidate.get("second_review_required") and not (first and first.get("action") in ("accept", "amend")):
            candidate["review"] = entry
            candidate["status"] = "in_review"
            add_history(candidate, actor, "first_review_accepted", reviewer=reviewer)
            # The second reviewer defaults to the default owner (maintainers), or any other owner.
            others = [h for h in sorted(registry.owners) if h != reviewer]
            second_handle = registry.default_owner if registry.default_owner in others else (others[0] if others else None)
            second = registry.owner(second_handle) if second_handle else None
            if second is not None:
                channels = self.notify_owner(second.as_dict(), "second_review", candidate)
                add_history(candidate, "system", "second_review_requested", owner=second.handle, channels=channels)
            self.repo.save(candidate)
            return candidate
        if candidate.get("second_review_required"):
            if first and first.get("reviewer") == reviewer:
                raise CandidateError("reviewer", "the second review must be done by another owner.")
            candidate["second_review"] = entry
        else:
            candidate["review"] = entry
        if (candidate.get("source") or {}).get("production_mode") == "llm-derived":
            candidate["source"]["production_mode"] = "llm-proposed-human-approved"
            add_history(candidate, actor, "llm_content_reviewed", reviewer=reviewer)
        candidate["status"] = "accepted"
        add_history(candidate, actor, "accepted", reviewer=reviewer, reason=reason)
        self.repo.save(candidate)
        return candidate

    # ---------------------------------------------------------------- promotion

    def promote(self, candidate_id: str, actor: str = "maintainer", today: date | None = None) -> dict[str, Any]:
        """Write an accepted candidate into the KB (``status: active``, computed confidence)."""
        candidate = self.repo.get(candidate_id)
        if candidate["status"] != "accepted":
            raise CandidateStateError("status", f"only an accepted candidate can be promoted (status '{candidate['status']}').")
        if any(h.get("event") == "promoted" for h in candidate.get("history") or []):
            raise CandidateStateError("status", "the candidate is already promoted; run 'kb publish'.")
        confidence = compute_confidence(candidate.get("evidence"), (candidate.get("source") or {}).get("production_mode"))
        today = today or datetime.now(UTC).date()
        reviewers = [r["reviewer"] for r in (candidate.get("review"), candidate.get("second_review")) if r]

        if candidate.get("asset_type") == "glossary":
            path = self._promote_glossary(candidate)
            asset_id = f"glossary:{candidate['title']}"
        else:
            fm, body = split_frontmatter(candidate["proposed_content"])
            if fm is None:
                raise CandidateError("proposed_content", "the candidate has no front matter: amend it first.")
            asset_id = str(fm["id"])
            fm["status"] = "active"
            fm["confidence"] = confidence
            fm["last_reviewed"] = today
            fm["owner"] = fm.get("owner") or str(candidate.get("assigned_owner") or "maintainers").lstrip("@")
            fm["validated_by"] = reviewers
            fm["validated_at"] = now_iso()
            if fm.get("checks"):
                fm["checks_status"] = "validated"
            if candidate.get("target_asset_id"):
                target = next((a for a in load_assets(self.kb_dir) if a.id == candidate["target_asset_id"]), None)
                if target is None:
                    raise CandidateError("target_asset_id", f"target asset '{candidate['target_asset_id']}' not found.")
                path = target.path
            else:
                path = asset_path(self.kb_dir, candidate["asset_type"], asset_id, fm.get("framework"))
                if path.exists():
                    raise CandidateStateError("proposed_content", f"{path} already exists.")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(join_frontmatter(fm, body), encoding="utf-8")

        add_history(candidate, actor, "promoted", path=str(path), asset=asset_id, confidence=confidence)
        candidate["promoted"] = {"path": str(path), "asset_id": asset_id, "confidence": confidence}
        self.repo.save(candidate)
        return candidate

    def _promote_glossary(self, candidate: dict[str, Any]) -> Path:
        path = self.kb_dir / "glossary" / "glossary.md"
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        entries = candidate["proposed_content"].strip()
        for match in re.finditer(r"^\*\*(.+?)\*\*", entries, re.MULTILINE):
            term = match.group(1).strip()
            existing = re.compile(rf"^\*\*{re.escape(term)}\*\*.*?(?=\n\n|\Z)", re.DOTALL | re.MULTILINE)
            if existing.search(text) and candidate["kind"] != "amendment":
                raise CandidateStateError("proposed_content", f"glossary term '{term}' already exists: submit an amendment.")
            text = existing.sub("", text).rstrip() + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.rstrip() + "\n\n" + entries + "\n", encoding="utf-8")
        return path

    # -------------------------------------------------------------- publication

    def publish(
        self,
        ingest: Callable[[], None],
        snapshot: Callable[[], dict[str, Any]],
        actor: str = "maintainer",
        changelog: Path | None = None,
    ) -> dict[str, Any]:
        """Re-ingest the KB, export a sealed snapshot, log the changelog, notify consumers."""
        promoted = [c for c in self.repo.find(status="accepted") if c.get("promoted")]
        if not promoted:
            return {"published": [], "snapshot_id": None, "message": "nothing to publish (no promoted candidate)"}
        ingest()
        envelope = snapshot()
        snapshot_id = envelope.get("snapshot_id")
        self._write_changelog(changelog or self.kb_dir / "CHANGELOG.md", snapshot_id, promoted)
        payload = {
            "snapshot_id": snapshot_id,
            "payload_sha256": envelope.get("payload_sha256"),
            "candidates": [c["id"] for c in promoted],
            "assets": [c["promoted"]["asset_id"] for c in promoted],
        }
        channels = self.notify_consumers("kb_published", payload)
        for c in promoted:
            c["status"] = "published"
            c["published"] = {"snapshot_id": snapshot_id, "at": now_iso()}
            add_history(c, actor, "published", snapshot_id=snapshot_id, channels=channels)
            self.repo.save(c)
        return {"published": [c["id"] for c in promoted], "snapshot_id": snapshot_id, "channels": channels}

    @staticmethod
    def _write_changelog(path: Path, snapshot_id: str | None, candidates: list[dict[str, Any]]) -> None:
        header = "# Knowledge base changelog\n\nPublished changes, newest first (written by `kb publish`).\n"
        existing = path.read_text(encoding="utf-8") if path.exists() else header
        if not existing.startswith("# "):
            existing = header + "\n" + existing
        head, _, rest = existing.partition("\n## ")
        lines = [f"## {datetime.now(UTC).date().isoformat()} — {snapshot_id or 'unsealed'}", ""]
        for c in candidates:
            reviewers = ", ".join(r["reviewer"] for r in (c.get("review"), c.get("second_review")) if r)
            lines.append(
                f"- `{c['promoted']['asset_id']}` ({c['kind']}, confidence `{c['promoted']['confidence']}`): "
                f"{c['title']} — {c['id']}, reviewed by {reviewers or 'n/a'}"
            )
        entry = "\n".join(lines) + "\n"
        body = head.rstrip() + "\n\n" + entry + ("\n## " + rest if rest else "")
        path.write_text(body, encoding="utf-8")

    # ---------------------------------------------------------------- reminders

    def remind(self, now: datetime | None = None, actor: str = "system",
               business_days: int = REMINDER_BUSINESS_DAYS) -> list[dict[str, Any]]:
        """Re-notify owners of candidates waiting in review for more than ``business_days``."""
        now = now or datetime.now(UTC)
        reminded = []
        registry = self.owners()
        for c in self.repo.find(status="in_review"):
            history = c.get("history") or []
            entered = next((h["at"] for h in reversed(history) if h.get("event") in ("in_review", "first_review_accepted")), None)
            if entered is None or business_days_between(_parse_at(entered), now) < business_days:
                continue
            last = next((h.get("reminded_at", h["at"]) for h in reversed(history) if h.get("event") == "reminded"), None)
            if last is not None and business_days_between(_parse_at(last), now) < 1:
                continue
            owner = registry.owner(c.get("assigned_owner") or registry.default_owner)
            channels = self.notify_owner(owner.as_dict(), "reminder", c)
            add_history(c, actor, "reminded", owner=owner.handle, channels=channels,
                        reminded_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"))
            self.repo.save(c)
            reminded.append(c)
        return reminded


def rex_payload(
    title: str,
    rationale: str,
    suggested_change: str,
    author: str | None,
    contact: str | None,
    source_engagement: str | None,
    system: str,
) -> dict[str, Any]:
    """Candidate payload (kind ``rex``) for a knowledge improvement suggestion."""
    fm, _ = split_frontmatter(suggested_change)
    return {
        "kind": "rex",
        "asset_type": fm.get("type") if fm and fm.get("type") in ASSET_TYPES else None,
        "domain": fm.get("domain") if fm and isinstance(fm.get("domain"), list) else [],
        "title": title,
        "rationale": rationale,
        "proposed_content": suggested_change,
        "source": {
            "system": system,
            "engagement": source_engagement,
            "author": author,
            "contact": contact,
            "production_mode": "human-authored",
        },
        "evidence": [{"kind": "engagement", "ref": source_engagement}] if source_engagement else [],
    }


__all__ = [
    "REVIEW_SCOPE",
    "CandidateService",
    "CandidateStateError",
    "business_days_between",
    "redact",
    "rex_payload",
]
