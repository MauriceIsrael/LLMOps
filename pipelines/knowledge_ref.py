"""Citable references into the knowledge base (K3, ADR-KH-01 D8).

A suite document cites the Hub by ``KnowledgeRef {sourceId: 'knowledge-hub', knowledgeKey, version}``: "a partial reference
does not exist". ``knowledgeKey`` is the typed identifier (``decision:ADR-0001``); ``version`` is the element's **revision**
(front matter ``revision``, a positive integer, 1 when absent, incremented by every accepted amendment). The legacy front
matter ``version`` is not used: for a control it is the revision of the regulatory text (``2022/2555``, ``Rel-18``).

Two guarantees, both testable:

* the same ``{knowledgeKey, version}`` always resolves to the same bytes: ``version-ledger.json`` records the SHA-256 of the
  content of every published revision and the export refuses a revision whose content changed;
* a reference is resolved **from a sealed snapshot** (verified against its checksum), never from the live base. A revision
  the snapshot does not hold is refused explicitly, never answered with the current content.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from pipelines import canonical
from pipelines.kb_candidates.kb import split_frontmatter

SOURCE_ID = "knowledge-hub"
LEDGER_NAME = "version-ledger.json"
SNAPSHOT_ID = re.compile(r"^snapshot-\d{4}-\d{2}-\d{2}-[0-9a-f]{7,40}$")
PAYLOAD_KEYS = ("applicability_index", "assets", "glossary", "frameworks", "controls", "compliance_index")


class VersionLedgerError(ValueError):
    """A published revision would change content, or a new revision is not recorded."""


class ResolutionError(LookupError):
    """A reference cannot be resolved. ``reason`` is machine-readable, ``detail`` carries what is available."""

    def __init__(self, reason: str, message: str, **detail: Any) -> None:
        self.reason = reason
        self.detail = detail
        super().__init__(message)


def format_typed_id(asset_id: str, asset_type: str | None) -> str:
    """Asset identifier with a normalised type prefix (``type:slug``)."""
    t = (asset_type or "").lower()
    if t in ("decision", "adr") or asset_id.startswith("ADR-"):
        return f"decision:{asset_id}"
    if t == "principle" or asset_id.startswith("P-"):
        return f"principle:{asset_id}"
    if t == "pattern" or asset_id.startswith("PAT-"):
        return f"pattern:{asset_id}"
    if t == "template" or asset_id.startswith("TPL-"):
        return f"template:{asset_id}"
    if t == "risk" or asset_id.startswith(("RSK-", "R-")):
        return f"risk:{asset_id}"
    if t in ("questionnaire", "framework"):
        return f"{t}:{asset_id}"
    return f"asset:{asset_id}"


def knowledge_ref(knowledge_key: str, revision: int) -> dict[str, str]:
    return {"sourceId": SOURCE_ID, "knowledgeKey": knowledge_key, "version": str(revision)}


def content_sha256(content: str) -> str:
    return "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()


def revision_of(content: str) -> int:
    """The ``revision`` of an asset's front matter: a positive integer, ``1`` when absent. Anything else is refused."""
    front, _ = split_frontmatter(content)
    value = (front or {}).get("revision", 1)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"front matter 'revision' must be a positive integer, got {value!r}")
    return value


def bump_revision(content: str) -> int:
    """Revision of the next accepted amendment of ``content``."""
    return revision_of(content) + 1


# --- ledger -------------------------------------------------------------------------------------------------------


def load_ledger(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("revisions", {})


def write_ledger(path: Path, revisions: dict[str, dict[str, str]]) -> None:
    doc = {
        "description": (
            "Append-only record of the content hash of every published revision of a knowledge element "
            "(ADR-KH-01 D8, lot K3): the same {knowledgeKey, version} always resolves to the same bytes. "
            "Never edit by hand; `poetry run python scripts/export_fixtures.py` records new revisions."
        ),
        "revisions": {k: dict(sorted(revisions[k].items(), key=lambda kv: int(kv[0]))) for k in sorted(revisions)},
    }
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def check_revisions(
    ledger: dict[str, dict[str, str]], published: dict[str, tuple[int, str]], record: bool
) -> dict[str, dict[str, str]]:
    """Check ``{key: (revision, content_sha256)}`` against the ledger; return the ledger to write when ``record``.

    A known ``(key, revision)`` with another hash is always refused. An unknown one is refused unless ``record``.
    Keys the ledger holds but the base no longer has stay recorded: an identifier is never recycled.
    """
    updated = {k: dict(v) for k, v in ledger.items()}
    problems: list[str] = []
    for key, (revision, sha) in sorted(published.items()):
        known = updated.get(key, {}).get(str(revision))
        if known is None:
            if not record:
                problems.append(f"{key} revision {revision} is not in the version ledger (run scripts/export_fixtures.py)")
            updated.setdefault(key, {})[str(revision)] = sha
        elif known != sha:
            problems.append(
                f"{key} revision {revision}: the content changed without a new revision "
                f"(ledger {known[:19]}..., now {sha[:19]}...). Amend through `kb promote` or raise `revision` in the front matter."
            )
    if problems:
        raise VersionLedgerError("; ".join(problems))
    return updated


# --- resolution from a sealed snapshot ----------------------------------------------------------------------------


def load_snapshot(snapshots_dir: Path, snapshot_id: str | None = None) -> dict[str, Any]:
    """The designated sealed snapshot (``latest`` when ``snapshot_id`` is ``None``), verified against its checksum."""
    if snapshot_id is None:
        path = snapshots_dir / "latest.json"
    else:
        if not SNAPSHOT_ID.match(snapshot_id):
            raise ResolutionError("invalid_snapshot_id", f"'{snapshot_id}' is not a snapshot identifier")
        path = snapshots_dir / f"{snapshot_id}.json"
    if not path.exists():
        raise ResolutionError("snapshot_unavailable", f"snapshot '{snapshot_id or 'latest'}' is not available", snapshot=snapshot_id)
    doc = json.loads(path.read_text(encoding="utf-8"))
    payload = {k: doc.get(k, [] if k in ("frameworks", "controls") else {}) for k in PAYLOAD_KEYS}
    if canonical.sha256(payload) != doc.get("payload_sha256"):
        raise ResolutionError("snapshot_corrupt", "the snapshot content does not match its checksum", snapshot=doc.get("snapshot_id"))
    return doc


def resolve(snapshot: dict[str, Any], key_or_id: str, version: str | None = None) -> dict[str, Any]:
    """The element ``key_or_id`` (typed key or bare id) at ``version`` from ``snapshot``; refuses, never approximates."""
    asset = next((a for a in snapshot.get("assets", []) if key_or_id in (a.get("typed_id"), a.get("id"))), None)
    if asset is None:
        raise ResolutionError("unknown_key", f"'{key_or_id}' is not in snapshot {snapshot.get('snapshot_id')}", snapshot=snapshot.get("snapshot_id"))
    held = str(asset["revision"])
    if version is not None and str(version) != held:
        raise ResolutionError(
            "version_not_in_snapshot",
            f"{asset['typed_id']} version {version} is not in snapshot {snapshot['snapshot_id']} (it holds {held})",
            snapshot=snapshot["snapshot_id"],
            available_version=held,
        )
    content = asset.get("content", "")
    if content_sha256(content) != asset.get("content_sha256"):
        raise ResolutionError("content_corrupt", f"{asset['typed_id']} content does not match its hash", snapshot=snapshot["snapshot_id"])
    return {
        "knowledge_ref": asset["knowledge_ref"],
        "id": asset["id"],
        "typed_id": asset["typed_id"],
        "title": asset.get("title"),
        "type": asset.get("type"),
        "status": asset.get("status"),
        "confidence": asset.get("confidence"),
        "version": held,
        "content_sha256": asset["content_sha256"],
        "content": content,
        "snapshot": {
            "snapshot_id": snapshot["snapshot_id"],
            "checksum": snapshot.get("checksum", snapshot.get("payload_sha256")),
            "created_at": snapshot.get("created_at"),
        },
    }
