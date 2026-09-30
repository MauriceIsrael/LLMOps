"""Domain owners (``data/kb/owners.yaml``): routing of candidates to their reviewers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_OWNERS_FILE = "owners.yaml"


@dataclass(frozen=True)
class Owner:
    handle: str
    email: str | None = None
    discord_webhook: str | None = None
    ntfy_topic: str | None = None
    roles: tuple[str, ...] = ()
    delegated: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"handle": self.handle, "email": self.email, "discord_webhook": self.discord_webhook,
                "ntfy_topic": self.ntfy_topic}

    def public_dict(self) -> dict[str, Any]:
        """Registry entry without notification secrets (webhook URLs)."""
        return {"handle": self.handle, "email": self.email, "roles": list(self.roles), "delegated": self.delegated}


@dataclass
class OwnersRegistry:
    owners: dict[str, Owner]
    domains: dict[str, str]
    default_owner: str

    def owner(self, handle: str) -> Owner:
        return self.owners.get(handle) or Owner(handle=handle)

    def owner_for_domains(self, domains: list[str]) -> Owner:
        """Owner of the first domain that has one (a sub-domain inherits its parent's owner)."""
        for domain in domains:
            parts = domain.split("/")
            for i in range(len(parts), 0, -1):
                handle = self.domains.get("/".join(parts[:i]))
                if handle:
                    return self.owner(handle)
        return self.owner(self.default_owner)

    def by_email(self, email: str) -> Owner | None:
        wanted = email.strip().lower()
        return next((o for o in self.owners.values() if o.email and o.email.lower() == wanted), None)

    def owned_domains(self, handle: str) -> list[str]:
        return sorted(d for d, h in self.domains.items() if h == handle)

    def can_review(self, handle: str, domains: list[str]) -> bool:
        """Owner of a domain of the candidate (or of a parent), default owner, or ``kb:maintain``."""
        owner = self.owners.get(handle)
        if owner is None:
            return False
        if handle == self.default_owner or "kb:maintain" in owner.roles:
            return True
        return any(self._owns(handle, d) for d in domains)

    def _owns(self, handle: str, domain: str) -> bool:
        parts = domain.split("/")
        return any(self.domains.get("/".join(parts[:i])) == handle for i in range(len(parts), 0, -1))


def load_owners(kb_dir: str | Path) -> OwnersRegistry:
    """Registry from the governance database when it holds owners, else from ``owners.yaml``."""
    from pipelines.governance.store import database_url

    if database_url():
        from pipelines.governance.registry import load_registry_from_db

        registry = load_registry_from_db()
        if registry is not None:
            return registry
    return load_owners_file(kb_dir)


def load_owners_file(kb_dir: str | Path) -> OwnersRegistry:
    path = Path(kb_dir) / DEFAULT_OWNERS_FILE
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
    data = data or {}
    owners = {
        handle: Owner(
            handle=handle,
            email=(info or {}).get("email"),
            discord_webhook=(info or {}).get("discord_webhook"),
            ntfy_topic=(info or {}).get("ntfy_topic"),
            roles=tuple((info or {}).get("roles") or ()),
        )
        for handle, info in (data.get("owners") or {}).items()
    }
    return OwnersRegistry(
        owners=owners,
        domains={str(k): str(v) for k, v in (data.get("domains") or {}).items()},
        default_owner=str(data.get("default_owner") or "@maintainers"),
    )
