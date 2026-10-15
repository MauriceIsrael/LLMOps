"""What anchors a programme in text bound for the knowledge base (K13, ADR-KH-01 A10-d-3).

The knowledge base is agnostic of every programme: a decision of a project enters it only as a candidate a person reviewed, and
nothing may tie it back to the engagement it came from. This module is the single definition of that anchor, shared by the
candidate cycle (``anonymization`` check) and the reuse journal (``subject_label``):

* the identifier of an engagement (the registered ones, the working bases on disk, and the one the candidate comes from);
* an e-mail address; a member handle (``@name``); an IP address or CIDR (documentation ranges allowed); a denylisted name.

``anchors`` returns what it found by category; values that identify a person are masked so the reviewer can locate them without
the check result becoming a second copy of the anchor.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pipelines.doctrine.text import normalize, normalize_phrase
from pipelines.kb_candidates.checks import find_ip_addresses, load_denylist

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
HANDLE = re.compile(r"(?<![\w@.])@[a-z][a-z0-9_-]{1,38}\b")
ANCHOR_FIELDS = ("source_engagement", "engagement", "engagement_id", "client", "site")  # front matter keys that name a programme


def known_engagement_ids(extra: list[str | None] | None = None) -> set[str]:
    """Engagements this deployment knows: registered, working bases on disk, plus ``extra`` (e.g. the candidate's own)."""
    from mcp_server.core.config import server_config

    ids: set[str] = {e for e in (extra or []) if e}
    base = Path(server_config.engagements_dir)
    if base.is_dir():
        ids |= {p.name.split(".")[0] for p in base.iterdir() if p.suffix in (".lbug", ".kuzu") or p.is_dir()}
    try:
        from pipelines.engagement.access import get_access
        from pipelines.governance.store import engagement_registry

        access = get_access()
        if access is not None:
            with access.engine.connect() as conn:
                ids |= {r[0] for r in conn.execute(engagement_registry.select().with_only_columns(engagement_registry.c.engagement))}
    except Exception:  # noqa: BLE001 - an unreachable registry must not stop the other checks
        pass
    return {i for i in ids if len(i) >= 3 and i != "default"}


def mask_email(address: str) -> str:
    local, _, domain = address.partition("@")
    return f"{local[:1]}***@{domain}"


def anchors(text: str, kb_dir: str | Path, engagement_ids: set[str], handle_text: str | None = None) -> dict[str, list[str]]:
    """What in ``text`` ties it to a programme, by category (empty when nothing does).

    ``handle_text`` narrows where member handles are looked for: the promotion records the *reviewers* of the knowledge base in the
    front matter (``validated_by``), which is governance of the base, not a programme anchor.
    """
    found: dict[str, list[str]] = {}
    norm = f" {normalize(text)} "
    names = sorted({t for t in load_denylist(kb_dir) if normalize_phrase(t) and f" {normalize_phrase(t)} " in norm})
    if names:
        found["names"] = names
    ips = sorted(set(find_ip_addresses(text)))
    if ips:
        found["ip_addresses"] = ips
    emails = sorted({mask_email(m.group(0)) for m in EMAIL.finditer(text)})
    if emails:
        found["emails"] = emails
    handles = sorted({m.group(0) for m in HANDLE.finditer(EMAIL.sub(" ", text if handle_text is None else handle_text))})
    if handles:
        found["handles"] = handles
    lowered = text.lower()
    ids = sorted(i for i in engagement_ids if re.search(rf"(?<![\w-]){re.escape(i.lower())}(?![\w-])", lowered))
    if ids:
        found["engagement_ids"] = ids
    return found


def describe(found: dict[str, list[str]]) -> str:
    labels = {"names": "denylisted name(s)", "ip_addresses": "IP address(es)/CIDR", "emails": "e-mail address(es)",
              "handles": "member handle(s)", "engagement_ids": "engagement identifier(s)", "fields": "programme field(s)"}
    return "; ".join(f"{labels[k]}: {v}" for k, v in found.items() if v)


def anchor_fields(frontmatter: dict[str, Any] | None) -> list[str]:
    return sorted(k for k in (frontmatter or {}) if k in ANCHOR_FIELDS and (frontmatter or {}).get(k))
