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

    def as_dict(self) -> dict[str, Any]:
        return {"handle": self.handle, "email": self.email, "discord_webhook": self.discord_webhook,
                "ntfy_topic": self.ntfy_topic}


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


def load_owners(kb_dir: str | Path) -> OwnersRegistry:
    path = Path(kb_dir) / DEFAULT_OWNERS_FILE
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else {}
    data = data or {}
    owners = {
        handle: Owner(
            handle=handle,
            email=(info or {}).get("email"),
            discord_webhook=(info or {}).get("discord_webhook"),
            ntfy_topic=(info or {}).get("ntfy_topic"),
        )
        for handle, info in (data.get("owners") or {}).items()
    }
    return OwnersRegistry(
        owners=owners,
        domains={str(k): str(v) for k, v in (data.get("domains") or {}).items()},
        default_owner=str(data.get("default_owner") or "@maintainers"),
    )
