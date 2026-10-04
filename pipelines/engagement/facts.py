"""Architecture facts: the vocabulary of the knowledge base and the facts a decision asserts (K18).

A decision may carry ``facts: [{key, value, source_excerpt}]``. The keys come from ``data/kb/vocabulary/facts.yaml``, shared
by every engagement. A fact counts only while the decision that carries it is **asserted** (status ``active``): a proposed,
withdrawn or superseded decision brings none. Nothing is repaired in silence: an unknown key or a value of the wrong type is
refused with ``UNKNOWN_FACT_KEY`` / ``FACT_TYPE``.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from pipelines.knowledge_ref import content_sha256, knowledge_ref

VOCABULARY_KEY = "vocabulary:facts"
TYPES = ("int", "bool", "enum", "duration")
KEY_FORMAT = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
MAX_FACTS = 50
MAX_EXCERPT = 1000
MAX_INT = 2**53 - 1  # the canonical-json v1 profile refuses larger integers


class VocabularyError(ValueError):
    """The vocabulary file is not usable: nothing is guessed."""


class FactError(ValueError):
    """A refused fact. ``code`` is ``UNKNOWN_FACT_KEY``, ``FACT_TYPE``, ``FACT_DUPLICATE`` or ``FACT_SHAPE``."""

    def __init__(self, code: str, reason: str, path: str) -> None:
        self.code = code
        self.reason = reason
        self.path = path
        super().__init__(f"{code}: {reason}")


def default_path() -> Path:
    from mcp_server.core.config import server_config

    return server_config.kb_dir / "vocabulary" / "facts.yaml"


def parse(text: str) -> dict[str, Any]:
    """The vocabulary of ``text``, checked: ``{version, keys: {key: definition}}``."""
    try:
        doc = yaml.safe_load(text) or {}
    except yaml.YAMLError as err:
        raise VocabularyError(f"not valid YAML: {err}") from err
    version = doc.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise VocabularyError("'version' must be a positive integer")
    keys: dict[str, dict[str, Any]] = {}
    for i, entry in enumerate(doc.get("keys") or []):
        key = entry.get("key") if isinstance(entry, dict) else None
        if not isinstance(key, str) or not KEY_FORMAT.match(key):
            raise VocabularyError(f"keys[{i}]: 'key' must look like 'domain.name'")
        if key in keys:
            raise VocabularyError(f"keys[{i}]: '{key}' is defined twice")
        if entry.get("type") not in TYPES:
            raise VocabularyError(f"{key}: 'type' must be one of {list(TYPES)}")
        if entry["type"] == "enum":
            values = entry.get("values")
            if not isinstance(values, list) or not values or not all(isinstance(v, str) and v for v in values) or len(set(values)) != len(values):
                raise VocabularyError(f"{key}: an enum needs a list of distinct non-empty 'values'")
        label = entry.get("label") or {}
        if not isinstance(label, dict) or not all(isinstance(label.get(lang), str) and label[lang] for lang in ("fr", "en")):
            raise VocabularyError(f"{key}: 'label' needs a 'fr' and an 'en' text")
        for bound in ("min", "max"):
            if bound in entry and (isinstance(entry[bound], bool) or not isinstance(entry[bound], int)):
                raise VocabularyError(f"{key}: '{bound}' must be an integer")
        keys[key] = entry
    if not keys:
        raise VocabularyError("the vocabulary defines no key")
    return {"version": version, "keys": keys}


@lru_cache(maxsize=8)
def _load(path: str, mtime: float) -> tuple[dict[str, Any], str]:
    text = Path(path).read_text(encoding="utf-8")
    return parse(text), content_sha256(text)


def load(path: Path | None = None) -> dict[str, Any]:
    """The vocabulary, with its content hash: ``{version, keys, content_sha256, knowledge_ref}``."""
    target = path or default_path()
    vocabulary, sha = _load(str(target), target.stat().st_mtime)
    return {**vocabulary, "content_sha256": sha, "knowledge_ref": knowledge_ref(VOCABULARY_KEY, vocabulary["version"])}


def public_keys(vocabulary: dict[str, Any]) -> list[dict[str, Any]]:
    """The keys as the snapshot of the knowledge base carries them: sorted, only declared properties."""
    out = []
    for key in sorted(vocabulary["keys"]):
        d = vocabulary["keys"][key]
        item: dict[str, Any] = {"key": key, "type": d["type"], "label": {"fr": d["label"]["fr"], "en": d["label"]["en"]}}
        for optional in ("values", "unit", "min", "max", "asset"):
            if d.get(optional) is not None:
                item[optional] = list(d[optional]) if optional == "values" else d[optional]
        out.append(item)
    return out


def _check_value(definition: dict[str, Any], value: Any, path: str) -> None:
    kind = definition["type"]
    if kind == "bool":
        if not isinstance(value, bool):
            raise FactError("FACT_TYPE", "expected a boolean", path)
    elif kind in ("int", "duration"):
        if isinstance(value, bool) or not isinstance(value, int):
            raise FactError("FACT_TYPE", "expected a whole number" + (" of seconds" if kind == "duration" else ""), path)
        low = definition.get("min", 0 if kind == "duration" else None)
        high = definition.get("max")
        if abs(value) > MAX_INT or (low is not None and value < low) or (high is not None and value > high):
            raise FactError("FACT_TYPE", f"out of range [{'-inf' if low is None else low}, {'+inf' if high is None else high}]", path)
    else:
        if not isinstance(value, str) or value not in definition["values"]:
            raise FactError("FACT_TYPE", f"expected one of {definition['values']}", path)


def validate(raw: Any, vocabulary: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """The facts of a decision, validated and normalised: ``[{key, value, source_excerpt}]`` sorted by key."""
    if raw is None or raw == []:
        return []
    if not isinstance(raw, list) or len(raw) > MAX_FACTS:
        raise FactError("FACT_SHAPE", f"'facts' is a list of at most {MAX_FACTS} {{key, value, source_excerpt}}", "facts")
    vocabulary = vocabulary or load()
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, item in enumerate(raw):
        path = f"facts[{i}]"
        if not isinstance(item, dict) or not isinstance(item.get("key"), str) or "value" not in item:
            raise FactError("FACT_SHAPE", "a fact is {key, value, source_excerpt}", path)
        key = item["key"]
        definition = vocabulary["keys"].get(key)
        if definition is None:
            raise FactError("UNKNOWN_FACT_KEY", f"'{key}' is not in the facts vocabulary (version {vocabulary['version']})", f"{path}.key")
        if key in seen:
            raise FactError("FACT_DUPLICATE", f"'{key}' appears twice in the same decision", f"{path}.key")
        seen.add(key)
        _check_value(definition, item["value"], f"{path}.value")
        excerpt = item.get("source_excerpt")
        if not isinstance(excerpt, str) or not excerpt.strip() or len(excerpt) > MAX_EXCERPT:
            raise FactError("FACT_SHAPE", f"'source_excerpt' is required: the passage of the decision the fact comes from (max {MAX_EXCERPT})", f"{path}.source_excerpt")
        out.append({"key": key, "value": item["value"], "source_excerpt": excerpt.strip()})
    return sorted(out, key=lambda f: f["key"])


def from_snapshot(kb_snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    """The vocabulary as a sealed snapshot of the knowledge base carries it (the one an engagement pins), or ``None``."""
    section = (kb_snapshot or {}).get("fact_vocabulary")
    if not section:
        return None
    return {"version": section["version"], "keys": {k["key"]: k for k in section["keys"]},
            "content_sha256": section["content_sha256"], "knowledge_ref": section["knowledge_ref"]}


def in_force(decisions: list[dict[str, Any]], vocabulary: dict[str, Any] | None = None) -> dict[str, Any]:
    """The facts in force: those of **asserted** decisions only, each with its decision, sorted for a stable checksum.

    ``contradictions`` lists the keys asserted with different values by two decisions in force: nothing picks a winner.
    """
    vocabulary = vocabulary or load()
    items: list[dict[str, Any]] = []
    for d in sorted(decisions, key=lambda d: d["id"]):
        if d.get("status") != "active":
            continue
        for f in d.get("facts") or []:
            unit = (vocabulary["keys"].get(f["key"]) or {}).get("unit")
            item = {"key": f["key"], "value": f["value"], "source_excerpt": f.get("source_excerpt", ""),
                    "decision": d["id"], "subject": d["subject"]}
            if unit:
                item["unit"] = unit
            items.append(item)
    items.sort(key=lambda f: (f["key"], f["decision"]))
    values: dict[str, set[str]] = {}
    for f in items:
        values.setdefault(f["key"], set()).add(repr(f["value"]))
    contradictions = [{"key": k, "decisions": sorted(f["decision"] for f in items if f["key"] == k)}
                      for k in sorted(values) if len(values[k]) > 1]
    return {"vocabulary": {"version": vocabulary["version"], "knowledge_ref": vocabulary["knowledge_ref"]},
            "items": items, "contradictions": contradictions}


def pinned(decisions: list[dict[str, Any]], kb_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """The facts in force read against the vocabulary of the pinned snapshot; ``vocabulary`` is ``None`` without facts.

    Raises :class:`FactError` when a fact cannot be read against that vocabulary (absent, or a key it does not know).
    """
    vocabulary = from_snapshot(kb_snapshot)
    asserted = [d for d in decisions if d.get("status") == "active" and d.get("facts")]
    if vocabulary is None:
        if asserted:
            raise FactError("FACT_VOCABULARY_MISSING", "decisions assert facts but the pinned knowledge snapshot has no facts vocabulary", "facts")
        return {"vocabulary": None, "items": [], "contradictions": []}
    for d in asserted:
        validate(d["facts"], vocabulary)
    return in_force(decisions, vocabulary)
