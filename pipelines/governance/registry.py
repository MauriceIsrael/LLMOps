"""Owners registry in the governance database (decision D5: LLMOps is the authority)."""

from __future__ import annotations

import json

from sqlalchemy import select

from pipelines.governance.store import domain_owners, get_engine, governance_meta, owner_domains
from pipelines.kb_candidates.owners import Owner, OwnersRegistry


def load_registry_from_db() -> OwnersRegistry | None:
    """The registry stored in the database, or ``None`` when it was never seeded."""
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(select(domain_owners)).all()
        if not rows:
            return None
        domains = {r.domain: r.handle for r in conn.execute(select(owner_domains)).all()}
        default = conn.execute(select(governance_meta.c.value).where(governance_meta.c.key == "default_owner")).first()
    owners = {
        r.handle: Owner(handle=r.handle, email=r.email, discord_webhook=r.discord_webhook, ntfy_topic=r.ntfy_topic,
                        roles=tuple(json.loads(r.roles or "[]")), delegated=bool(r.delegated))
        for r in rows
    }
    return OwnersRegistry(owners=owners, domains=domains, default_owner=default.value if default else "@maintainers")


def save_registry(registry: OwnersRegistry) -> None:
    """Replace the stored registry (seeding, admin update)."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(domain_owners.delete())
        conn.execute(owner_domains.delete())
        conn.execute(governance_meta.delete().where(governance_meta.c.key == "default_owner"))
        for o in registry.owners.values():
            conn.execute(domain_owners.insert().values(
                handle=o.handle, email=o.email, discord_webhook=o.discord_webhook, ntfy_topic=o.ntfy_topic,
                roles=json.dumps(list(o.roles)), delegated=o.delegated))
        for domain, handle in registry.domains.items():
            conn.execute(owner_domains.insert().values(domain=domain, handle=handle))
        conn.execute(governance_meta.insert().values(key="default_owner", value=registry.default_owner))


KB_ROLES = ("kb:review", "kb:evaluate", "kb:maintain", "kb:admin")


def registry_from_payload(payload: dict) -> OwnersRegistry:
    """Validate an admin update: known roles, unique e-mails, consistent domains and default owner."""
    raw_owners = payload.get("owners")
    if not isinstance(raw_owners, list) or not raw_owners:
        raise ValueError("'owners' must be a non-empty list.")
    owners: dict[str, Owner] = {}
    emails: set[str] = set()
    for item in raw_owners:
        if not isinstance(item, dict) or not str(item.get("handle") or "").startswith("@"):
            raise ValueError("each owner needs a 'handle' starting with '@'.")
        handle = str(item["handle"])
        if handle in owners:
            raise ValueError(f"duplicate owner '{handle}'.")
        roles = tuple(item.get("roles") or ())
        unknown = [r for r in roles if r not in KB_ROLES]
        if unknown:
            raise ValueError(f"unknown role(s) for {handle}: {unknown} (expected {list(KB_ROLES)}).")
        email = (str(item["email"]).strip().lower() or None) if item.get("email") else None
        if email and email in emails:
            raise ValueError(f"the e-mail '{email}' is used by two owners.")
        if email:
            emails.add(email)
        owners[handle] = Owner(handle=handle, email=email, discord_webhook=item.get("discord_webhook"),
                               ntfy_topic=item.get("ntfy_topic"), roles=roles, delegated=bool(item.get("delegated")))
    domains = {str(k): str(v) for k, v in (payload.get("domains") or {}).items()}
    missing = sorted({h for h in domains.values() if h not in owners})
    if missing:
        raise ValueError(f"domains point to unknown owner(s): {missing}.")
    default_owner = str(payload.get("default_owner") or "")
    if default_owner not in owners:
        raise ValueError("'default_owner' must be one of the owners.")
    return OwnersRegistry(owners=owners, domains=domains, default_owner=default_owner)
