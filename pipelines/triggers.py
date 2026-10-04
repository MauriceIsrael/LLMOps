"""Question triggers: declarative rules that link asserted facts to a question that becomes relevant (K19).

A rule is architect knowledge, so it lives **with the element that justifies it** (a principle, a pattern, a control) in the
knowledge base: ``data/kb/triggers/<id>.yaml``, one rule per file, versioned and citable like any element
(``trigger:<id>`` at ``version``, guarded by the version ledger, K3).

    trigger_id: TRG-multisite-replication
    version: 1
    asset: P-010                        # the carrier: an element of the knowledge base (never invented)
    when:                               # a conjunction: every condition must hold
      - {key: topology.dc_count, op: gte, value: 2}
    question: {fr: ..., en: ...}
    rationale: {fr: ..., en: ...}
    initial_level: L1_framed            # L0_named | L1_framed
    suggested_role: architect
    mandatory: false                    # true for a regulatory control: closing the question then needs a justification

The format is **declarative** (no code) so that every evaluator gives the same result. Semantics, fixed here and implemented by
:func:`matches`: a condition is true only when a fact with that key is in force and the comparison holds; with no fact for the
key, the condition is false (this includes ``neq``); ``in`` holds when the value is one of the listed values; ``gte`` and ``lte``
apply to ``int`` and ``duration`` keys only. Facts are those of K18 (asserted decisions only).

A rule that is not valid is not published: the report names the file and the path of each error.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from pipelines.engagement import facts as fact_module
from pipelines.knowledge_ref import content_sha256, knowledge_ref

OPS = ("eq", "neq", "gte", "lte", "in")
ORDERED_TYPES = ("int", "duration")
LEVELS = ("L0_named", "L1_framed")
ID = re.compile(r"^TRG-[a-z0-9][a-z0-9-]{0,62}$")
LOCAL_ID = re.compile(r"^TRG-local-[a-z0-9][a-z0-9-]{0,50}$")  # an engagement's own rule (K21), never a knowledge-base element
FIELDS = {"trigger_id", "version", "asset", "when", "question", "rationale", "initial_level", "suggested_role", "mandatory"}
MAX_TEXT = 1000
MAX_CONDITIONS = 10
TRIGGERS_DIR = "triggers"


class TriggerError(ValueError):
    """The triggers of the knowledge base are not publishable. ``problems`` is ``[{trigger, path, code, reason}]``."""

    def __init__(self, problems: list[dict[str, str]]) -> None:
        self.problems = problems
        head = "; ".join(f"{p['trigger']} {p['path']}: {p['reason']}" for p in problems[:5])
        super().__init__(f"{len(problems)} invalid trigger rule(s): {head}")


def trigger_key(trigger_id: str) -> str:
    return f"trigger:{trigger_id}"


def carriers(kb_dir: Path) -> dict[str, dict[str, Any]]:
    """The elements that may carry a rule: every element of the knowledge base with a front matter ``id`` (assets, controls)."""
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(kb_dir.rglob("*.md")):
        if path.name.startswith("_") or TRIGGERS_DIR in path.relative_to(kb_dir).parts:
            continue
        text = path.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if not match:
            continue
        try:
            front = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            continue
        if isinstance(front, dict) and isinstance(front.get("id"), str):
            out[front["id"]] = {"type": front.get("type"), "severity": front.get("severity"), "framework": front.get("framework")}
    return out


def _text(value: Any, path: str, problems: list[dict[str, str]], name: str) -> None:
    ok = isinstance(value, dict) and set(value) == {"fr", "en"} and all(isinstance(v, str) and v.strip() and len(v) <= MAX_TEXT for v in value.values())
    if not ok:
        problems.append({"trigger": name, "path": path, "code": "TEXT", "reason": f"needs a non-empty 'fr' and 'en' text (max {MAX_TEXT} characters)"})


def check_condition(condition: Any, path: str, vocabulary: dict[str, Any]) -> tuple[str, str] | None:
    """``(code, reason)`` of the first error of a condition, or ``None``."""
    if not isinstance(condition, dict) or set(condition) != {"key", "op", "value"}:
        return "CONDITION_SHAPE", "a condition is {key, op, value}"
    definition = vocabulary["keys"].get(condition["key"]) if isinstance(condition["key"], str) else None
    if definition is None:
        return "UNKNOWN_FACT_KEY", f"'{condition['key']}' is not in the facts vocabulary (version {vocabulary['version']})"
    op = condition["op"]
    if op not in OPS:
        return "UNKNOWN_OP", f"'op' must be one of {list(OPS)}"
    if op in ("gte", "lte") and definition["type"] not in ORDERED_TYPES:
        return "OP_TYPE", f"'{op}' applies to int and duration keys; '{condition['key']}' is {definition['type']}"
    values = condition["value"]
    if op == "in":
        if not isinstance(values, list) or not values or len({repr(v) for v in values}) != len(values):
            return "VALUE_TYPE", "'in' needs a non-empty list of distinct values"
    else:
        values = [values]
    for v in values:
        try:
            fact_module._check_value(definition, v, path)  # noqa: SLF001 - one source of truth for the types of a key
        except fact_module.FactError as err:
            return "VALUE_TYPE", err.reason
    return None


def validate_rule(doc: Any, name: str, vocabulary: dict[str, Any], carrier_index: dict[str, dict[str, Any]],
                  local: bool = False) -> list[dict[str, str]]:
    """Every problem of one rule document, with the path of each. Nothing is repaired.

    ``local``: a rule of one engagement (K21), same schema and same checks; its id is ``TRG-local-…`` and its carrier is optional
    (a rule specific to a programme may have no element of the knowledge base behind it), checked when given.
    """
    problems: list[dict[str, str]] = []

    def add(path: str, code: str, reason: str) -> None:
        problems.append({"trigger": name, "path": path, "code": code, "reason": reason})

    if not isinstance(doc, dict):
        add("$", "SHAPE", "a rule is a YAML mapping")
        return problems
    for unknown in sorted(set(doc) - FIELDS):
        add(unknown, "UNKNOWN_FIELD", f"'{unknown}' is not a field of a rule")
    id_format = LOCAL_ID if local else ID
    if not isinstance(doc.get("trigger_id"), str) or not id_format.match(doc["trigger_id"]):
        add("trigger_id", "ID", "'trigger_id' must look like " + ("TRG-local-some-name" if local else "TRG-some-name"))
    elif doc["trigger_id"] != name:
        add("trigger_id", "ID", f"'trigger_id' must be the file name ({name})")
    elif not local and doc["trigger_id"].startswith("TRG-local-"):
        add("trigger_id", "ID", "'TRG-local-' is reserved for the rules of one engagement (K21)")
    version = doc.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        add("version", "VERSION", "'version' must be a positive integer")
    carrier = carrier_index.get(doc.get("asset")) if isinstance(doc.get("asset"), str) else None
    if carrier is None and not (local and doc.get("asset") is None):
        add("asset", "UNKNOWN_ASSET", f"the carrier '{doc.get('asset')}' is not an element of the knowledge base")
    when = doc.get("when")
    if not isinstance(when, list) or not when or len(when) > MAX_CONDITIONS:
        add("when", "WHEN", f"'when' is a non-empty list of at most {MAX_CONDITIONS} conditions")
    else:
        for i, condition in enumerate(when):
            err = check_condition(condition, f"when[{i}]", vocabulary)
            if err:
                sub = "key" if err[0] == "UNKNOWN_FACT_KEY" else "op" if err[0] in ("UNKNOWN_OP", "OP_TYPE") else "value" if err[0] == "VALUE_TYPE" else ""
                add(f"when[{i}]" + (f".{sub}" if sub else ""), err[0], err[1])
    _text(doc.get("question"), "question", problems, name)
    _text(doc.get("rationale"), "rationale", problems, name)
    if doc.get("initial_level") not in LEVELS:
        add("initial_level", "LEVEL", f"'initial_level' must be one of {list(LEVELS)}")
    role = doc.get("suggested_role")
    if not isinstance(role, str) or not role.strip() or len(role) > 64:
        add("suggested_role", "ROLE", "'suggested_role' is a non-empty role name")
    if not isinstance(doc.get("mandatory"), bool):
        add("mandatory", "MANDATORY", "'mandatory' must be true or false")
    elif carrier and carrier.get("type") == "control" and carrier.get("severity") == "mandatory" and doc["mandatory"] is not True:
        add("mandatory", "MANDATORY_REQUIRED", "a rule carried by a mandatory regulatory control must be mandatory")
    return problems


def load_all(kb_dir: Path, vocabulary: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """The valid rules of ``<kb_dir>/triggers`` sorted by id, each with ``content_sha256`` of its file.

    Raises :class:`TriggerError` with every problem when any rule is invalid: a rule that is not valid is not published.
    """
    folder = kb_dir / TRIGGERS_DIR
    files = sorted(folder.glob("*.yaml")) if folder.is_dir() else []
    if not files:
        return []
    if vocabulary is None:
        try:
            vocabulary = fact_module.load(kb_dir / "vocabulary" / "facts.yaml")
        except (OSError, fact_module.VocabularyError) as err:
            raise TriggerError([{"trigger": "*", "path": "vocabulary", "code": "NO_VOCABULARY", "reason": f"the facts vocabulary is unusable: {err}"}]) from err
    index = carriers(kb_dir)
    problems: list[dict[str, str]] = []
    rules: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in files:
        text = path.read_text(encoding="utf-8")
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError as err:
            problems.append({"trigger": path.stem, "path": "$", "code": "YAML", "reason": f"not valid YAML: {str(err).splitlines()[0]}"})
            continue
        found = validate_rule(doc, path.stem, vocabulary, index)
        if not found and doc["trigger_id"] in seen:
            found = [{"trigger": path.stem, "path": "trigger_id", "code": "DUPLICATE", "reason": "identifier already defined"}]
        problems.extend(found)
        if not found:
            seen.add(doc["trigger_id"])
            rules.append({**doc, "content_sha256": content_sha256(text)})
    if problems:
        raise TriggerError(problems)
    return sorted(rules, key=lambda r: r["trigger_id"])


def public(rule: dict[str, Any], carrier_ref: dict[str, Any]) -> dict[str, Any]:
    """A rule as the sealed snapshot of the knowledge base carries it, resolved to its carrier."""
    return {
        "trigger_id": rule["trigger_id"], "version": rule["version"],
        "knowledge_ref": knowledge_ref(trigger_key(rule["trigger_id"]), rule["version"]),
        "carrier": carrier_ref, "when": [dict(c) for c in rule["when"]],
        "question": dict(rule["question"]), "rationale": dict(rule["rationale"]),
        "initial_level": rule["initial_level"], "suggested_role": rule["suggested_role"], "mandatory": rule["mandatory"],
    }


def matches(rule: dict[str, Any], facts: dict[str, Any]) -> bool:
    """Reference evaluation of a rule against ``{key: value}`` (the facts in force). Pure and deterministic."""
    for c in rule["when"]:
        if c["key"] not in facts:
            return False
        have, want, op = facts[c["key"]], c["value"], c["op"]
        if op == "eq":
            ok = have == want and type(have) is type(want)
        elif op == "neq":
            ok = not (have == want and type(have) is type(want))
        elif op == "gte":
            ok = have >= want
        elif op == "lte":
            ok = have <= want
        else:
            ok = any(have == w and type(have) is type(w) for w in want)
        if not ok:
            return False
    return True
