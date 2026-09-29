"""Structured check clauses (``checks`` front-matter block) and their evaluation.

A clause, attached to a principle, pattern, decision or control::

    checks:
      - id: P-002-C1
        kind: requires          # requires | forbids
        when:                   # the clause applies if the option matches
          terms_any: [closed-loop, auto-remediation]
        expect:                 # requires only: what must also be present
          terms_any: [human-approval, supervised]
        message: "Any closed loop must stay supervised by a human."

Semantics (deterministic, lexical):

* ``when`` does not match  -> the clause does not apply;
* ``forbids`` + ``when``   -> ``violates``;
* ``requires`` + ``when``  -> ``supports`` if ``expect`` matches, else ``violates``.

A matcher accepts ``terms_any`` (at least one term) and/or ``terms_all`` (every term);
when both are given, both must hold. Terms are matched through ``text.match_terms``
(normalization + glossary synonyms).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pipelines.doctrine.text import Vocabulary, match_terms

CHECK_KINDS = ("requires", "forbids")
MATCHER_KEYS = ("terms_any", "terms_all")


@dataclass(frozen=True)
class Matcher:
    terms_any: tuple[str, ...] = ()
    terms_all: tuple[str, ...] = ()

    def match(self, normalized_text: str, vocabulary: Vocabulary) -> tuple[bool, list[str]]:
        """Return (matches, matched terms)."""
        matched: list[str] = []
        ok = True
        if self.terms_any:
            hits = match_terms(normalized_text, self.terms_any, vocabulary)
            ok = ok and bool(hits)
            matched += hits
        if self.terms_all:
            hits = match_terms(normalized_text, self.terms_all, vocabulary)
            ok = ok and len(hits) == len(self.terms_all)
            matched += [h for h in hits if h not in matched]
        if not self.terms_any and not self.terms_all:
            ok = False
        return ok, matched


@dataclass(frozen=True)
class CheckClause:
    id: str
    kind: str
    when: Matcher
    expect: Matcher | None
    message: str
    status: str = "draft"  # draft | validated (from ``checks_status``)
    extra: dict[str, Any] = field(default_factory=dict, compare=False)


@dataclass(frozen=True)
class ClauseResult:
    clause: CheckClause
    verdict: str  # supports | violates
    matched_terms: list[str]


def validate_clause(raw: Any) -> list[str]:
    """Return the list of problems of a raw clause (empty when valid)."""
    problems: list[str] = []
    if not isinstance(raw, dict):
        return ["clause must be a mapping"]
    if not raw.get("id") or not isinstance(raw.get("id"), str):
        problems.append("missing string 'id'")
    kind = raw.get("kind")
    if kind not in CHECK_KINDS:
        problems.append(f"'kind' must be one of {list(CHECK_KINDS)}")
    for key in ("when", "expect"):
        block = raw.get(key)
        if block is None:
            if key == "when" or kind == "requires":
                problems.append(f"missing '{key}'")
            continue
        if not isinstance(block, dict) or not any(block.get(k) for k in MATCHER_KEYS):
            problems.append(f"'{key}' must define terms_any and/or terms_all")
            continue
        for k in MATCHER_KEYS:
            v = block.get(k)
            if v is not None and (not isinstance(v, list) or not all(isinstance(t, str) and t.strip() for t in v)):
                problems.append(f"'{key}.{k}' must be a list of non-empty strings")
    if kind == "forbids" and raw.get("expect") is not None:
        problems.append("'expect' is only meaningful for kind 'requires'")
    if raw.get("message") is not None and not isinstance(raw.get("message"), str):
        problems.append("'message' must be a string")
    return problems


def _matcher(block: dict[str, Any] | None) -> Matcher | None:
    if not block:
        return None
    return Matcher(
        terms_any=tuple(str(t) for t in block.get("terms_any") or ()),
        terms_all=tuple(str(t) for t in block.get("terms_all") or ()),
    )


def parse_checks(raw_checks: Any, checks_status: str | None = None) -> list[CheckClause]:
    """Parse a raw ``checks`` block, silently skipping invalid clauses.

    Invalid clauses are reported by ``validate_clause`` (used by the KB candidate
    checks); the judge never fails on a malformed clause, it ignores it.
    """
    if not isinstance(raw_checks, list):
        return []
    status = "validated" if str(checks_status or "").lower() in ("validated", "active") else "draft"
    clauses = []
    for raw in raw_checks:
        if validate_clause(raw):
            continue
        when = _matcher(raw.get("when"))
        if when is None:
            continue
        clauses.append(
            CheckClause(
                id=str(raw["id"]),
                kind=str(raw["kind"]),
                when=when,
                expect=_matcher(raw.get("expect")),
                message=str(raw.get("message") or ""),
                status=status,
            )
        )
    return clauses


def evaluate_clause(clause: CheckClause, normalized_text: str, vocabulary: Vocabulary) -> ClauseResult | None:
    """Evaluate a clause on an option's normalized text; None when it does not apply."""
    applies, when_terms = clause.when.match(normalized_text, vocabulary)
    if not applies:
        return None
    if clause.kind == "forbids":
        return ClauseResult(clause, "violates", when_terms)
    assert clause.expect is not None
    satisfied, expect_terms = clause.expect.match(normalized_text, vocabulary)
    if satisfied:
        return ClauseResult(clause, "supports", when_terms + [t for t in expect_terms if t not in when_terms])
    return ClauseResult(clause, "violates", when_terms)
