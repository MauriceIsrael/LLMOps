"""Question triggers and facts-vocabulary keys in the candidate cycle (K22).

The rules of K19 and the keys of K18 enter the knowledge base through the **same cycle as any other knowledge** (contract 1.2):
a candidate, deterministic checks, a human review, promotion, publication. Nothing is published automatically, whatever its origin.

* ``asset_type: trigger``: the content is the YAML of one rule (``data/kb/triggers/<id>.yaml``). A new rule, or an amendment
  (``target_asset_id`` is the rule, ``version`` is the previous one plus one: the version ledger, K3, requires it).
* ``asset_type: fact_key``: the content is the YAML of one key of ``data/kb/vocabulary/facts.yaml``. Accepting it adds the key
  and raises the vocabulary ``version``. A reviewer may instead **merge** it into an existing key (``merge_fact_key``).

The checks are those of K19 (same validator, same vocabulary): a rule that cites a key the vocabulary does not know fails its
``schema`` check with the path of the key: nothing is repaired in silence.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from pipelines import triggers
from pipelines.engagement import facts as fact_module

TRIGGER_TYPES = ("trigger", "fact_key")


def parse_content(text: str) -> dict[str, Any] | None:
    try:
        doc = yaml.safe_load(text or "")
    except yaml.YAMLError:
        return None
    return doc if isinstance(doc, dict) else None


def vocabulary_path(kb_dir: Path) -> Path:
    return kb_dir / "vocabulary" / "facts.yaml"


def _result(status: str, detail: str) -> dict[str, str]:
    return {"name": "schema", "status": status, "detail": detail}


def problems_of(candidate: dict[str, Any], kb_dir: Path) -> tuple[list[dict[str, str]], dict[str, Any] | None]:
    """Every problem of a trigger or fact_key candidate as ``{path, code, reason}``, and the parsed document.

    The same list feeds the ``schema`` check and the live validation of the admin application.
    """
    doc = parse_content(candidate.get("proposed_content", ""))
    if doc is None:
        what = "rule" if candidate.get("asset_type") == "trigger" else "vocabulary key"
        return [{"path": "$", "code": "YAML", "reason": f"the content must be the YAML mapping of one {what}"}], None
    amendment = candidate.get("kind") == "amendment" or bool(candidate.get("target_asset_id"))
    try:
        vocabulary = fact_module.load(vocabulary_path(kb_dir))
    except (OSError, fact_module.VocabularyError) as err:
        return [{"path": "vocabulary", "code": "NO_VOCABULARY", "reason": f"the facts vocabulary is unusable: {err}"}], doc
    if candidate.get("asset_type") == "fact_key":
        return _key_problems(doc, vocabulary, amendment, candidate.get("target_asset_id")), doc
    return _rule_problems(doc, vocabulary, kb_dir, amendment, candidate.get("target_asset_id")), doc


def check_schema(candidate: dict[str, Any], kb_dir: Path) -> dict[str, str]:
    """The ``schema`` check of a trigger or fact_key candidate."""
    problems, doc = problems_of(candidate, kb_dir)
    if problems:
        return _result("fail", "; ".join(f"{p['path']} [{p['code']}] {p['reason']}" for p in problems))
    if candidate["asset_type"] == "fact_key":
        return _result("pass", f"vocabulary key '{doc['key']}' ({doc['type']}) is valid" + (f", justified by {doc['asset']}" if doc.get("asset") else ""))
    vocabulary = fact_module.load(vocabulary_path(kb_dir))
    return _result("pass", f"rule {doc['trigger_id']} version {doc['version']}: {len(doc['when'])} condition(s) valid against vocabulary version {vocabulary['version']}")


def _key_problems(doc: dict[str, Any], vocabulary: dict[str, Any], amendment: bool, target: str | None) -> list[dict[str, str]]:
    try:
        fact_module.parse(yaml.safe_dump({"version": 1, "keys": [doc]}))
    except fact_module.VocabularyError as err:
        return [{"path": "key", "code": "KEY", "reason": str(err)}]
    key = doc["key"]
    if amendment:
        if key != target:
            return [{"path": "key", "code": "TARGET", "reason": f"amendment key '{key}' differs from target_asset_id '{target}'"}]
        if key not in vocabulary["keys"]:
            return [{"path": "key", "code": "TARGET", "reason": f"target key '{key}' does not exist"}]
        if vocabulary["keys"][key]["type"] != doc["type"]:
            return [{"path": "type", "code": "KEY_TYPE", "reason": f"the type of '{key}' cannot change ({vocabulary['keys'][key]['type']} to {doc['type']}): rules and facts depend on it"}]
    elif key in vocabulary["keys"]:
        return [{"path": "key", "code": "EXISTS", "reason": f"'{key}' already exists in the facts vocabulary: submit an amendment, or merge"}]
    return []


def _rule_problems(doc: dict[str, Any], vocabulary: dict[str, Any], kb_dir: Path, amendment: bool, target: str | None) -> list[dict[str, str]]:
    trigger_id = str(doc.get("trigger_id"))
    out = [{"path": p["path"], "code": p["code"], "reason": p["reason"]}
           for p in triggers.validate_rule(doc, trigger_id, vocabulary, triggers.carriers(kb_dir))]
    path = kb_dir / triggers.TRIGGERS_DIR / f"{trigger_id}.yaml"
    if amendment:
        if trigger_id != target:
            out.append({"path": "trigger_id", "code": "TARGET", "reason": f"amendment trigger_id '{trigger_id}' differs from target_asset_id '{target}'"})
        elif not path.exists():
            out.append({"path": "trigger_id", "code": "TARGET", "reason": f"target rule '{target}' does not exist"})
        else:
            previous = (parse_content(path.read_text(encoding="utf-8")) or {}).get("version")
            if isinstance(previous, int) and doc.get("version") != previous + 1:
                out.append({"path": "version", "code": "VERSION", "reason": f"an amendment of version {previous} must be version {previous + 1}"})
    elif path.exists():
        out.append({"path": "trigger_id", "code": "EXISTS", "reason": f"'{trigger_id}' already exists: submit an amendment with target_asset_id '{trigger_id}'"})
    return out


def promote(candidate: dict[str, Any], kb_dir: Path) -> tuple[Path, str]:
    """Write an accepted trigger or fact_key candidate into the knowledge base: ``(path, asset id)``."""
    doc = parse_content(candidate["proposed_content"]) or {}
    if candidate["asset_type"] == "trigger":
        path = kb_dir / triggers.TRIGGERS_DIR / f"{doc['trigger_id']}.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=1000, default_flow_style=None), encoding="utf-8")
        return path, str(doc["trigger_id"])
    path = vocabulary_path(kb_dir)
    text = path.read_text(encoding="utf-8")
    header = "".join(line for line in text.splitlines(keepends=True) if line.startswith("#") or not line.strip()).split("version:")[0]
    body = yaml.safe_load(text)
    keys = [k for k in body["keys"] if k["key"] != doc["key"]]
    index = next((i for i, k in enumerate(body["keys"]) if k["key"] == doc["key"]), len(keys))
    keys.insert(index, doc)
    body = {"version": int(body["version"]) + 1, "keys": keys}
    path.write_text(header.rstrip() + "\n" + yaml.safe_dump(body, sort_keys=False, allow_unicode=True, width=1000, default_flow_style=None),
                    encoding="utf-8")
    return path, f"vocabulary:{doc['key']}"


def rewrite_key(content: str, old: str, new: str) -> str:
    """The rule ``content`` with every condition on ``old`` moved to ``new`` (a merge into an existing key)."""
    doc = parse_content(content) or {}
    for condition in doc.get("when") or []:
        if isinstance(condition, dict) and condition.get("key") == old:
            condition["key"] = new
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=1000, default_flow_style=None)


def keys_of(content: str) -> set[str]:
    doc = parse_content(content) or {}
    return {c["key"] for c in doc.get("when") or [] if isinstance(c, dict) and isinstance(c.get("key"), str)}


SLUG = re.compile(r"[^a-z0-9]+")


def slug(text: str) -> str:
    return SLUG.sub("-", text.lower()).strip("-")[:48]
