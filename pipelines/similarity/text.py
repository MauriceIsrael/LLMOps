"""Text to encode for each asset: deterministic, so the client and the server agree on what a vector stands for.

The server never encodes anything: it tells the client which text to encode (``pending``), and verifies that a
deposited vector carries the SHA-256 of the text the asset has *now* (a changed asset makes its vector stale).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from pipelines.kb_candidates.kb import KbAsset, load_assets

EMBEDDABLE_TYPES = ("principle", "pattern", "decision", "control")
SECTIONS = {
    "principle": ("Statement",),
    "pattern": ("Problem", "Solution"),
    "decision": ("Context", "Decision"),
    "control": ("Legal Requirement",),
}
MAX_CHARS = 2000
_HEADING = re.compile(r"^## (.+?)\s*$", re.MULTILINE)


def _section(body: str, heading: str) -> str:
    matches = list(_HEADING.finditer(body))
    for i, m in enumerate(matches):
        if m.group(1).strip() == heading:
            end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
            return " ".join(body[m.end():end].split())
    return ""


def asset_text(asset: KbAsset) -> str:
    """Title (and French title for a control), then the sections that state what the asset says."""
    parts = [asset.title]
    title_fr = asset.frontmatter.get("title_fr")
    if title_fr:
        parts.append(str(title_fr))
    for heading in SECTIONS.get(asset.type, ()):
        text = _section(asset.body, heading)
        if text:
            parts.append(text)
    if len(parts) == 1 + bool(title_fr):  # no known section: fall back to the beginning of the body
        parts.append(" ".join(asset.body.split())[:MAX_CHARS])
    return "\n".join(parts)[:MAX_CHARS]


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def embeddable_assets(kb_dir: str | Path) -> list[dict[str, Any]]:
    """Active doctrine and controls with the text to encode, in a stable order."""
    items = []
    for a in load_assets(kb_dir):
        if a.type not in EMBEDDABLE_TYPES or str(a.frontmatter.get("status")) != "active":
            continue
        text = asset_text(a)
        items.append({"ref": a.id, "type": a.type, "title": a.title, "text": text, "text_sha256": text_sha256(text)})
    return sorted(items, key=lambda i: (i["type"], i["ref"]))
