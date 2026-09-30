"""Deterministic text normalization and term matching for the doctrine engine.

No language model is involved: matching is lexical, on normalized text (lower case,
accents removed, punctuation folded to spaces, light plural stemming), extended with
the synonym groups of the glossary.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field

# Minimal bilingual (EN/FR) stop word list: words that carry no doctrinal meaning.
STOPWORDS = frozenset(
    """
    a an and are as at be by for from has have in into is it its of on or that the this to
    with without within via per not no any all each every can may must shall should will
    de des du la le les un une et ou en au aux par pour sur sans avec dans est sont que qui
    ce cet cette ces son sa ses leur leurs il elle ils elles on nous vous doit doivent
    """.split()
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def stem(token: str) -> str:
    """Light, language-agnostic plural folding (policies -> policy, controls -> control)."""
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def tokens(text: str) -> list[str]:
    """Normalized, stemmed tokens (stop words kept, so that phrases stay contiguous)."""
    folded = _NON_ALNUM.sub(" ", strip_accents(str(text or "")).lower())
    return [stem(t) for t in folded.split() if t]


def normalize(text: str) -> str:
    """Space-padded normalized text, suitable for phrase containment tests."""
    return " " + " ".join(tokens(text)) + " "


def normalize_phrase(phrase: str) -> str:
    return " ".join(tokens(phrase))


def content_tokens(text: str) -> list[str]:
    """Tokens that carry meaning (stop words and 1-letter tokens removed), in order, unique."""
    seen: dict[str, None] = {}
    for t in tokens(text):
        if t in STOPWORDS or (len(t) < 2 and not t.isdigit()):
            continue
        seen.setdefault(t, None)
    return list(seen)


@dataclass
class Vocabulary:
    """Synonym groups (normalized phrases). A phrase belongs to at most one group."""

    groups: list[frozenset[str]] = field(default_factory=list)
    _index: dict[str, int] = field(default_factory=dict)

    def add_group(self, phrases: Iterable[str]) -> None:
        normalized = {normalize_phrase(p) for p in phrases if normalize_phrase(p)}
        if not normalized:
            return
        # Merge with existing groups sharing a phrase (keeps groups disjoint).
        overlapping = sorted({self._index[p] for p in normalized if p in self._index})
        for gi in overlapping:
            normalized |= self.groups[gi]
        for gi in reversed(overlapping):
            self.groups[gi] = frozenset()
        self.groups.append(frozenset(normalized))
        gi = len(self.groups) - 1
        for p in normalized:
            self._index[p] = gi

    def variants(self, phrase: str) -> frozenset[str]:
        """All normalized phrases equivalent to ``phrase`` (including itself)."""
        p = normalize_phrase(phrase)
        gi = self._index.get(p)
        if gi is None:
            return frozenset({p}) if p else frozenset()
        return self.groups[gi]

    def phrases(self) -> list[str]:
        """Multi-word phrases known to the vocabulary, longest first."""
        return sorted((p for p in self._index if " " in p), key=lambda p: (-len(p.split()), p))


# Negation cues (EN/FR). An occurrence preceded (within NEGATION_WINDOW tokens) by a cue
# does not count: "without human approval" does not satisfy "human approval".
NEGATION_CUES = frozenset(
    ["no", "not", "without", "never", "non", "sans", "pas", "aucun", "aucune", "jamais", "ni", "lack", "absence"]
)
NEGATION_WINDOW = 3


def contains_phrase(normalized_text: str, phrase: str) -> bool:
    """Whole-word containment of a normalized phrase in a space-padded normalized text."""
    return bool(phrase) and f" {phrase} " in normalized_text


def contains_affirmed(normalized_text: str, phrase: str) -> bool:
    """Like ``contains_phrase``, ignoring occurrences negated by a preceding cue word.

    A phrase that itself starts with a cue (e.g. "no human approval") is matched as is.
    """
    if not contains_phrase(normalized_text, phrase):
        return False
    if phrase.split()[0] in NEGATION_CUES:
        return True
    needle = f" {phrase} "
    start = normalized_text.find(needle)
    while start != -1:
        before = normalized_text[:start].split()[-NEGATION_WINDOW:]
        if not any(tok in NEGATION_CUES for tok in before):
            return True
        start = normalized_text.find(needle, start + 1)
    return False


def match_terms(normalized_text: str, terms: Iterable[str], vocabulary: Vocabulary) -> list[str]:
    """Terms (as written) found, affirmed, in the text — literally or through a synonym.

    A term found only through a synonym is reported once per synonym group, so that the
    result lists the evidence rather than every equivalent spelling.
    """
    literal: list[str] = []
    by_synonym: list[str] = []
    groups_seen: set[frozenset[str]] = set()
    for term in terms:
        term = str(term)
        own = normalize_phrase(term)
        group = vocabulary.variants(term)
        if contains_affirmed(normalized_text, own):
            literal.append(term)
            groups_seen.add(group)
    for term in terms:
        term = str(term)
        group = vocabulary.variants(term)
        if term in literal or group in groups_seen:
            continue
        if any(contains_affirmed(normalized_text, v) for v in group):
            by_synonym.append(term)
            groups_seen.add(group)
    return [str(t) for t in terms if str(t) in literal or str(t) in by_synonym]


def query_concepts(text: str, vocabulary: Vocabulary) -> list[frozenset[str]]:
    """Split a free-text query into concepts, each a set of equivalent normalized phrases.

    Known multi-word vocabulary phrases are recognised first (longest first), then the
    remaining meaningful tokens become single-word concepts.
    """
    norm = normalize(text)
    concepts: list[frozenset[str]] = []
    consumed = norm
    for phrase in vocabulary.phrases():
        if contains_phrase(consumed, phrase):
            concepts.append(vocabulary.variants(phrase))
            consumed = consumed.replace(f" {phrase} ", " | ")
    for tok in content_tokens(consumed.replace("|", " ")):
        concepts.append(vocabulary.variants(tok))
    unique: list[frozenset[str]] = []
    for c in concepts:
        if c and c not in unique:
            unique.append(c)
    return unique
