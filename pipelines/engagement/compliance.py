"""Declared coverage requirement → control in the engagement snapshot (K17, contract 1.30).

The Hub verifies nothing (ADR-KH-01 D2) and does not match texts here. It states a **chain of declarations**, each link of
which a reader can follow in the same snapshot:

    requirement  ←carried by←  subject  ←decided by←  decision  →cites→  knowledge asset  →implements→  control

* the requirement is carried by the subject (contract 1.27);
* the decision is the one recorded on that subject, and it cites the asset in ``based_on`` (K16);
* the asset implements the control in the **pinned** knowledge snapshot (``compliance_index``), never in the live base.

A link counts as ``allocated`` only while an **asserted** decision stands behind it; a link carried only by proposed decisions
is ``proposed``. A withdrawn or superseded decision brings none. The status is never ``verified`` and the section never names an
origin: lowering a decision from asserted to proposed changes the section, hence the checksum.

What this is not: it does not say the control is met, nor that the asset's text answers the requirement. A control the
requirement *should* be matched to but no decision declares is not listed here (that would take a text matching outside the
pinned snapshot): it stays visible as a requirement carried by a subject without any link.
"""

from __future__ import annotations

from typing import Any

BASIS = "declared_by_decision"
STATUSES = ("allocated", "proposed")
ASSERTION = {"allocated": "asserted", "proposed": "proposed"}


def _control_index(kb_snapshot: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    """Asset identifier → the controls it implements, from the pinned snapshot (sorted, deterministic)."""
    by_asset: dict[str, list[dict[str, str]]] = {}
    for framework, controls in (kb_snapshot.get("compliance_index") or {}).items():
        for control_id, entry in controls.items():
            for asset_id in entry.get("implemented_by") or []:
                by_asset.setdefault(asset_id, []).append(
                    {"control_ref": control_id, "framework": framework, "control_version": str(entry.get("version") or "")})
    for controls_of in by_asset.values():
        controls_of.sort(key=lambda c: (c["framework"], c["control_ref"]))
    return by_asset


def _asset(kb_snapshot: dict[str, Any], key: str) -> dict[str, Any] | None:
    return next((a for a in kb_snapshot.get("assets", []) if key in (a.get("typed_id"), a.get("id"))), None)


def derive(
    requirements: list[dict[str, Any]],
    subjects: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    kb_snapshot: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """The ``compliance`` rows of an engagement: pure, sorted, empty when nothing is declared or the base is not pinned."""
    if kb_snapshot is None:
        return []
    known = {r["id"] for r in requirements}
    decided_out = {  # a requirement the people decided not to deliberate is out of the chain
        r["id"] for r in requirements
        if (r.get("disposition") or {}).get("status") == "active" and r["disposition"]["value"] != "deliberated"}
    carried = {s["name"]: [rid for rid in s.get("requirement_ids", []) if rid in known and rid not in decided_out] for s in subjects}
    controls_of = _control_index(kb_snapshot)

    # (requirement, control) → {"active": {decision: assets}, "proposed": {decision: assets}}
    links: dict[tuple[str, str], dict[str, Any]] = {}
    for d in decisions:
        if d.get("status") not in ("active", "proposed"):
            continue
        requirement_ids = carried.get(d.get("subject") or "", [])
        if not requirement_ids:
            continue
        for ref in d.get("based_on") or []:
            asset = _asset(kb_snapshot, ref["id"])
            if asset is None:
                continue
            for control in controls_of.get(asset["id"], []):
                for rid in requirement_ids:
                    slot = links.setdefault((rid, control["control_ref"]), {**control, "active": {}, "proposed": {}})
                    slot["active" if d["status"] == "active" else "proposed"].setdefault(d["id"], set()).add(asset["typed_id"])

    rows: list[dict[str, Any]] = []
    for (rid, cid), slot in sorted(links.items()):
        status = "allocated" if slot["active"] else "proposed"
        standing = slot["active"] or slot["proposed"]
        rows.append({
            "id": f"CMP:{rid}:{cid}", "requirement_id": rid, "control_ref": cid, "framework": slot["framework"],
            "control_version": slot["control_version"], "status": status, "assertion_level": ASSERTION[status],
            "basis": BASIS, "decision_ids": sorted(standing),
            "via_assets": sorted({a for assets in standing.values() for a in assets}),
        })
    return rows
