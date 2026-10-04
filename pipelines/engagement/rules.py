"""What one engagement changes in the reference trigger rules (K21, ADR-KH-01 A10).

The reference rules (K19) live in the knowledge base and say nothing of a programme. An engagement still has its own: a
reference rule may not apply to it, and a rule specific to the programme may be missing. These adjustments are **engaged
elements**: they belong to the engagement base, never to the knowledge base.

* **Deactivating** a reference rule is the gesture of a ``decider``, with a **justification that is mandatory** and traced in
  the audit, ``mandatory`` rules included. The subjects the rule already opened stay, marked ``foundation_contested`` (K20).
* **A local rule** has the schema and the checks of a reference rule (K19, against the vocabulary of K18). A ``contributor``
  proposes it; it applies only once a ``decider`` **other than its author** has asserted it.
* The engine reads ``rules of the pinned base - deactivations + asserted local rules``.

Capitalising a useful local rule toward the reference base goes through the proposals channel (K7, K13): not in this lot.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipelines import triggers
from pipelines.engagement import facts as fact_module
from pipelines.engagement.cascade import effective_rules, pinned_snapshot, rules_of
from pipelines.engagement.write import WriteError, _text, require_distinct

LOCAL_FIELDS = ("trigger_id", "version", "asset", "when", "question", "rationale", "initial_level", "suggested_role", "mandatory")


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S")


def carrier_index(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The elements of the pinned base that may carry a rule, as the snapshot lists them."""
    out = {a["id"]: {"type": a.get("type"), "severity": None} for a in snapshot.get("assets", [])}
    out.update({c["id"]: {"type": "control", "severity": c.get("severity")} for c in snapshot.get("controls", [])})
    return out


class RuleAdjuster:
    """Writes the rule adjustments of one engagement on behalf of one member (``actor`` is their handle)."""

    def __init__(self, repo: Any, access: Any, engagement: str, actor: str, snapshots_dir: Path, cascade: Any = None) -> None:
        self.repo = repo
        self.access = access
        self.engagement = engagement
        self.actor = actor
        self.snapshots_dir = snapshots_dir
        self.cascade = cascade

    def _snapshot(self) -> dict[str, Any]:
        snapshot, reason = pinned_snapshot(self.access, self.engagement, self.snapshots_dir, self.actor, create=True)
        if snapshot is None:
            raise WriteError(409, "kb_snapshot_unavailable", f"the knowledge snapshot the engagement reads its rules from is unusable ({reason})")
        return snapshot

    def _done(self, out: dict[str, Any]) -> dict[str, Any]:
        out["cascade"] = self.cascade() if self.cascade else None  # K20: the rules in force changed
        return out

    # --- deactivating a reference rule -----------------------------------------------------------------------------

    def disable(self, trigger_id: str, body: dict[str, Any]) -> dict[str, Any]:
        rule = rules_of(self._snapshot()).get(trigger_id)
        if rule is None:
            raise WriteError(404, "unknown_rule", f"'{trigger_id}' is not a reference rule of the pinned knowledge snapshot")
        justification = _text(body, "justification", limit=1000)  # mandatory, rules marked mandatory included
        record_id = f"ADJ-disable-{trigger_id}"
        current = self.repo.get_adjustment(record_id)
        if current and current["status"] == "active":
            raise WriteError(409, "already_disabled", f"'{trigger_id}' is already deactivated for this engagement")
        self.repo.save_adjustment({
            "id": record_id, "engagement": self.engagement, "kind": "disable", "trigger_id": trigger_id, "status": "active",
            "payload": {"mandatory": rule["mandatory"], "version": rule["version"]}, "justification": justification,
            "author": self.actor, "validated_by": "", "validated_at": ""})
        self.access.audit(self.engagement, self.actor, "rule_disable", "allowed", {
            "trigger_id": trigger_id, "mandatory": rule["mandatory"], "justification": justification})
        return self._done({"adjustment": self._public(self.repo.get_adjustment(record_id))})

    def enable(self, trigger_id: str) -> dict[str, Any]:
        record_id = f"ADJ-disable-{trigger_id}"
        current = self.repo.get_adjustment(record_id)
        if not current or current["status"] != "active":
            raise WriteError(409, "not_disabled", f"'{trigger_id}' is not deactivated for this engagement")
        self.repo.set_adjustment_status(record_id, "withdrawn")
        self.access.audit(self.engagement, self.actor, "rule_enable", "allowed", {"trigger_id": trigger_id})
        return self._done({"adjustment": self._public(self.repo.get_adjustment(record_id))})

    # --- local rules -----------------------------------------------------------------------------------------------

    def propose_local(self, body: dict[str, Any]) -> dict[str, Any]:
        snapshot = self._snapshot()
        vocabulary = fact_module.from_snapshot(snapshot)
        if vocabulary is None:
            raise WriteError(409, "kb_snapshot_unavailable", "the pinned knowledge snapshot has no facts vocabulary")
        doc = {k: body[k] for k in LOCAL_FIELDS if k in body}
        doc.setdefault("version", 1)
        doc.setdefault("asset", None)
        doc.setdefault("mandatory", False)
        extra = sorted(set(body) - set(LOCAL_FIELDS))
        problems = [{"trigger": str(doc.get("trigger_id")), "path": k, "code": "UNKNOWN_FIELD", "reason": f"'{k}' is not a field of a rule"} for k in extra]
        problems += triggers.validate_rule(doc, str(doc.get("trigger_id")), vocabulary, carrier_index(snapshot), local=True)
        if problems:
            first = problems[0]
            raise WriteError(400, first["code"], first["reason"], first["path"], problems=problems)
        record_id = f"ADJ-local-{doc['trigger_id']}"
        current = self.repo.get_adjustment(record_id)
        if current and current["status"] != "withdrawn":
            raise WriteError(409, "rule_exists", f"'{doc['trigger_id']}' already exists ({current['status']}): withdraw it to propose another")
        self.repo.save_adjustment({
            "id": record_id, "engagement": self.engagement, "kind": "local", "trigger_id": doc["trigger_id"], "status": "proposed",
            "payload": doc, "justification": "", "author": self.actor, "validated_by": "", "validated_at": ""})
        return {"adjustment": self._public(self.repo.get_adjustment(record_id))}

    def assert_local(self, trigger_id: str) -> dict[str, Any]:
        record = self._local(trigger_id)
        if record["status"] != "proposed":
            raise WriteError(409, "not_proposed", f"{trigger_id} is '{record['status']}': only a proposed rule can be asserted")
        require_distinct(self.actor, [record["author"]], trigger_id)
        self.repo.set_adjustment_status(record["id"], "active", self.actor, _now())
        self.access.audit(self.engagement, self.actor, "rule_assert", "allowed", {"trigger_id": trigger_id})
        return self._done({"adjustment": self._public(self.repo.get_adjustment(record["id"]))})

    def withdraw_local(self, trigger_id: str, is_decider: bool) -> dict[str, Any]:
        record = self._local(trigger_id)
        if record["status"] not in ("proposed", "active"):
            raise WriteError(409, "not_withdrawable", f"{trigger_id} is '{record['status']}'")
        if record["author"] != self.actor and not is_decider:
            raise WriteError(403, "not_author", "only the author or a decider withdraws a rule")
        self.repo.set_adjustment_status(record["id"], "withdrawn", record["validated_by"], record["validated_at"])
        self.access.audit(self.engagement, self.actor, "rule_withdraw", "allowed", {"trigger_id": trigger_id})
        return self._done({"adjustment": self._public(self.repo.get_adjustment(record["id"]))})

    def _local(self, trigger_id: str) -> dict[str, Any]:
        record = self.repo.get_adjustment(f"ADJ-local-{trigger_id}")
        if not record or record["engagement"] != self.engagement:
            raise WriteError(404, "unknown_rule", f"local rule '{trigger_id}' not found")
        return record

    # --- reading ---------------------------------------------------------------------------------------------------

    @staticmethod
    def _public(a: dict[str, Any] | None) -> dict[str, Any]:
        a = a or {}
        out = {"trigger_id": a.get("trigger_id"), "kind": a.get("kind"), "status": a.get("status"), "author": a.get("author"),
               "justification": a.get("justification") or "", "validated_by": a.get("validated_by") or "",
               "validated_at": a.get("validated_at") or ""}
        if a.get("kind") == "local":
            out["rule"] = a.get("payload")
        return out

    def overview(self) -> dict[str, Any]:
        snapshot = self._snapshot()
        adjustments = self.repo.list_adjustments(self.engagement)
        _, disabled = effective_rules(snapshot, adjustments)
        why = {a["trigger_id"]: a["justification"] for a in adjustments if a["kind"] == "disable" and a["status"] == "active"}
        reference = [{"trigger_id": tid, "version": r["version"], "mandatory": r["mandatory"], "carrier": r["carrier"],
                      "disabled": tid in disabled, "justification": why.get(tid, "")} for tid, r in sorted(rules_of(snapshot).items())]
        return {"kb_snapshot": {"snapshot_id": snapshot["snapshot_id"], "checksum": snapshot["payload_sha256"]},
                "reference": reference, "local": [self._public(a) for a in adjustments if a["kind"] == "local"]}
