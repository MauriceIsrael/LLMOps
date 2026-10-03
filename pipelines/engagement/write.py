"""Writing into a managed engagement (K15, ADR-KH-01 A10 and A11).

Archinex is the workbench where architects deliberate; the Hub records. Every write here follows the same rules:

* the **author is the member** behind the call (their handle), never a name sent in the body;
* a contribution is **proposed**: nothing becomes active without a person with the ``decide`` role who is **not its
  author**, and what a model derived (``origin: llm-derived``) is proposed like the rest, never asserted for it;
* a client may send an **idempotency key**: the same key gives the same identifier and an existing item is returned
  unchanged (``created: false``), so an import can be replayed without duplicating or resetting anything;
* nothing is guessed: an unknown value is refused with the field it concerns.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from tools.elicitation.config import CONFIDENCE_LEVELS, QUESTION_STATUSES, SUBJECT_LEVELS

ORIGINS = ("human", "llm-derived")
MAX_TEXT = 4000
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")
KEY = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
ASSERTED_LEVELS = ("L3_decided", "L4_specified")
REVERSIBILITY = ("reversible", "costly", "irreversible")


class WriteError(Exception):
    """A refused write. ``status`` is the HTTP status, ``code`` the machine-readable reason, ``argument`` the field."""

    def __init__(self, status: int, code: str, reason: str, argument: str | None = None, **detail: Any) -> None:
        self.status = status
        self.code = code
        self.reason = reason
        self.argument = argument
        self.detail = detail
        super().__init__(f"{code}: {reason}")

    def body(self) -> dict[str, Any]:
        if self.status == 400:
            return {"status": "invalid_argument", "argument": self.argument, "reason": self.reason, **self.detail}
        if self.status == 404:
            return {"status": "not_found", "error": self.code, "reason": self.reason, **self.detail}
        return {"status": "error", "error": self.code, "reason": self.reason, **self.detail}


def _text(body: dict[str, Any], field: str, *, required: bool = True, default: str = "", limit: int = MAX_TEXT) -> str:
    value = body.get(field, default)
    if value is None or value == "":
        value = default
    if not isinstance(value, str):
        raise WriteError(400, "invalid_argument", f"'{field}' must be a string", field)
    value = value.strip()
    if required and not value:
        raise WriteError(400, "invalid_argument", f"'{field}' is required", field)
    if len(value) > limit:
        raise WriteError(400, "invalid_argument", f"'{field}' is longer than {limit} characters", field)
    return value


def _key(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str) or not KEY.match(value):
        raise WriteError(400, "invalid_argument", "the idempotency key must be 1 to 128 of letters, digits . _ : -", "idempotency_key")
    return value


def _derived_id(prefix: str, engagement: str, kind: str, key: str) -> str:
    return f"{prefix}-" + hashlib.sha256(f"{engagement}|{kind}|{key}".encode()).hexdigest()[:12]


def _origin(body: dict[str, Any]) -> str:
    origin = body.get("origin", "human")
    if origin not in ORIGINS:
        raise WriteError(400, "invalid_argument", f"'origin' must be one of {list(ORIGINS)}", "origin")
    return origin


def _based_on(body: dict[str, Any]) -> list[dict[str, Any]]:
    raw = body.get("based_on") or []
    if not isinstance(raw, list) or not all(isinstance(i, dict) and isinstance(i.get("id"), str) and i["id"] for i in raw):
        raise WriteError(400, "invalid_argument", "'based_on' is a list of {id, resolved?}", "based_on")
    return [{"id": i["id"], "resolved": i.get("resolved")} for i in raw]


def require_distinct(actor: str, authors: list[str], what: str) -> None:
    """Nobody validates what they wrote (ADR-KH-01 A11-d)."""
    from mcp_server.core.auth import require_distinct_validator

    for author in authors:
        try:
            require_distinct_validator(actor, author)
        except PermissionError as err:
            raise WriteError(409, "self_validation", f"{actor} wrote {what}: another person with the decider role must assert it") from err


class EngagementWriter:
    """Writes into one engagement on behalf of one member (``actor`` is their handle)."""

    def __init__(self, repo: Any, engagement: str, actor: str) -> None:
        self.repo = repo
        self.engagement = engagement
        self.actor = actor

    # --- subjects -------------------------------------------------------------------------------------------------

    def add_subject(self, body: dict[str, Any]) -> dict[str, Any]:
        name = _text(body, "name", limit=120)
        definition = _text(body, "definition", required=False)
        created = name not in self.repo.subject_levels(self.engagement)
        self.repo.save_subject(name, engagement=self.engagement, definition=definition, origin="declared")
        return {"created": created, "subject": name}

    def advance_subject(self, name: str, body: dict[str, Any]) -> dict[str, Any]:
        level = _text(body, "level", limit=32)
        if level not in SUBJECT_LEVELS:
            raise WriteError(400, "invalid_argument", f"'level' must be one of {SUBJECT_LEVELS}", "level")
        if level in ASSERTED_LEVELS:
            # K16: a decided subject has an asserted decision (the statements alone do not decide)
            if not [d for d in self.repo.list_decisions(self.engagement) if d["subject"] == name and d["status"] == "active"]:
                raise WriteError(409, "no_asserted_decision", f"{level} needs an asserted decision about '{name}'")
            asserted = [s for s in self.repo.get_active_statements(self.engagement)
                        if s.get("subject") == name and s.get("status") == "active"]
            open_ids = {sid for c in self.repo.get_conflicts(self.engagement, "open")
                        for sid in (self.repo.get_conflict(c["id"]) or {}).get("statement_ids", [])}
            if open_ids & {s["id"] for s in asserted}:
                raise WriteError(409, "open_conflict", f"'{name}' has an open conflict: arbitrate it before {level}")
        self.repo.advance_subject_level(name=name, level=level, engagement=self.engagement)
        return {"subject": name, "level": level}

    # --- statements -----------------------------------------------------------------------------------------------

    def add_statement(self, body: dict[str, Any], key: str | None = None) -> dict[str, Any]:
        key = _key(key or body.get("idempotency_key"))
        subject = _text(body, "subject", limit=120)
        value = _text(body, "value")
        confidence = _text(body, "confidence", limit=32)
        if confidence not in CONFIDENCE_LEVELS:
            raise WriteError(400, "invalid_argument", f"'confidence' must be one of {sorted(CONFIDENCE_LEVELS)}", "confidence")
        based_on = _based_on(body)
        if confidence == "verified" and not based_on:
            raise WriteError(400, "invalid_argument", "'verified' needs evidence: list it in 'based_on'", "confidence")
        origin = _origin(body)
        statement: dict[str, Any] = {
            "engagement": self.engagement, "subject": subject, "value": value, "confidence": confidence,
            "section": _text(body, "section", required=False, default="general", limit=120),
            "predicate": _text(body, "predicate", required=False, default="has_property", limit=64),
            "role": _text(body, "role", required=False, default="architect", limit=64),
            "verbatim": _text(body, "verbatim", required=False) or value,
            "based_on": based_on, "origin": origin,
            "author": self.actor,  # the member behind the call, whatever the body says
            "status": "proposed",
        }
        if key:
            statement["id"] = _derived_id("S", self.engagement, "statement", key)
            if self.repo.get_statement_record(statement["id"]):
                return {"created": False, "statement": self._public(self.repo.get_statement_record(statement["id"]))}
        try:
            statement_id = self.repo.save_statement(statement)
        except ValueError as err:
            raise WriteError(400, "invalid_argument", str(err), "predicate") from err
        return {"created": True, "statement": self._public(self.repo.get_statement_record(statement_id))}

    def assert_statement(self, statement_id: str) -> dict[str, Any]:
        st = self._statement(statement_id)
        if st["status"] != "proposed":
            raise WriteError(409, "not_proposed", f"{statement_id} is '{st['status']}': only a proposed statement can be asserted")
        require_distinct(self.actor, [st.get("author") or ""], f"{statement_id}")
        self.repo.validate_statement(statement_id, self.actor)
        conflicts = self.repo.run_checks(self.engagement, [statement_id])
        return {"statement": self._public(self.repo.get_statement_record(statement_id)),
                "conflicts_opened": [c["id"] for c in conflicts]}

    def withdraw_statement(self, statement_id: str, is_decider: bool) -> dict[str, Any]:
        st = self._statement(statement_id)
        if st["status"] not in ("proposed", "active"):
            raise WriteError(409, "not_withdrawable", f"{statement_id} is '{st['status']}'")
        if st.get("author") != self.actor and not is_decider:
            raise WriteError(403, "not_author", "only the author or a decider withdraws a statement")
        self.repo.set_statement_status(statement_id, "withdrawn")
        return {"statement": self._public(self.repo.get_statement_record(statement_id))}

    # --- decisions (K16) ------------------------------------------------------------------------------------------

    def add_decision(self, body: dict[str, Any], key: str | None = None) -> dict[str, Any]:
        key = _key(key or body.get("idempotency_key"))
        subject = _text(body, "subject", limit=120)
        if subject not in self.repo.subject_levels(self.engagement):
            raise WriteError(400, "invalid_argument", f"unknown subject '{subject}': create it first", "subject")
        decision = _text(body, "decision")
        rationale = _text(body, "rationale")
        reversibility = _text(body, "reversibility", limit=16)
        if reversibility not in REVERSIBILITY:
            raise WriteError(400, "invalid_argument", f"'reversibility' must be one of {list(REVERSIBILITY)}", "reversibility")
        rejected = self._list_of(body, "rejected", {"option": True, "reason": True})
        violations = self._list_of(body, "accepted_violations", {"typed_id": True, "justification": True})
        consequences = body.get("consequences") or []
        if not isinstance(consequences, list) or not all(isinstance(c, str) and c.strip() for c in consequences):
            raise WriteError(400, "invalid_argument", "'consequences' is a list of non-empty strings", "consequences")
        kept = decision.strip().lower()
        if any(r["option"].strip().lower() == kept for r in rejected):
            raise WriteError(400, "invalid_argument", "the retained decision is also listed among the rejected options", "rejected")
        record: dict[str, Any] = {
            "engagement": self.engagement, "subject": subject, "decision": decision, "rationale": rationale,
            "rejected": rejected, "reversibility": reversibility, "consequences": [c.strip() for c in consequences],
            "accepted_violations": violations, "based_on": _based_on(body), "origin": _origin(body),
            "author": self.actor, "status": "proposed", "validated_by": "", "validated_at": "", "supersedes": "",
        }
        if key:
            record["id"] = _derived_id("D", self.engagement, "decision", key)
            if self.repo.get_decision_record(record["id"]):
                return {"created": False, "decision": self._public_decision(self.repo.get_decision_record(record["id"]))}
        existing = [d for d in self.repo.list_decisions(self.engagement) if d["subject"] == subject]
        superseded = body.get("supersedes") or ""
        if any(d["status"] == "proposed" for d in existing):
            raise WriteError(409, "decision_pending", f"'{subject}' already has a proposed decision: assert or withdraw it first")
        active = next((d for d in existing if d["status"] == "active"), None)
        if superseded and not (active and superseded == active["id"]):
            raise WriteError(400, "invalid_argument", f"'supersedes' must name the asserted decision of '{subject}'", "supersedes")
        if active and not superseded:
            raise WriteError(409, "decision_exists", f"'{subject}' has an asserted decision ({active['id']}): name it in 'supersedes' to replace it")
        record["supersedes"] = superseded
        if not key:
            record["id"] = "D-" + _derived_id("D", self.engagement, "decision", f"{subject}|{len(self.repo.list_decisions(self.engagement)) + 1}")[2:]
        self.repo.save_decision(record)
        return {"created": True, "decision": self._public_decision(self.repo.get_decision_record(record["id"]))}

    def assert_decision(self, decision_id: str) -> dict[str, Any]:
        d = self._decision(decision_id)
        if d["status"] != "proposed":
            raise WriteError(409, "not_proposed", f"{decision_id} is '{d['status']}': only a proposed decision can be asserted")
        require_distinct(self.actor, [d.get("author") or ""], decision_id)
        others = [x for x in self.repo.list_decisions(self.engagement)
                  if x["subject"] == d["subject"] and x["status"] == "active" and x["id"] != d.get("supersedes")]
        if others:
            raise WriteError(409, "decision_exists", f"'{d['subject']}' already has an asserted decision ({others[0]['id']})")
        self.repo.validate_decision(decision_id, self.actor)
        return {"decision": self._public_decision(self.repo.get_decision_record(decision_id)),
                "superseded": [d["supersedes"]] if d.get("supersedes") else []}

    def withdraw_decision(self, decision_id: str, is_decider: bool) -> dict[str, Any]:
        d = self._decision(decision_id)
        if d["status"] not in ("proposed", "active"):
            raise WriteError(409, "not_withdrawable", f"{decision_id} is '{d['status']}'")
        if d.get("author") != self.actor and not is_decider:
            raise WriteError(403, "not_author", "only the author or a decider withdraws a decision")
        if d["status"] == "active" and self.repo.subject_levels(self.engagement).get(d["subject"]) in ASSERTED_LEVELS:
            raise WriteError(409, "subject_decided", f"'{d['subject']}' is decided on this decision: supersede it instead of withdrawing it")
        self.repo.set_decision_status(decision_id, "withdrawn")
        return {"decision": self._public_decision(self.repo.get_decision_record(decision_id))}

    @staticmethod
    def _list_of(body: dict[str, Any], field: str, keys: dict[str, bool]) -> list[dict[str, str]]:
        raw = body.get(field) or []
        if not isinstance(raw, list):
            raise WriteError(400, "invalid_argument", f"'{field}' is a list of {{{', '.join(keys)}}}", field)
        out = []
        for i, item in enumerate(raw):
            if not isinstance(item, dict) or any(not isinstance(item.get(k), str) or not item[k].strip() for k in keys):
                raise WriteError(400, "invalid_argument", f"{field}[{i}] needs a non-empty {' and '.join(keys)}", field)
            out.append({k: item[k].strip() for k in keys})
        return out

    def _decision(self, decision_id: str) -> dict[str, Any]:
        d = self.repo.get_decision_record(decision_id)
        if not d or d.get("engagement") != self.engagement:
            raise WriteError(404, "unknown_decision", f"decision '{decision_id}' not found")
        return d

    @staticmethod
    def _public_decision(d: dict[str, Any] | None) -> dict[str, Any]:
        keys = ("id", "subject", "decision", "rationale", "rejected", "reversibility", "consequences", "accepted_violations",
                "based_on", "status", "origin", "author", "validated_by", "validated_at", "supersedes")
        return {k: (d or {}).get(k) for k in keys}

    # --- questions and answers ------------------------------------------------------------------------------------

    def add_question(self, body: dict[str, Any], key: str | None = None) -> dict[str, Any]:
        key = _key(key or body.get("idempotency_key"))
        question = {
            "engagement": self.engagement,
            "question": _text(body, "question"),
            "why_it_matters": _text(body, "why_it_matters", required=False),
            "section": _text(body, "section", required=False, default="general", limit=120),
            "gap_type": _text(body, "gap_type", required=False, default="G2_unanswered_blocking", limit=48),
            "expected_shape": _text(body, "expected_shape", required=False, default="free_text", limit=32),
            "routed_to": _text(body, "routed_to", required=False, default="architect", limit=64),
            "status": "open",
        }
        if body.get("subject"):
            question["subject"] = _text(body, "subject", limit=120)
        if key:
            question["id"] = _derived_id("Q", self.engagement, "question", key)
            if self.repo.get_question(question["id"]):
                return {"created": False, "question": self.repo.get_question(question["id"])}
        question_id = self.repo.save_question(question)
        return {"created": True, "question": self.repo.get_question(question_id)}

    def answer_question(self, question_id: str, body: dict[str, Any], key: str | None = None) -> dict[str, Any]:
        question = self.repo.get_question(question_id)
        if not question:
            raise WriteError(404, "unknown_question", f"question '{question_id}' not found")
        if question.get("status") in ("declined", "rerouted"):
            raise WriteError(409, "question_closed", f"the question is '{question['status']}'")
        body = {**body, "section": body.get("section") or question.get("section") or "general"}
        body.setdefault("subject", self.subject_of_question(question_id) or "general")
        result = self.add_statement(body, key)
        if result["created"]:
            self.repo.link_answer(result["statement"]["id"], question_id)
            if "answered" in QUESTION_STATUSES:
                self.repo.update_question_status(question_id, "answered")
        return result

    def subject_of_question(self, question_id: str) -> str | None:
        rows = self.repo.db_client.execute_cypher(
            "MATCH (q:Question {id: $id})-[:TARGETS]->(s:Subject) RETURN s.name as name;", params={"id": question_id})
        return rows[0]["name"] if rows and "error" not in rows[0] else None

    # --- requirements ---------------------------------------------------------------------------------------------

    def add_requirements(self, body: dict[str, Any]) -> dict[str, Any]:
        items = body.get("requirements")
        if not isinstance(items, list) or not items or len(items) > 500:
            raise WriteError(400, "invalid_argument", "'requirements' is a list of 1 to 500 items", "requirements")
        origin = _origin(body)
        created, unchanged = [], []
        prepared = []
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                raise WriteError(400, "invalid_argument", f"requirements[{i}] must be an object", "requirements")
            req_id = item.get("id")
            if not isinstance(req_id, str) or not ID.match(req_id):
                raise WriteError(400, "invalid_argument", f"requirements[{i}].id is required (letters, digits . _ : -)", "requirements")
            prepared.append({
                "id": req_id, "engagement": self.engagement, "text": _text(item, "text"),
                "section": _text(item, "section", required=False, limit=200),
                "category": _text(item, "category", required=False, default="general", limit=64),
                "criticality": _text(item, "criticality", required=False, default="mandatory", limit=32),
                "status": "gap",
            })
        existing = {r["id"]: r for r in self.repo.get_requirements(self.engagement)}
        for req in prepared:
            old = existing.get(req["id"])
            if old is None:
                created.append(req)
            elif old.get("text") != req["text"]:
                raise WriteError(409, "requirement_changed", f"{req['id']} exists with another text: requirements are not rewritten", id=req["id"])
            else:
                unchanged.append(req["id"])
        for req in created:
            self.repo.save_requirement(req)
        return {"created": [r["id"] for r in created], "unchanged": unchanged, "origin": origin}

    # --- conflicts ------------------------------------------------------------------------------------------------

    def arbitrate(self, conflict_id: str, body: dict[str, Any]) -> dict[str, Any]:
        conflict = self.repo.get_conflict(conflict_id)
        if not conflict:
            raise WriteError(404, "unknown_conflict", f"conflict '{conflict_id}' not found")
        if conflict.get("status") != "open":
            raise WriteError(409, "not_open", f"the conflict is '{conflict.get('status')}'")
        keep = _text(body, "keep_statement_id", limit=64)
        if keep not in conflict["statement_ids"]:
            raise WriteError(400, "invalid_argument", f"'{keep}' is not involved in {conflict_id}", "keep_statement_id")
        reason = _text(body, "reason", limit=1000)
        authors = [(self.repo.get_statement_record(s) or {}).get("author") or "" for s in conflict["statement_ids"]]
        require_distinct(self.actor, authors, f"a statement of {conflict_id}")
        self.repo.arbitrate_conflict(conflict_id, keep, reason, self.actor)
        return {"conflict": {k: v for k, v in (self.repo.get_conflict(conflict_id) or {}).items()}}

    # --- helpers --------------------------------------------------------------------------------------------------

    def _statement(self, statement_id: str) -> dict[str, Any]:
        st = self.repo.get_statement_record(statement_id)
        if not st or st.get("engagement") != self.engagement:
            raise WriteError(404, "unknown_statement", f"statement '{statement_id}' not found")
        return st

    @staticmethod
    def _public(st: dict[str, Any] | None) -> dict[str, Any]:
        keys = ("id", "subject", "section", "predicate", "value", "author", "role", "confidence", "status", "origin",
                "validated_by", "validated_at")
        return {k: (st or {}).get(k) for k in keys}
