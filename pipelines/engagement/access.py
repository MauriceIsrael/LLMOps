"""Roles, membership and audit of an engagement (K14, ADR-KH-01 A11).

An engagement with a row in ``engagement_registry`` is **managed**: only its members reach it, in every environment (the
"open outside production" mode of ``authorise`` applies to unmanaged, legacy engagements only). A person acts through a
trusted client (a token carrying ``eng:delegate``, which sends ``X-Actor-Email``); the client never decides who may do what.

Roles and the actions they allow::

    reader       read
    contributor  read, contribute            (propose statements and answers; nothing becomes asserted)
    decider      read, contribute, decide    (assert and arbitrate: only a person with this role asserts)
    admin        everything above + export, import, members

``members`` (create the engagement, manage members) is also allowed to the operator token (``server_admin``), which cannot
read the content: operating the server and reading a programme's data are different powers.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from pipelines.governance.store import (
    database_url,
    engagement_audit,
    engagement_exports,
    engagement_members,
    engagement_registry,
    get_engine,
)

ROLES = ("reader", "contributor", "decider", "admin")
ACTIONS = ("read", "contribute", "decide", "export", "import", "members")
ROLE_ACTIONS: dict[str, frozenset[str]] = {
    "reader": frozenset({"read"}),
    "contributor": frozenset({"read", "contribute"}),
    "decider": frozenset({"read", "contribute", "decide"}),
    "admin": frozenset({"read", "contribute", "decide", "export", "import", "members"}),
}
CONFIDENTIALITY = ("public", "internal", "confidential")
ENGAGEMENT_ID = re.compile(r"^[a-z0-9-]{1,64}$")
HANDLE = re.compile(r"^@[a-z0-9][a-z0-9._-]{0,62}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AccessError(ValueError):
    """An invalid request on the registry (unknown role, no admin left, duplicate...). ``argument`` names the field."""

    def __init__(self, argument: str, reason: str) -> None:
        self.argument = argument
        self.reason = reason
        super().__init__(f"{argument}: {reason}")


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _email(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not EMAIL.match(text):
        raise AccessError("email", f"'{value}' is not an e-mail address")
    return text


def validate_members(members: Any) -> list[dict[str, str]]:
    """Normalised member list; at least one admin; unique e-mails and handles; known roles."""
    if not isinstance(members, list) or not members:
        raise AccessError("members", "a non-empty list is required")
    out: list[dict[str, str]] = []
    emails: set[str] = set()
    handles: set[str] = set()
    for item in members:
        if not isinstance(item, dict):
            raise AccessError("members", "each member is an object {email, handle, role}")
        email = _email(item.get("email"))
        handle = str(item.get("handle") or "")
        role = str(item.get("role") or "")
        if not HANDLE.match(handle):
            raise AccessError("handle", f"'{handle}' must look like @name (lowercase letters, digits, . _ -)")
        if role not in ROLES:
            raise AccessError("role", f"'{role}' is not one of {list(ROLES)}")
        if email in emails:
            raise AccessError("email", f"the e-mail '{email}' appears twice")
        if handle in handles:
            raise AccessError("handle", f"the handle '{handle}' appears twice")
        emails.add(email)
        handles.add(handle)
        out.append({"email": email, "handle": handle, "role": role})
    if not any(m["role"] == "admin" for m in out):
        raise AccessError("members", "at least one admin is required: an engagement nobody can administer is locked")
    return out


class EngagementAccess:
    def __init__(self, url: str | None = None) -> None:
        self.engine = get_engine(url)

    # --- registry -------------------------------------------------------------------------------------------------

    def is_managed(self, engagement: str) -> bool:
        with self.engine.connect() as conn:
            return conn.execute(
                select(func.count()).select_from(engagement_registry).where(engagement_registry.c.engagement == engagement)
            ).scalar_one() > 0

    def confidentiality(self, engagement: str) -> str | None:
        with self.engine.connect() as conn:
            row = conn.execute(
                select(engagement_registry.c.confidentiality).where(engagement_registry.c.engagement == engagement)
            ).first()
        return row[0] if row else None

    def create(self, engagement: str, confidentiality: str, admin_email: str, admin_handle: str, created_by: str) -> dict[str, Any]:
        if not ENGAGEMENT_ID.match(str(engagement)):
            raise AccessError("engagement", "must be lowercase letters, digits and hyphens (1 to 64 characters)")
        if confidentiality not in CONFIDENTIALITY:
            raise AccessError("confidentiality", f"must be one of {list(CONFIDENTIALITY)}")
        admin = validate_members([{"email": admin_email, "handle": admin_handle, "role": "admin"}])[0]
        now = _now()
        try:
            with self.engine.begin() as conn:
                conn.execute(engagement_registry.insert().values(
                    engagement=engagement, confidentiality=confidentiality, created_at=now, created_by=created_by))
                conn.execute(engagement_members.insert().values(
                    engagement=engagement, email=admin["email"], handle=admin["handle"], role="admin",
                    added_by=created_by, added_at=now))
        except IntegrityError as err:
            raise AccessError("engagement", f"'{engagement}' already exists") from err
        self.audit(engagement, created_by, "members", "allowed", {"event": "created", "confidentiality": confidentiality})
        return {"engagement": engagement, "confidentiality": confidentiality, "members": self.members(engagement)}

    def set_confidentiality(self, engagement: str, confidentiality: str, by: str) -> None:
        if confidentiality not in CONFIDENTIALITY:
            raise AccessError("confidentiality", f"must be one of {list(CONFIDENTIALITY)}")
        with self.engine.begin() as conn:
            conn.execute(engagement_registry.update().where(engagement_registry.c.engagement == engagement)
                         .values(confidentiality=confidentiality))
        self.audit(engagement, by, "members", "allowed", {"event": "confidentiality", "to": confidentiality})

    # --- members --------------------------------------------------------------------------------------------------

    def members(self, engagement: str) -> list[dict[str, str]]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(engagement_members).where(engagement_members.c.engagement == engagement)
                                .order_by(engagement_members.c.handle)).all()
        return [{"email": r.email, "handle": r.handle, "role": r.role} for r in rows]

    def replace_members(self, engagement: str, members: Any, by: str) -> list[dict[str, str]]:
        valid = validate_members(members)
        now = _now()
        with self.engine.begin() as conn:
            conn.execute(engagement_members.delete().where(engagement_members.c.engagement == engagement))
            for m in valid:
                conn.execute(engagement_members.insert().values(engagement=engagement, added_by=by, added_at=now, **m))
        self.audit(engagement, by, "members", "allowed", {"event": "members_replaced", "handles": [m["handle"] for m in valid]})
        return valid

    def member(self, engagement: str, email: str) -> dict[str, str] | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(engagement_members).where(
                engagement_members.c.engagement == engagement, engagement_members.c.email == email.strip().lower())).first()
        return {"email": row.email, "handle": row.handle, "role": row.role} if row else None

    # --- sealed exports (K11) --------------------------------------------------------------------------------------

    def get_export(self, snapshot_id: str) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(engagement_exports).where(engagement_exports.c.snapshot_id == snapshot_id)).first()
        if row is None:
            return None
        return {"engagement": row.engagement, "envelope": json.loads(row.envelope), "produced_by": row.produced_by}

    def put_export(self, envelope: dict[str, Any], engagement: str, produced_by: str, is_provisional: bool) -> bool:
        """Store an issued snapshot; ``False`` when that identifier (same content) already exists. Never overwrites."""
        from pipelines import canonical

        try:
            with self.engine.begin() as conn:
                conn.execute(engagement_exports.insert().values(
                    snapshot_id=envelope["snapshotId"], engagement=engagement, checksum=envelope["checksum"],
                    produced_at=envelope["createdAt"], produced_by=produced_by, is_provisional=is_provisional,
                    envelope=canonical.dumps(envelope)))
            return True
        except IntegrityError:
            return False

    def list_exports(self, engagement: str) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(engagement_exports).where(engagement_exports.c.engagement == engagement)
                                .order_by(engagement_exports.c.produced_at.desc(), engagement_exports.c.snapshot_id)).all()
        return [{"sourceSystem": "knowledge-hub", "snapshotId": r.snapshot_id, "checksum": r.checksum,
                 "producedAt": r.produced_at, "produced_by": r.produced_by, "is_provisional": bool(r.is_provisional)}
                for r in rows]

    # --- audit ----------------------------------------------------------------------------------------------------

    def audit(self, engagement: str, actor: str, action: str, outcome: str, detail: dict[str, Any] | None = None) -> None:
        with self.engine.begin() as conn:
            conn.execute(engagement_audit.insert().values(
                at=_now(), engagement=engagement, actor=actor, action=action, outcome=outcome,
                detail=json.dumps(detail or {}, ensure_ascii=False, sort_keys=True)))

    def audit_events(self, engagement: str, limit: int = 100) -> list[dict[str, Any]]:
        with self.engine.connect() as conn:
            rows = conn.execute(select(engagement_audit).where(engagement_audit.c.engagement == engagement)
                                .order_by(engagement_audit.c.id.desc()).limit(max(1, min(limit, 1000)))).all()
        return [{"id": r.id, "at": r.at, "actor": r.actor, "action": r.action, "outcome": r.outcome,
                 "detail": json.loads(r.detail or "{}")} for r in rows]


def get_access() -> EngagementAccess | None:
    """The access registry when a governance database is configured, else ``None`` (no engagement is managed)."""
    return EngagementAccess() if database_url() else None
