"""Importing an engagement into the Hub (K12, ADR-KH-01 A10-f), the safe way.

Archinex used to hold the engagement; the Hub is now the system of record. The import is performed by the client that knows its
own data (Archinex) through one route; the Hub makes it **safe and rehearsable**:

* **dry run**: nothing is written; the report lists what would be accepted, left unchanged, adjusted and rejected, each rejection
  with its path and reason. By default a batch with a single rejection is **not applied** at all (``allow_partial`` lifts that).
* **provenance, not rewriting**: the historical author, creation date and validator are kept (the author and validator must be
  members of the engagement, referred to by handle) and every imported item is marked ``imported_from`` the batch.
* **nothing is asserted in the batch's own name**: an item is *active* only when the source names a validator who is a member
  with the decider or admin role, is **not the author**, and gives the date; otherwise it is imported *proposed* and reported
  (``no_validator``). A self-validation is rejected for that item.
* **nothing is repaired in silence**: unknown handles, confidences out of vocabulary, e-mail addresses in a text, requirements
  rewritten with another text, a second asserted decision for a subject: rejected with a code. A subject whose requested maturity
  its decisions do not support is imported at ``L2_decomposed`` and reported as ``adjusted``.
* **idempotent**: every item has a ``key``; an item whose identifier exists is left unchanged, never overwritten.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pipelines.engagement.write import (
    KEY,
    WriteError,
    _derived_id,
    _text,
    prepare_decision,
    prepare_statement,
)
from tools.elicitation.config import SUBJECT_LEVELS

MAX_ITEMS = 2000
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+")
DECIDING = ("decider", "admin")
STATEMENT_STATUSES = ("active", "proposed", "withdrawn", "superseded")
DECISION_STATUSES = ("active", "proposed", "withdrawn", "superseded")
QUESTION_STATUSES = ("open", "sent", "answered", "declined")
CAP_LEVEL = "L2_decomposed"


@dataclass
class Plan:
    accepted: list[dict[str, Any]] = field(default_factory=list)
    unchanged: list[dict[str, Any]] = field(default_factory=list)
    adjusted: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    operations: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    maturity: dict[str, str] = field(default_factory=dict)

    def reject(self, ref: str, kind: str, code: str, reason: str, path: str = "") -> None:
        self.rejected.append({"ref": ref, "kind": kind, "code": code, "path": path, "reason": reason})


def _iso(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise WriteError(400, "invalid_argument", f"'{field_name}' must be an ISO 8601 date-time", field_name)
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as err:
        raise WriteError(400, "invalid_argument", f"'{field_name}' must be an ISO 8601 date-time", field_name) from err
    return value


def _strings(node: Any):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _strings(v)


class Importer:
    def __init__(self, repo: Any, engagement: str, members: dict[str, str], batch_id: str) -> None:
        self.repo = repo
        self.engagement = engagement
        self.members = members  # handle -> role
        self.batch_id = batch_id

    # --- planning (no write) --------------------------------------------------------------------------------------

    def plan(self, body: dict[str, Any]) -> Plan:
        plan = Plan()
        collections = {k: body.get(k) or [] for k in ("subjects", "requirements", "statements", "decisions", "questions")}
        for name, items in collections.items():
            if not isinstance(items, list):
                raise WriteError(400, "invalid_argument", f"'{name}' must be a list", name)
        if sum(len(v) for v in collections.values()) > MAX_ITEMS:
            raise WriteError(400, "invalid_argument", f"a batch holds at most {MAX_ITEMS} items", "batch")
        existing_subjects = dict(self.repo.subject_levels(self.engagement))
        batch_subjects: dict[str, str] = {}
        self._subjects(plan, collections["subjects"], existing_subjects, batch_subjects)
        known_subjects = set(existing_subjects) | set(batch_subjects)
        self._requirements(plan, collections["requirements"])
        self._statements(plan, collections["statements"], known_subjects)
        decisions = self._decisions(plan, collections["decisions"], known_subjects)
        self._questions(plan, collections["questions"], known_subjects)
        self._maturity(plan, batch_subjects, decisions)
        return plan

    def _subjects(self, plan: Plan, items: list[Any], existing: dict[str, str], batch: dict[str, str]) -> None:
        for i, item in enumerate(items):
            ref = str(item.get("name", f"subjects[{i}]")) if isinstance(item, dict) else f"subjects[{i}]"
            try:
                if not isinstance(item, dict):
                    raise WriteError(400, "invalid_argument", "each subject is an object", f"subjects[{i}]")
                name = _text(item, "name", limit=120)
                definition = _text(item, "definition", required=False)
                level = item.get("maturity") or SUBJECT_LEVELS[0]
                if level not in SUBJECT_LEVELS:
                    raise WriteError(400, "invalid_argument", f"'maturity' must be one of {SUBJECT_LEVELS}", "maturity")
                self._no_email(item)
            except WriteError as err:
                plan.reject(ref, "subject", err.code, err.reason, f"subjects[{i}].{err.argument or ''}".rstrip("."))
                continue
            if name in existing:
                plan.unchanged.append({"ref": name, "kind": "subject"})
            else:
                batch[name] = level
                plan.operations.append(("subject", {"name": name, "definition": definition}))
                plan.accepted.append({"ref": name, "kind": "subject", "status": level})

    def _requirements(self, plan: Plan, items: list[Any]) -> None:
        existing = {r["id"]: r for r in self.repo.get_requirements(self.engagement)}
        for i, item in enumerate(items):
            ref = str(item.get("id", f"requirements[{i}]")) if isinstance(item, dict) else f"requirements[{i}]"
            try:
                if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"] or not KEY.match(item["id"]):
                    raise WriteError(400, "invalid_argument", "each requirement needs an 'id' (letters, digits . _ : -)", "id")
                req = {"id": item["id"], "engagement": self.engagement, "text": _text(item, "text"),
                       "section": _text(item, "section", required=False, limit=200),
                       "category": _text(item, "category", required=False, default="general", limit=64),
                       "criticality": _text(item, "criticality", required=False, default="mandatory", limit=32), "status": "gap"}
                self._no_email(item)
            except WriteError as err:
                plan.reject(ref, "requirement", "invalid_argument", err.reason, f"requirements[{i}].{err.argument or ''}".rstrip("."))
                continue
            old = existing.get(req["id"])
            if old is None:
                plan.operations.append(("requirement", req))
                plan.accepted.append({"ref": req["id"], "kind": "requirement", "status": "gap"})
            elif old.get("text") == req["text"]:
                plan.unchanged.append({"ref": req["id"], "kind": "requirement"})
            else:
                plan.reject(req["id"], "requirement", "requirement_changed", "the requirement exists with another text: requirements are not rewritten", f"requirements[{i}].text")

    def _attribution(self, item: dict[str, Any], kind: str, i: int, ref: str, plan: Plan, statuses: tuple[str, ...]) -> dict[str, Any] | None:
        """Author, dates, validator and the resulting status of an imported statement or decision."""
        author = item.get("author")
        if not isinstance(author, str) or author not in self.members:
            plan.reject(ref, kind, "unknown_author", "the author must be a member of the engagement, by handle", f"{kind}s[{i}].author")
            return None
        created_at = _iso(item["created_at"], "created_at") if item.get("created_at") else datetime.now(UTC).isoformat()
        requested = item.get("status")
        if requested is not None and requested not in statuses:
            plan.reject(ref, kind, "invalid_argument", f"'status' must be one of {list(statuses)}", f"{kind}s[{i}].status")
            return None
        validator, validated_at = item.get("validated_by") or "", item.get("validated_at") or ""
        status = requested or "proposed"
        if validator:
            if validator == author:
                plan.reject(ref, kind, "self_validation", "the validator is the author: another decider must assert it", f"{kind}s[{i}].validated_by")
                return None
            if self.members.get(validator) not in DECIDING:
                plan.reject(ref, kind, "validator_not_a_decider", "the validator must be a member with the decider or admin role", f"{kind}s[{i}].validated_by")
                return None
            if not validated_at:
                plan.reject(ref, kind, "validated_at_required", "a validator needs the date of the assertion", f"{kind}s[{i}].validated_at")
                return None
            validated_at = _iso(validated_at, "validated_at")
            if requested in (None, "active"):
                status = "active"
            elif requested == "proposed":
                plan.reject(ref, kind, "status_conflict", "a proposed item cannot name a validator", f"{kind}s[{i}].status")
                return None
        else:
            validated_at = ""
            if requested == "active":
                plan.adjusted.append({"ref": ref, "kind": kind, "code": "no_validator", "reason": "asserted in the source without a validator: imported as proposed"})
                status = "proposed"
        return {"author": author, "created_at": created_at, "status": status, "validated_by": validator, "validated_at": validated_at}

    def _statements(self, plan: Plan, items: list[Any], subjects: set[str]) -> None:
        for i, item in enumerate(items):
            ref = str(item.get("key", f"statements[{i}]")) if isinstance(item, dict) else f"statements[{i}]"
            try:
                if not isinstance(item, dict) or not isinstance(item.get("key"), str) or not KEY.match(item["key"]):
                    raise WriteError(400, "invalid_argument", "each statement needs a 'key' (idempotency)", "key")
                fields = prepare_statement(item)
                self._no_email(item)
                if fields["subject"] not in subjects:
                    raise WriteError(400, "unknown_subject", f"unknown subject '{fields['subject']}'", "subject")
                attribution = self._attribution(item, "statement", i, ref, plan, STATEMENT_STATUSES)
            except WriteError as err:
                plan.reject(ref, "statement", err.code, err.reason,
                            f"statements[{i}].{err.argument or ''}".rstrip("."))
                continue
            if attribution is None:
                continue
            sid = _derived_id("S", self.engagement, "statement", item["key"])
            if self.repo.get_statement_record(sid):
                plan.unchanged.append({"ref": ref, "kind": "statement", "id": sid})
                continue
            record = {**fields, **attribution, "id": sid, "engagement": self.engagement, "imported_from": self.batch_id}
            plan.operations.append(("statement", record))
            plan.accepted.append({"ref": ref, "kind": "statement", "id": sid, "status": record["status"]})

    def _decisions(self, plan: Plan, items: list[Any], subjects: set[str]) -> list[dict[str, Any]]:
        planned: list[dict[str, Any]] = []
        keys: dict[str, str] = {}
        for i, item in enumerate(items):
            ref = str(item.get("key", f"decisions[{i}]")) if isinstance(item, dict) else f"decisions[{i}]"
            try:
                if not isinstance(item, dict) or not isinstance(item.get("key"), str) or not KEY.match(item["key"]):
                    raise WriteError(400, "invalid_argument", "each decision needs a 'key' (idempotency)", "key")
                fields = prepare_decision(item)
                self._no_email(item)
                if fields["subject"] not in subjects:
                    raise WriteError(400, "unknown_subject", f"unknown subject '{fields['subject']}'", "subject")
                attribution = self._attribution(item, "decision", i, ref, plan, DECISION_STATUSES)
            except WriteError as err:
                plan.reject(ref, "decision", err.code, err.reason, f"decisions[{i}].{err.argument or ''}".rstrip("."))
                continue
            if attribution is None:
                continue
            did = _derived_id("D", self.engagement, "decision", item["key"])
            keys[item["key"]] = did
            if self.repo.get_decision_record(did):
                plan.unchanged.append({"ref": ref, "kind": "decision", "id": did})
                continue
            planned.append({**fields, **attribution, "id": did, "engagement": self.engagement, "imported_from": self.batch_id,
                            "_ref": ref, "_index": i, "_supersedes_key": item.get("supersedes_key") or ""})
        existing = {d["id"]: d for d in self.repo.list_decisions(self.engagement)}
        by_id = {**existing, **{d["id"]: d for d in planned}}
        for d in planned:
            key = d.pop("_supersedes_key")
            d["supersedes"] = keys.get(key, key) if key else ""
        # one asserted and at most one pending decision per subject, counting what the engagement already holds
        for d in list(planned):
            same = [x for x in by_id.values() if x["subject"] == d["subject"] and x["id"] != d["id"]]
            clash = None
            if d["status"] == "active" and any(x["status"] == "active" and x["id"] != d["supersedes"] for x in same):
                clash = ("decision_exists", f"'{d['subject']}' already has an asserted decision")
            elif d["status"] == "proposed" and any(x["status"] == "proposed" for x in same):
                clash = ("decision_pending", f"'{d['subject']}' already has a proposed decision")
            elif d["supersedes"]:
                target = by_id.get(d["supersedes"])
                if target is None or target["subject"] != d["subject"]:
                    clash = ("invalid_argument", "'supersedes_key' must name another decision of the same subject")
                elif d["status"] == "active" and target["status"] != "superseded":
                    clash = ("supersession_inconsistent", "the superseded decision must itself be imported as 'superseded'")
            if clash:
                plan.reject(d["_ref"], "decision", clash[0], clash[1], f"decisions[{d['_index']}]")
                planned.remove(d)
                by_id.pop(d["id"], None)
        for d in planned:
            ref = d.pop("_ref")
            d.pop("_index")
            plan.operations.append(("decision", d))
            plan.accepted.append({"ref": ref, "kind": "decision", "id": d["id"], "status": d["status"]})
        return [d for d in by_id.values()]

    def _questions(self, plan: Plan, items: list[Any], subjects: set[str]) -> None:
        for i, item in enumerate(items):
            ref = str(item.get("key", f"questions[{i}]")) if isinstance(item, dict) else f"questions[{i}]"
            try:
                if not isinstance(item, dict) or not isinstance(item.get("key"), str) or not KEY.match(item["key"]):
                    raise WriteError(400, "invalid_argument", "each question needs a 'key' (idempotency)", "key")
                status = item.get("status") or "open"
                if status not in QUESTION_STATUSES:
                    raise WriteError(400, "invalid_argument", f"'status' must be one of {list(QUESTION_STATUSES)}", "status")
                question = {"engagement": self.engagement, "question": _text(item, "question"),
                            "why_it_matters": _text(item, "why_it_matters", required=False),
                            "section": _text(item, "section", required=False, default="general", limit=120),
                            "gap_type": _text(item, "gap_type", required=False, default="G2_unanswered_blocking", limit=48),
                            "expected_shape": "free_text", "routed_to": _text(item, "routed_to", required=False, default="architect", limit=64),
                            "status": status}
                if item.get("subject"):
                    question["subject"] = _text(item, "subject", limit=120)
                    if question["subject"] not in subjects:
                        raise WriteError(400, "unknown_subject", f"unknown subject '{question['subject']}'", "subject")
                self._no_email(item)
            except WriteError as err:
                plan.reject(ref, "question", err.code, err.reason, f"questions[{i}].{err.argument or ''}".rstrip("."))
                continue
            qid = _derived_id("Q", self.engagement, "question", item["key"])
            if self.repo.get_question(qid):
                plan.unchanged.append({"ref": ref, "kind": "question", "id": qid})
                continue
            plan.operations.append(("question", {**question, "id": qid}))
            plan.accepted.append({"ref": ref, "kind": "question", "id": qid, "status": status})

    def _maturity(self, plan: Plan, batch_subjects: dict[str, str], decisions: list[dict[str, Any]]) -> None:
        asserted = {d["subject"] for d in decisions if d["status"] == "active"}
        for name, level in batch_subjects.items():
            if level in ("L3_decided", "L4_specified") and name not in asserted:
                plan.adjusted.append({"ref": name, "kind": "subject", "code": "maturity_capped",
                                      "reason": f"{level} needs an asserted decision: imported at {CAP_LEVEL}"})
                level = CAP_LEVEL
            plan.maturity[name] = level

    @staticmethod
    def _no_email(item: dict[str, Any]) -> None:
        if any(EMAIL.search(text) for text in _strings(item)):
            raise WriteError(400, "email", "an e-mail address cannot enter the Hub: handles only")

    # --- applying -------------------------------------------------------------------------------------------------

    def apply(self, plan: Plan) -> dict[str, Any]:
        """Write the planned operations. Returns the conflicts that asserted statements opened."""
        for kind, op in plan.operations:
            if kind == "subject":
                self.repo.save_subject(op["name"], engagement=self.engagement, definition=op["definition"], origin="imported")
            elif kind == "requirement":
                self.repo.save_requirement(op)
            elif kind == "statement":
                self.repo.save_statement(op)
            elif kind == "decision":
                self.repo.save_decision(op)
            elif kind == "question":
                self.repo.save_question(op)
        active = [op["id"] for kind, op in plan.operations if kind == "statement" and op["status"] == "active"]
        conflicts = self.repo.run_checks(self.engagement, active) if active else []
        open_ids = {sid for c in conflicts for sid in c.get("statement_ids", [])}
        subjects_in_conflict = {op["subject"] for kind, op in plan.operations if kind == "statement" and op["id"] in open_ids}
        for name, level in plan.maturity.items():
            if level in ("L3_decided", "L4_specified") and name in subjects_in_conflict:
                plan.adjusted.append({"ref": name, "kind": "subject", "code": "maturity_capped",
                                      "reason": f"open conflict on '{name}': imported at {CAP_LEVEL}"})
                level = CAP_LEVEL
            if level != SUBJECT_LEVELS[0]:
                self.repo.advance_subject_level(name=name, level=level, engagement=self.engagement)
        return {"conflicts_opened": [c["id"] for c in conflicts]}
