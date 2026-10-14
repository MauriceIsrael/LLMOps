"""Requirement → control coverage of an engagement, computed by the Hub (K17, contract 1.31).

Deterministic and declarative: the Hub **verifies nothing** (ADR-KH-01 D2, K6). For each requirement of the engagement and each
control it was matched to (``matched_controls``, resolved against the pinned knowledge snapshot), the coverage is what the
engagement's decisions *declare*:

* ``allocated``: an **asserted** decision cites the control, or an asset that implements it (``based_on``);
* ``proposed``: only a proposed decision does;
* ``uncovered``: no decision does.

A requirement evacuated by an asserted decision on it is not deliberated: it brings no row. A control the pinned knowledge
snapshot does not know is listed in ``unresolved``, never invented. ``verified`` does not exist here, and the origin is always
``knowledge-hub`` (the schema has no other value).
"""

from __future__ import annotations

import json
from typing import Any

ORIGIN = "knowledge-hub"
STATUSES = ("allocated", "proposed", "uncovered")
COUNTED = ("active", "proposed")  # a withdrawn or superseded decision covers nothing


def matched_controls(raw: Any) -> list[str]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "[]")
        except ValueError:
            return []
    return sorted({str(c) for c in raw or [] if c})


def coverage(requirements: list[dict[str, Any]], decisions: list[dict[str, Any]], kb_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """The ``compliance`` section: ``{origin, kb_snapshot, items, unresolved}``, sorted for a stable checksum."""
    pin = {"snapshot_id": kb_snapshot["snapshot_id"], "checksum": kb_snapshot["payload_sha256"]} if kb_snapshot else None
    controls = {c["id"]: c for c in (kb_snapshot or {}).get("controls", [])}
    cited = []
    for d in decisions:
        if d.get("status") in COUNTED:
            cited.append((d, {str(b["id"]) for b in d.get("based_on", [])}))
    items: list[dict[str, Any]] = []
    unresolved: list[dict[str, str]] = []
    for req in sorted(requirements, key=lambda r: r["id"]):
        disposition = req.get("disposition") or {}
        if disposition.get("status") == "active" and disposition.get("value") == "evacuated":
            continue
        for control_id in matched_controls(req.get("matched_controls")):
            control = controls.get(control_id)
            if control is None:
                unresolved.append({"requirement_id": req["id"], "control_id": control_id})
                continue
            implementers = set(control.get("implemented_by") or [])
            covering = [(d, refs & ({control_id} | implementers)) for d, refs in cited if refs & ({control_id} | implementers)]
            levels = {d["status"] for d, _ in covering}
            status = "allocated" if "active" in levels else ("proposed" if levels else "uncovered")
            items.append({
                "requirement_id": req["id"], "control_id": control_id, "framework": control.get("framework") or "",
                "severity": control.get("severity") or "", "status": status,
                "decisions": sorted({d["id"] for d, _ in covering}),
                "assets": sorted({a for _, hit in covering for a in hit if a != control_id}),
            })
    return {"origin": ORIGIN, "kb_snapshot": pin, "items": items, "unresolved": unresolved}
