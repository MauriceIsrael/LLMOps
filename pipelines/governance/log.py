"""Governance journal: events (append-only), review requests and comments (lot L6).

Everything here needs the governance database (``database_url()``); without it
``get_log()`` returns ``None`` and the cycle runs exactly as in contract 1.3.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from pipelines.governance.store import (
    comments,
    database_url,
    get_engine,
    governance_events,
    review_requests,
)

EVENT_TYPES = (
    "candidate.submitted", "candidate.assigned", "review.requested", "candidate.reviewed",
    "candidate.commented", "candidate.promoted", "candidate.published", "reminder.due",
    "owners.updated", "eval.updated", "coverage.changed",
)
REQUEST_KINDS = ("second_review", "advice")
DUE_BUSINESS_DAYS = 5


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def add_business_days(start: datetime, days: int) -> datetime:
    cursor, left = start, days
    while left > 0:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5:
            left -= 1
    return cursor


def default_due_at(start: datetime | None = None) -> str:
    return add_business_days(start or datetime.now(UTC), DUE_BUSINESS_DAYS).strftime("%Y-%m-%dT%H:%M:%SZ")


class GovernanceLog:
    def __init__(self, url: str | None = None) -> None:
        self.engine = get_engine(url)

    # ------------------------------------------------------------------ events

    def emit(self, type_: str, candidate_id: str | None, actor: str, recipients: list[str] | None = None,
             **payload: Any) -> int:
        with self.engine.begin() as conn:
            res = conn.execute(governance_events.insert().values(
                at=now_iso(), type=type_, candidate_id=candidate_id, actor=actor,
                recipients=json.dumps(sorted(set(recipients or []))),
                payload=json.dumps(payload, ensure_ascii=False, default=str)))
            return int((res.inserted_primary_key or (0,))[0])

    def events_since(self, cursor: int = 0, limit: int = 100) -> dict[str, Any]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(governance_events).where(governance_events.c.id > cursor)
                                .order_by(governance_events.c.id).limit(limit)).all()
        events = [{"id": r.id, "at": r.at, "type": r.type, "candidate_id": r.candidate_id, "actor": r.actor,
                   "recipients": json.loads(r.recipients), "payload": json.loads(r.payload)} for r in rows]
        return {"events": events, "next_cursor": events[-1]["id"] if events else cursor}

    # ---------------------------------------------------------------- requests

    def create_request(self, candidate_id: str, handle: str, kind: str, requested_by: str,
                       message: str | None = None, due_at: str | None = None) -> dict[str, Any]:
        values = {"candidate_id": candidate_id, "requested_handle": handle, "kind": kind, "message": message,
                  "requested_by": requested_by, "due_at": due_at or default_due_at(), "status": "open",
                  "created_at": now_iso()}
        with self.engine.begin() as conn:
            res = conn.execute(review_requests.insert().values(**values))
            return {"id": int((res.inserted_primary_key or (0,))[0]), **values, "closed_at": None}

    def close_requests(self, candidate_id: str, handle: str, status: str = "done") -> int:
        with self.engine.begin() as conn:
            res = conn.execute(review_requests.update().where(
                (review_requests.c.candidate_id == candidate_id) & (review_requests.c.requested_handle == handle)
                & (review_requests.c.status == "open")).values(status=status, closed_at=now_iso()))
            return int(res.rowcount)

    def requests(self, handle: str | None = None, candidate_id: str | None = None,
                 status: str | None = "open") -> list[dict[str, Any]]:
        query = select(review_requests).order_by(review_requests.c.id)
        if handle:
            query = query.where(review_requests.c.requested_handle == handle)
        if candidate_id:
            query = query.where(review_requests.c.candidate_id == candidate_id)
        if status:
            query = query.where(review_requests.c.status == status)
        with self.engine.connect() as conn:
            return [dict(r._mapping) for r in conn.execute(query).all()]

    # ---------------------------------------------------------------- comments

    def add_comment(self, candidate_id: str, author: str, body: str) -> dict[str, Any]:
        values = {"candidate_id": candidate_id, "author": author, "body": body, "at": now_iso()}
        with self.engine.begin() as conn:
            res = conn.execute(comments.insert().values(**values))
            return {"id": int((res.inserted_primary_key or (0,))[0]), **values}

    def comments(self, candidate_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(comments).where(comments.c.candidate_id == candidate_id)
                                .order_by(comments.c.id)).all()
        return [dict(r._mapping) for r in rows]


def get_log() -> GovernanceLog | None:
    """The journal when a governance database is configured, else ``None``."""
    return GovernanceLog() if database_url() else None
