"""Access audit log for KB governance operations (issue #7).

Records every expert access decision (allowed or denied), authentication method,
assertion JTI, actor identity, action and targeted resource.
"""

from __future__ import annotations

import json
import threading
from typing import Any

from sqlalchemy import select

from pipelines.governance.store import database_url, get_engine, kb_access_audit
from pipelines.kb_candidates.model import now_iso


class GovernanceAuditStore:
    """Audit logger storing governance access events in memory and database."""

    def __init__(self, max_memory_entries: int = 1000) -> None:
        self.max_memory_entries = max_memory_entries
        self._memory_log: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    def clear(self) -> None:
        with self._lock:
            self._memory_log.clear()
        if database_url():
            try:
                engine = get_engine()
                with engine.begin() as conn:
                    conn.execute(kb_access_audit.delete())
            except Exception:
                pass

    def record(
        self,
        actor: str,
        action: str,
        outcome: str,  # allowed | denied
        resource: str | None = None,
        detail: dict[str, Any] | None = None,
        jti: str | None = None,
        auth_method: str = "header",
    ) -> None:
        """Record an access decision in the audit log."""
        entry: dict[str, Any] = {
            "at": now_iso(),
            "actor": actor or "anonymous",
            "auth_method": auth_method,
            "jti": jti,
            "action": action,
            "resource": resource,
            "outcome": outcome,
            "detail": detail or {},
        }

        with self._lock:
            self._memory_log.append(entry)
            if len(self._memory_log) > self.max_memory_entries:
                self._memory_log = self._memory_log[-self.max_memory_entries:]

        if database_url():
            try:
                engine = get_engine()
                with engine.begin() as conn:
                    conn.execute(
                        kb_access_audit.insert().values(
                            at=entry["at"],
                            actor=entry["actor"],
                            auth_method=entry["auth_method"],
                            jti=entry["jti"],
                            action=entry["action"],
                            resource=entry["resource"],
                            outcome=entry["outcome"],
                            detail=json.dumps(entry["detail"]),
                        )
                    )
            except Exception:
                # Audit logging must fail open to avoid service disruption
                pass

    def query(
        self,
        actor: str | None = None,
        action: str | None = None,
        outcome: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query audit log entries matching filters, newest first."""
        if database_url():
            try:
                engine = get_engine()
                with engine.connect() as conn:
                    q = select(kb_access_audit).order_by(kb_access_audit.c.id.desc()).limit(limit)
                    if actor:
                        q = q.where(kb_access_audit.c.actor == actor.strip())
                    if action:
                        q = q.where(kb_access_audit.c.action == action.strip())
                    if outcome:
                        q = q.where(kb_access_audit.c.outcome == outcome.strip())
                    rows = conn.execute(q).all()
                    return [
                        {
                            "id": r.id,
                            "at": r.at,
                            "actor": r.actor,
                            "auth_method": r.auth_method,
                            "jti": r.jti,
                            "action": r.action,
                            "resource": r.resource,
                            "outcome": r.outcome,
                            "detail": json.loads(r.detail or "{}"),
                        }
                        for r in rows
                    ]
            except Exception:
                pass

        with self._lock:
            entries = list(reversed(self._memory_log))
            res: list[dict[str, Any]] = []
            for e in entries:
                if actor and e["actor"] != actor.strip():
                    continue
                if action and e["action"] != action.strip():
                    continue
                if outcome and e["outcome"] != outcome.strip():
                    continue
                res.append(dict(e))
                if len(res) >= limit:
                    break
            return res


_audit_store = GovernanceAuditStore()


def get_governance_audit() -> GovernanceAuditStore:
    return _audit_store

