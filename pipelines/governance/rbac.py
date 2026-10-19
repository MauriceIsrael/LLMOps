"""Fine-grained Role-Based Access Control (RBAC) and delegation for KB governance (issue #7).

Features:
- Domain-scoped roles (e.g. ``kb:review`` on ``security/*``, ``kb:evaluate`` on ``resilience/*``).
- Temporary delegation of domain ownership and review duties.
- Strict separation of duties preventing candidate authors from reviewing their own contributions.
- Immediate revocation support.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from pipelines.governance.store import database_url, get_engine, kb_delegations
from pipelines.kb_candidates.model import now_iso
from pipelines.kb_candidates.service import CandidateForbiddenError


def domain_matches(pattern: str, domain: str) -> bool:
    """Check if a domain matches a pattern (hierarchical wildcard or prefix)."""
    pat = pattern.strip().lower()
    dom = domain.strip().lower()
    if pat in ("*", ""):
        return True
    if pat == dom:
        return True
    if pat.endswith("/*"):
        prefix = pat[:-2]
        return dom == prefix or dom.startswith(prefix + "/")
    # Exact parent prefix match (e.g. "architecture" covers "architecture/resilience")
    if dom.startswith(pat + "/"):
        return True
    return False


def _is_active(starts_at: str, expires_at: str, revoked_at: str | None = None) -> bool:
    if revoked_at:
        return False
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if starts_at and starts_at > now:
        return False
    if expires_at and expires_at < now:
        return False
    return True


class DelegationStore:
    """Persistence and evaluation of temporary domain delegations."""

    def __init__(self) -> None:
        self._memory_delegations: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def clear(self) -> None:
        with self._lock:
            self._memory_delegations.clear()
        if database_url():
            try:
                engine = get_engine()
                with engine.begin() as conn:
                    conn.execute(kb_delegations.delete())
            except Exception:
                pass

    def create_delegation(
        self,
        delegator: str,
        delegate: str,
        domains: list[str],
        roles: list[str],
        expires_at: str,
        starts_at: str | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        """Create a new temporary delegation."""
        delegation_id = str(uuid.uuid4())
        at = now_iso()
        record: dict[str, Any] = {
            "id": delegation_id,
            "delegator": delegator.strip(),
            "delegate": delegate.strip(),
            "domains": [d.strip() for d in domains if d.strip()],
            "roles": [r.strip() for r in roles if r.strip()],
            "starts_at": (starts_at or at).strip(),
            "expires_at": expires_at.strip(),
            "created_at": at,
            "created_by": (created_by or delegator).strip(),
            "revoked_at": None,
            "revoked_by": None,
        }

        with self._lock:
            self._memory_delegations[delegation_id] = dict(record)

        if database_url():
            try:
                engine = get_engine()
                with engine.begin() as conn:
                    conn.execute(
                        kb_delegations.insert().values(
                            id=record["id"],
                            delegator=record["delegator"],
                            delegate=record["delegate"],
                            domains=json.dumps(record["domains"]),
                            roles=json.dumps(record["roles"]),
                            starts_at=record["starts_at"],
                            expires_at=record["expires_at"],
                            created_at=record["created_at"],
                            created_by=record["created_by"],
                            revoked_at=None,
                            revoked_by=None,
                        )
                    )
            except Exception:
                pass

        return record

    def revoke_delegation(self, delegation_id: str, revoked_by: str | None = None) -> bool:
        """Revoke an active delegation immediately."""
        at = now_iso()
        found = False
        with self._lock:
            if delegation_id in self._memory_delegations:
                rec = self._memory_delegations[delegation_id]
                rec["revoked_at"] = at
                rec["revoked_by"] = revoked_by or "admin"
                found = True

        if database_url():
            try:
                engine = get_engine()
                with engine.begin() as conn:
                    res = conn.execute(
                        kb_delegations.update()
                        .where(kb_delegations.c.id == delegation_id)
                        .values(revoked_at=at, revoked_by=revoked_by or "admin")
                    )
                    if res.rowcount > 0:
                        found = True
            except Exception:
                pass

        return found

    def list_delegations(
        self,
        delegate: str | None = None,
        delegator: str | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        """List delegations filtered by delegate, delegator, and active status."""
        records: list[dict[str, Any]] = []

        if database_url():
            try:
                engine = get_engine()
                with engine.connect() as conn:
                    query = select(kb_delegations)
                    if delegate:
                        query = query.where(kb_delegations.c.delegate == delegate.strip())
                    if delegator:
                        query = query.where(kb_delegations.c.delegator == delegator.strip())
                    rows = conn.execute(query).all()
                    for r in rows:
                        records.append({
                            "id": r.id,
                            "delegator": r.delegator,
                            "delegate": r.delegate,
                            "domains": json.loads(r.domains or "[]"),
                            "roles": json.loads(r.roles or "[]"),
                            "starts_at": r.starts_at,
                            "expires_at": r.expires_at,
                            "created_at": r.created_at,
                            "created_by": r.created_by,
                            "revoked_at": r.revoked_at,
                            "revoked_by": r.revoked_by,
                        })
            except Exception:
                records = []

        if not records:
            with self._lock:
                for r in self._memory_delegations.values():
                    if delegate and r["delegate"] != delegate.strip():
                        continue
                    if delegator and r["delegator"] != delegator.strip():
                        continue
                    records.append(dict(r))

        if active_only:
            records = [r for r in records if _is_active(r["starts_at"], r["expires_at"], r.get("revoked_at"))]

        return sorted(records, key=lambda x: x["created_at"], reverse=True)

    def is_delegated(self, delegate_handle: str, domain: str, role: str) -> bool:
        """Whether ``delegate_handle`` holds an active delegation covering ``domain`` and ``role``."""
        delegations = self.list_delegations(delegate=delegate_handle, active_only=True)
        for d in delegations:
            role_match = not d["roles"] or "*" in d["roles"] or role in d["roles"]
            if not role_match:
                continue
            for pattern in d["domains"]:
                if domain_matches(pattern, domain):
                    return True
        return False

    def delegators_for(self, delegate_handle: str, domain: str, role: str) -> list[str]:
        """List delegators who granted ``role`` on ``domain`` to ``delegate_handle``."""
        delegations = self.list_delegations(delegate=delegate_handle, active_only=True)
        delegators: list[str] = []
        for d in delegations:
            role_match = not d["roles"] or "*" in d["roles"] or role in d["roles"]
            if not role_match:
                continue
            for pattern in d["domains"]:
                if domain_matches(pattern, domain):
                    delegators.append(d["delegator"])
                    break
        return delegators


_delegation_store = DelegationStore()


def get_delegation_store() -> DelegationStore:
    return _delegation_store


def extract_candidate_author(candidate: dict[str, Any]) -> str | None:
    """Identify the author handle or email of a candidate from history or metadata."""
    # 1. From candidate submission event in history
    history = candidate.get("history") or []
    for h in history:
        if h.get("event") == "submitted" and h.get("actor"):
            actor = str(h["actor"]).strip()
            if actor and actor not in ("system", "anonymous"):
                return actor

    # 2. From candidate source
    source = candidate.get("source") or {}
    source_author = source.get("author") or source.get("actor")
    if source_author and str(source_author).strip() not in ("system", "anonymous"):
        return str(source_author).strip()

    # 3. Direct top-level fields
    for field in ("created_by", "author"):
        val = candidate.get(field)
        if val and str(val).strip() not in ("system", "anonymous"):
            return str(val).strip()

    return None


def check_separation_of_duties(
    reviewer_handle: str,
    candidate: dict[str, Any],
    reviewer_email: str | None = None,
) -> None:
    """Enforce separation of duties: the author of a candidate cannot review it.

    Raises ``CandidateForbiddenError`` (403) when self-review is attempted.
    """
    author = extract_candidate_author(candidate)
    rev_h = (reviewer_handle or "").strip().lower()
    rev_e = (reviewer_email or "").strip().lower()

    # Check candidate or source author email if present
    author_email = (
        candidate.get("author_email")
        or (candidate.get("source") or {}).get("author_email")
        or (candidate.get("source") or {}).get("email")
    )
    if author_email and rev_e and str(author_email).strip().lower() == rev_e:
        raise CandidateForbiddenError(
            "reviewer",
            "separation_of_duties: the author of a candidate cannot review it (author e-mail match).",
        )

    if not author:
        return

    auth = author.strip().lower()

    # Matches handle or email
    if auth.startswith("email:"):
        auth_email = auth[6:].strip()
        if rev_e and rev_e == auth_email:
            raise CandidateForbiddenError(
                "reviewer",
                "separation_of_duties: the author of a candidate cannot review it (author e-mail match).",
            )
    elif "@" in auth and not auth.startswith("@"):
        if rev_e and rev_e == auth:
            raise CandidateForbiddenError(
                "reviewer",
                "separation_of_duties: the author of a candidate cannot review it (author e-mail match).",
            )
    else:
        if rev_h and rev_h == auth:
            raise CandidateForbiddenError(
                "reviewer",
                "separation_of_duties: the author of a candidate cannot review it (author handle match).",
            )


def expert_can_review_domain(
    handle: str,
    domains: list[str],
    registry: Any,
    domain_roles: dict[str, list[str]] | None = None,
    delegation_store: DelegationStore | None = None,
) -> bool:
    """Evaluate whether an expert has permission to review a candidate in given domains.

    Considers:
    - Default owner / Maintainer role (global bypass).
    - Registered domain ownership (owners registry).
    - Explicit domain-scoped roles (e.g. from token assertion claims).
    - Active temporary delegations.
    """
    owner = registry.owners.get(handle)
    if owner and (handle == registry.default_owner or "kb:maintain" in owner.roles):
        return True

    # Standard registry ownership
    if registry.can_review(handle, domains):
        return True

    # Explicit domain roles passed in assertion
    if domain_roles:
        for dom in domains:
            for pat, roles in domain_roles.items():
                if ("kb:review" in roles or "*" in roles) and domain_matches(pat, dom):
                    return True

    # Temporary delegations
    store = delegation_store or get_delegation_store()
    for dom in domains:
        if store.is_delegated(handle, dom, "kb:review"):
            return True

    return False

