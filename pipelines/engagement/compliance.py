"""Requirement → control coverage of an engagement, computed by the Hub (K17, contract 1.31; declared chain, contract 1.34).

Deterministic and declarative: the Hub **verifies nothing** (ADR-KH-01 D2, K6). For each requirement of the engagement and each
control it was matched to (``matched_controls``, resolved against the pinned knowledge snapshot), the coverage is what the
engagement's decisions *declare*:

* ``allocated``: an **asserted** decision cites the control, or an asset that implements it (``based_on``);
* ``proposed``: only a proposed decision does;
* ``uncovered``: no decision does.

A requirement can also reach a control **without any matching of text**, through the chain the engagement itself declares
(contract 1.34): the requirement is carried by a subject, a decision on that subject cites an asset (or the control itself), and
the pinned snapshot says that asset implements the control. Such a row has ``basis: "declared_by_decision"`` and is never
``uncovered`` (it exists because a decision stands behind it). A pair already matched keeps its single, unchanged row.

A requirement evacuated by an asserted decision on it is not deliberated: it brings no row. A control the pinned knowledge
snapshot does not know is listed in ``unresolved``, never invented. ``verified`` does not exist here, and the origin is always
``knowledge-hub`` (the schema has no other value).
"""

from __future__ import annotations

import json
from typing import Any

ORIGIN = "knowledge-hub"
BASIS = "declared_by_decision"  # the only value of the optional ``basis`` of a row; a matched row has none
STATUSES = ("allocated", "proposed", "uncovered")
COUNTED = ("active", "proposed")  # a withdrawn or superseded decision covers nothing


def matched_controls(raw: Any) -> list[str]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "[]")
        except ValueError:
            return []
    return sorted({str(c) for c in raw or [] if c})


def _cited(decision: dict[str, Any], by_typed: dict[str, str]) -> set[str]:
    """What a decision cites (``based_on``), with a typed key (``decision:ADR-0001``) read as the asset it designates."""
    refs = {str(b["id"]) for b in decision.get("based_on", [])}
    return {by_typed.get(r, r) for r in refs}


def coverage(
    requirements: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    kb_snapshot: dict[str, Any] | None,
    subjects: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """The ``compliance`` section: ``{origin, kb_snapshot, items, unresolved}``, sorted for a stable checksum.

    ``subjects`` (``[{name, requirement_ids?}]``) lets the declared chain add the rows no matching produced; without it only
    matched rows exist.
    """
    pin = {"snapshot_id": kb_snapshot["snapshot_id"], "checksum": kb_snapshot["payload_sha256"]} if kb_snapshot else None
    controls = {c["id"]: c for c in (kb_snapshot or {}).get("controls", [])}
    by_typed = {a["typed_id"]: a["id"] for a in (kb_snapshot or {}).get("assets", []) if a.get("typed_id")}
    cited = [(d, _cited(d, by_typed)) for d in decisions if d.get("status") in COUNTED]

    def evacuated(req: dict[str, Any]) -> bool:
        disposition = req.get("disposition") or {}
        return disposition.get("status") == "active" and disposition.get("value") == "evacuated"

    items: list[dict[str, Any]] = []
    unresolved: list[dict[str, str]] = []
    for req in sorted(requirements, key=lambda r: r["id"]):
        if evacuated(req):
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

    # The declared chain: requirement <- subject <- decision -> cited asset -> control (pinned snapshot). No text is matched.
    seen = {(i["requirement_id"], i["control_id"]) for i in items}
    open_requirements = {r["id"] for r in requirements if not evacuated(r)}
    carried: dict[str, list[str]] = {}
    for subject in subjects or []:
        carried[subject["name"]] = sorted(rid for rid in subject.get("requirement_ids", []) if rid in open_requirements)
    chain: dict[tuple[str, str], list[tuple[dict[str, Any], set[str]]]] = {}
    for decision, refs in cited:
        for requirement_id in carried.get(decision.get("subject") or "", []):
            for control_id, control in controls.items():
                hit = refs & ({control_id} | set(control.get("implemented_by") or []))
                if hit and (requirement_id, control_id) not in seen:
                    chain.setdefault((requirement_id, control_id), []).append((decision, hit))
    for (requirement_id, control_id), covering in chain.items():
        levels = {d["status"] for d, _ in covering}
        control = controls[control_id]
        items.append({
            "requirement_id": requirement_id, "control_id": control_id, "framework": control.get("framework") or "",
            "severity": control.get("severity") or "", "status": "allocated" if "active" in levels else "proposed",
            "decisions": sorted({d["id"] for d, _ in covering}),
            "assets": sorted({a for _, hit in covering for a in hit if a != control_id}),
            "basis": BASIS,
        })
    items.sort(key=lambda i: (i["requirement_id"], i["control_id"]))
    return {"origin": ORIGIN, "kb_snapshot": pin, "items": items, "unresolved": unresolved}
