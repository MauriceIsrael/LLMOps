"""The cascade engine: an asserted decision opens more precise subjects (K20, ADR-KH-01 A10).

Interactive forward chaining, **deterministic and without a language model**: the facts in force of the whole engagement (K18:
asserted decisions only) are read against the question triggers of the knowledge snapshot the engagement is pinned to (K19).
A rule that holds opens a subject; a subject is a **question, not an assertion**: nobody validates it, and the engine **never
derives a decision**: only people decide.

* **Provenance.** A derived subject keeps ``{trigger_id, trigger_version, kb_snapshot, facts}``, its parents (subject and
  decision) and the suggested role. Its ``origin`` is ``derived``: no route takes it from a caller.
* **Idempotence.** A rule opens at most one subject per engagement (key ``trigger_id`` + engagement): replaying an assertion
  or an import creates nothing more. ``run`` is a function of the state, not of the events: any number of runs gives the same.
* **Truth maintenance.** When the condition of a rule stops holding (decision superseded or withdrawn), its subject becomes
  ``contested`` with the cause; it is **never deleted**. If the condition holds again the mark is lifted.
* **Pinned base.** The snapshot is fixed at the first derivation and moved only by an admin (``PUT …/kb-pin``): the same state
  and the same pinned base always give the same subjects.

A key asserted with different values by two decisions in force is **not usable**: a condition on it is false (nothing picks a
winner). A mandatory rule (regulatory control) opens a blocking question that only a decider closes, with a justification.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pipelines import triggers
from pipelines.engagement import facts as fact_module
from pipelines.knowledge_ref import ResolutionError, load_snapshot

SOUND = "sound"
CONTESTED = "contested"  # exposed as ``foundation_contested``
FOUNDATION_STATUS = {SOUND: "sound", CONTESTED: "foundation_contested"}


def _slug(trigger_id: str) -> str:
    return trigger_id[len("TRG-"):] if trigger_id.startswith("TRG-") else trigger_id


def pinned_snapshot(access: Any, engagement: str, snapshots_dir: Path, by: str, create: bool) -> tuple[dict[str, Any] | None, str | None]:
    """``(snapshot, None)`` or ``(None, reason)``: the pinned snapshot, pinning the latest one on first use when ``create``."""
    pin = access.get_pin(engagement)
    try:
        if pin is None:
            if not create:
                return None, "not_pinned"
            snapshot = load_snapshot(snapshots_dir)
            access.set_pin(engagement, snapshot["snapshot_id"], snapshot["payload_sha256"], by, replace=False)
            return snapshot, None
        try:
            snapshot = load_snapshot(snapshots_dir, pin["snapshot_id"])
        except ResolutionError as err:
            if err.reason != "snapshot_unavailable":
                raise
            snapshot = load_snapshot(snapshots_dir)  # the latest one may be the pinned one
            if snapshot["snapshot_id"] != pin["snapshot_id"]:
                return None, "pinned_snapshot_unavailable"
    except ResolutionError as err:
        return None, err.reason
    if snapshot["payload_sha256"] != pin["checksum"]:
        return None, "pinned_snapshot_changed"
    return snapshot, None


def rules_of(snapshot: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """The reference rules of a knowledge snapshot (K19), by id."""
    return {r["trigger_id"]: r for r in ((snapshot or {}).get("question_triggers") or {}).get("items", [])}


def local_rule(adjustment: dict[str, Any]) -> dict[str, Any]:
    """An engagement's own rule (K21) in the shape of a reference rule: no ``knowledge_ref``, ``scope`` ``local``."""
    doc = adjustment["payload"]
    return {**doc, "trigger_id": adjustment["trigger_id"], "knowledge_ref": None, "scope": "local"}


def effective_rules(snapshot: dict[str, Any] | None, adjustments: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], set[str]]:
    """``(rules, disabled)``: the rules of the pinned base, minus the deactivated ones, plus the asserted local rules (K21)."""
    disabled = {a["trigger_id"] for a in adjustments if a["kind"] == "disable" and a["status"] == "active"}
    rules = {tid: {**r, "scope": "reference"} for tid, r in rules_of(snapshot).items() if tid not in disabled}
    for a in adjustments:
        if a["kind"] == "local" and a["status"] == "active":
            rules[a["trigger_id"]] = local_rule(a)
    return rules, disabled


def _fact_map(items: list[dict[str, Any]], contradictions: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """``{key: value}`` of the facts usable by a rule, and ``{key: fact}`` for their provenance."""
    unusable = {c["key"] for c in contradictions}
    values: dict[str, Any] = {}
    origin: dict[str, dict[str, Any]] = {}
    for f in items:
        if f["key"] not in unusable:
            values[f["key"]] = f["value"]
            origin[f["key"]] = f
    return values, origin


class Cascade:
    """Evaluates the rules of the pinned snapshot against one engagement and keeps its derived subjects true."""

    def __init__(self, repo: Any, access: Any, engagement: str, snapshots_dir: Path, actor: str) -> None:
        self.repo = repo
        self.access = access
        self.engagement = engagement
        self.snapshots_dir = snapshots_dir
        self.actor = actor

    def run(self) -> dict[str, Any]:
        """Bring the derived subjects in line with the facts in force. Never raises for a base problem: reports ``skipped``."""
        from pipelines.engagement.write import _derived_id  # noqa: PLC0415

        snapshot, reason = pinned_snapshot(self.access, self.engagement, self.snapshots_dir, self.actor, create=True)
        if snapshot is None:
            return {"skipped": reason, "created": [], "contested": [], "restored": []}
        decisions = self.repo.list_decisions(self.engagement)
        try:
            in_force = fact_module.pinned(decisions, snapshot)
        except fact_module.FactError as err:
            return {"skipped": err.code.lower(), "created": [], "contested": [], "restored": []}
        values, origin = _fact_map(in_force["items"], in_force["contradictions"])
        rules, disabled = effective_rules(snapshot, self.repo.list_adjustments(self.engagement))
        existing = {d["trigger_id"]: d for d in self.repo.list_derived_subjects(self.engagement)}
        names = set(self.repo.subject_levels(self.engagement))
        report: dict[str, Any] = {"pinned": snapshot["snapshot_id"], "created": [], "contested": [], "restored": []}

        for trigger_id in sorted(set(rules) | set(existing)):
            rule = rules.get(trigger_id)
            held = existing.get(trigger_id)
            if rule is None:  # deactivated, withdrawn, or no longer in the pinned base: its subject stays, contested
                if held and held["foundation"] == SOUND:
                    self._contest(held, {"rule_disabled": True} if trigger_id in disabled else {"rule_missing": True}, report)
                continue
            holds = triggers.matches(rule, values)
            if held is None:
                if holds:
                    self._create(rule, values, origin, snapshot, names, report, _derived_id)
            elif holds and held["foundation"] == CONTESTED:
                derivation = {**held["derivation"], "cause": None}
                self.repo.set_foundation(self.engagement, held["name"], SOUND, derivation)
                report["restored"].append(held["name"])
            elif not holds and held["foundation"] == SOUND:
                self._contest(held, {"unsatisfied": triggers.unsatisfied(rule, values, {c["key"] for c in in_force["contradictions"]})}, report)
        if report["created"] or report["contested"] or report["restored"]:
            self.access.audit(self.engagement, self.actor, "cascade", "allowed", {
                "kb_snapshot": snapshot["snapshot_id"], "created": len(report["created"]),
                "contested": len(report["contested"]), "restored": len(report["restored"])})
        return report

    # --- steps ----------------------------------------------------------------------------------------------------

    def _create(self, rule, values, origin, snapshot, names, report, derived_id) -> None:
        used = [{"key": c["key"], "value": values[c["key"]], "decision": origin[c["key"]]["decision"]} for c in rule["when"]]
        used = sorted({(f["key"], repr(f["value"]), f["decision"]): f for f in used}.values(), key=lambda f: (f["key"], f["decision"]))
        parents = sorted({(origin[f["key"]]["subject"], f["decision"]) for f in used})
        name = _slug(rule["trigger_id"])
        if name in names:  # a person already owns that name: never take it over
            name += "-derived"
        question_id = None
        derivation = {
            "trigger_id": rule["trigger_id"], "trigger_version": rule["version"], "knowledge_ref": rule["knowledge_ref"],
            "scope": rule.get("scope", "reference"),
            "kb_snapshot": {"snapshot_id": snapshot["snapshot_id"], "checksum": snapshot["payload_sha256"]},
            "facts": used, "parents": [{"subject": s, "decision": d} for s, d in parents],
            "question": rule["question"], "rationale": rule["rationale"], "suggested_role": rule["suggested_role"],
            "mandatory": rule["mandatory"], "cause": None, "question_id": None,
        }
        if rule["mandatory"]:
            question_id = derived_id("Q", self.engagement, "cascade", rule["trigger_id"])
            derivation["question_id"] = question_id
        self.repo.save_derived_subject(self.engagement, name, rule["question"]["en"], rule["initial_level"], rule["trigger_id"], derivation)
        if question_id:
            self.repo.save_derived_question({
                "id": question_id, "engagement": self.engagement, "gap_type": "G2_unanswered_blocking", "section": "cascade",
                "question": rule["question"]["en"], "why_it_matters": rule["rationale"]["en"], "expected_shape": "free_text",
                "routed_to": rule["suggested_role"], "status": "open", "subject": name}, rule["trigger_id"], True)
        names.add(name)
        report["created"].append(name)

    def _contest(self, held: dict[str, Any], cause: dict[str, Any], report: dict[str, Any]) -> None:
        self.repo.set_foundation(self.engagement, held["name"], CONTESTED, {**held["derivation"], "cause": cause})
        report["contested"].append(held["name"])


# --- reading ----------------------------------------------------------------------------------------------------------


def lineage_items(derived: list[dict[str, Any]], snapshot: dict[str, Any] | None,
                  adjustments: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """The derived subjects as the snapshot and the lineage route carry them: no date, a function of the state.

    ``resolved``: a reference rule resolves when the pinned base holds it at that version (a deactivated rule still does); a
    local rule resolves while the engagement records it (K21), whatever its status.
    """
    rules = rules_of(snapshot)
    local = {a["trigger_id"]: a for a in adjustments or [] if a["kind"] == "local"}
    items = []
    for d in sorted(derived, key=lambda d: d["trigger_id"]):
        v = d["derivation"]
        scope = v.get("scope", "reference")
        rule = local[d["trigger_id"]]["payload"] if scope == "local" and d["trigger_id"] in local else rules.get(d["trigger_id"])
        items.append({
            "subject": d["name"], "trigger_id": d["trigger_id"], "trigger_version": v.get("trigger_version"), "scope": scope,
            "knowledge_ref": v.get("knowledge_ref"), "resolved": bool(rule and rule["version"] == v.get("trigger_version")),
            "kb_snapshot": v.get("kb_snapshot"), "facts": v.get("facts", []), "parents": v.get("parents", []),
            "foundation": FOUNDATION_STATUS.get(d["foundation"], d["foundation"]), "cause": v.get("cause"),
            "mandatory": bool(v.get("mandatory")), "suggested_role": v.get("suggested_role", ""),
            "question_id": v.get("question_id"), "question": v.get("question"), "rationale": v.get("rationale"),
        })
    return items


def lineage_tree(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derivation tree: parent subject → decision → derived subjects (and theirs, when they carry decisions in turn)."""
    derived_names = {i["subject"] for i in items}

    def children(subject: str, seen: frozenset[str]) -> list[dict[str, Any]]:
        by_decision: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            for p in item["parents"]:
                if p["subject"] == subject and item["subject"] not in seen:
                    by_decision.setdefault(p["decision"], []).append(item)
        return [{"decision": decision, "derived": [
            {"subject": i["subject"], "rule": i["trigger_id"], "version": i["trigger_version"], "foundation": i["foundation"],
             "facts": i["facts"], "children": children(i["subject"], seen | {subject, i["subject"]})}
            for i in sorted(group, key=lambda i: i["trigger_id"])]} for decision, group in sorted(by_decision.items())]

    roots = sorted({p["subject"] for i in items for p in i["parents"]} - derived_names)
    return [{"subject": r, "decisions": children(r, frozenset({r}))} for r in roots]
