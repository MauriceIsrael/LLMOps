"""Interpretation of an expert's answer into candidate statements (intake flow).

No language model is used here. Two implementations:

* ``ScriptedInterpreter`` — used when the engagement provides
  ``examples/<engagement>/scripted_interpretations.yaml``: deterministic rules (text
  cues -> candidate statements, uncertainties, maturity advance, discovered subjects)
  written for a reference scenario, plus a fallback.
* ``PassthroughInterpreter`` — the default: the answer is kept verbatim as an
  ``Uncertainty`` on the question's subject; no statement is invented.

Every candidate is then shown to the expert for confirmation before anything is saved.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

import yaml

from tools.elicitation.profile import engagement_file, load_profile
from tools.elicitation.resolve import engagement_of

SCRIPT_FILE = "scripted_interpretations.yaml"


class Interpreter(Protocol):
    def interpret(self, state: dict[str, Any]) -> dict[str, Any]: ...


def _empty_result() -> dict[str, Any]:
    return {
        "candidate_statements": [],
        "uncertainties": [],
        "candidate_patterns": [],
        "no_pattern_for_decomposition": False,
        "advance_level_to": None,
        "created_subjects": [],
    }


def _context(state: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    q = state.get("question", {}) or {}
    return {
        "q": q,
        "text": state.get("answer_text", ""),
        "section": q.get("section", defaults.get("section", "")),
        "question_id": q.get("id", "Q-0001"),
        "author": state.get("author", defaults.get("author", "")),
        "role": state.get("role", defaults.get("role", "architect")),
        "engagement": engagement_of(state.get("engagement") or q.get("engagement")),
        "subject": q.get("subject", defaults.get("subject", "")),
    }


class PassthroughInterpreter:
    """Default: keep the answer verbatim as an uncertainty, invent no statement."""

    def interpret(self, state: dict[str, Any]) -> dict[str, Any]:
        profile = load_profile(state.get("engagement") or (state.get("question") or {}).get("engagement"))
        ctx = _context(state, {"role": profile.default_role, "subject": profile.default_subject})
        result = _empty_result()
        if ctx["text"].strip():
            result["uncertainties"] = [{
                "engagement": ctx["engagement"],
                "subject": ctx["subject"],
                "text": ctx["text"].strip(),
                "author": ctx["author"],
                "role": ctx["role"],
                "question_id": ctx["question_id"],
            }]
        return result


class ScriptedInterpreter:
    """Rules of a reference scenario, read from ``scripted_interpretations.yaml``.

    Each rule has cues (``when_any``, matched on the lower-cased answer with collapsed
    whitespace, or on the raw lower-cased answer with ``match: raw``) and produces
    statements (``{section, subject, predicate, value, confidence}``; ``value: $verbatim80``
    stands for the first 80 characters of the answer), optional uncertainties (with their
    own ``when_any``), ``advance_level_to``, ``created_subjects``, ``candidate_patterns`` and
    ``no_pattern_for_decomposition``. ``fallback`` applies when no rule matches.
    """

    def __init__(self, script: dict[str, Any]) -> None:
        self.defaults = dict(script.get("defaults") or {})
        self.rules = list(script.get("rules") or [])
        self.fallback = script.get("fallback")

    @classmethod
    def from_file(cls, path: str | Path) -> ScriptedInterpreter:
        return cls(yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {})

    @staticmethod
    def _matches(cues: list[str], norm_text: str, raw_lower: str, mode: str) -> bool:
        haystack = raw_lower if mode == "raw" else norm_text
        return any(str(c).lower() in haystack for c in cues)

    def _statement(self, spec: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
        value = str(spec.get("value", ""))
        if value == "$verbatim80":
            value = ctx["text"][:80]
        return {
            "question_id": ctx["question_id"],
            "engagement": ctx["engagement"],
            "section": spec.get("section") or ctx["section"],
            "subject": spec.get("subject") or ctx["subject"],
            "predicate": spec.get("predicate", "has_property"),
            "value": value,
            "author": ctx["author"],
            "role": ctx["role"],
            "confidence": spec.get("confidence", "designed"),
            "verbatim": ctx["text"],
        }

    def _apply(self, rule: dict[str, Any], ctx: dict[str, Any], norm_text: str, raw_lower: str) -> dict[str, Any]:
        result = _empty_result()
        result["candidate_statements"] = [self._statement(s, ctx) for s in rule.get("statements") or []]
        for unc in rule.get("uncertainties") or []:
            if self._matches(unc.get("when_any") or [], norm_text, raw_lower, unc.get("match", "normalized")):
                result["uncertainties"].append({
                    "engagement": ctx["engagement"],
                    "subject": unc.get("subject") or ctx["subject"],
                    "text": unc.get("text", ""),
                })
        result["advance_level_to"] = rule.get("advance_level_to")
        result["created_subjects"] = list(rule.get("created_subjects") or [])
        result["candidate_patterns"] = list(rule.get("candidate_patterns") or [])
        result["no_pattern_for_decomposition"] = bool(rule.get("no_pattern_for_decomposition", False))
        return result

    def interpret(self, state: dict[str, Any]) -> dict[str, Any]:
        ctx = _context(state, self.defaults)
        text = ctx["text"]
        norm_text = " ".join(text.lower().split())
        raw_lower = text.lower()
        for rule in self.rules:
            if self._matches(rule.get("when_any") or [], norm_text, raw_lower, rule.get("match", "normalized")):
                return self._apply(rule, ctx, norm_text, raw_lower)
        if self.fallback:
            return self._apply(self.fallback, ctx, norm_text, raw_lower)
        return PassthroughInterpreter().interpret(state)


def get_interpreter(engagement: str | None) -> Interpreter:
    """Scripted interpreter when the engagement ships a script, passthrough otherwise."""
    path = engagement_file(engagement, SCRIPT_FILE)
    if path is not None:
        return ScriptedInterpreter.from_file(path)
    return PassthroughInterpreter()
