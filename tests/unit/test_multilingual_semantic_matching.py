"""Tests for multilingual FR/EN semantic and doctrine matching (Issue #132)."""

from pathlib import Path

import pytest
import yaml

from pipelines.doctrine.checks import (
    CheckClause,
    Matcher,
    evaluate_clause,
    expand_clause_terms,
)
from pipelines.doctrine.text import Vocabulary, expand_terms, normalize

KB_DIR = Path(__file__).parent.parent.parent / "data" / "kb"


@pytest.fixture
def kb_vocabulary() -> Vocabulary:
    vocab = Vocabulary()
    synonyms_file = KB_DIR / "glossary" / "synonyms.yaml"
    assert synonyms_file.is_file()
    data = yaml.safe_load(synonyms_file.read_text(encoding="utf-8")) or {}
    for group in data.get("groups", []):
        if isinstance(group, list):
            vocab.add_group(str(t) for t in group)
    return vocab


def test_bilingual_synonym_groups_loaded(kb_vocabulary: Vocabulary):
    # Verify core telecom and resilience terminology groups
    four_eyes_variants = kb_vocabulary.variants("four-eyes")
    assert any("double validation" in v for v in four_eyes_variants)
    assert any("quatre yeux" in v for v in four_eyes_variants)

    holdover_variants = kb_vocabulary.variants("holdover")
    assert any("autonomie de synchronisation" in v for v in holdover_variants)

    jamming_variants = kb_vocabulary.variants("jamming")
    assert any("brouillage" in v for v in jamming_variants)

    backup_room_variants = kb_vocabulary.variants("back-up room")
    assert any("salle de repli" in v for v in backup_room_variants)

    sepp_variants = kb_vocabulary.variants("sepp")
    assert any("roaming sepp" in v for v in sepp_variants)


def test_expand_terms_and_clause_terms(kb_vocabulary: Vocabulary):
    terms = ["four-eyes", "jamming"]
    expanded = expand_terms(terms, kb_vocabulary)
    assert "double validation" in expanded
    assert "brouillage gnss" in expanded or "brouillage" in expanded

    clause = CheckClause(
        id="C-TEST-01",
        kind="requires",
        when=Matcher(terms_any=("back-up room",)),
        expect=Matcher(terms_any=("four-eyes",)),
        message="A backup room requires four-eyes approval.",
    )
    expanded_clause = expand_clause_terms(clause, kb_vocabulary)
    assert any("salle de repli" in t for t in expanded_clause["when_terms_any"])
    assert any("double validation" in t for t in expanded_clause["expect_terms_any"])


def test_french_option_matches_english_clause(kb_vocabulary: Vocabulary):
    clause = CheckClause(
        id="C-EN-01",
        kind="requires",
        when=Matcher(terms_any=("back-up room",)),
        expect=Matcher(terms_any=("four-eyes",)),
        message="Operations in backup room must require four-eyes validation.",
    )

    # Option in French that satisfies both when and expect
    opt_compliant = "Nous activons la salle de repli secondaire avec obligation de double validation des accès."
    res = evaluate_clause(clause, normalize(opt_compliant), kb_vocabulary)
    assert res is not None
    assert res.verdict == "supports"
    assert "back-up room" in res.matched_terms
    assert "four-eyes" in res.matched_terms

    # Option in French that triggers when but violates expect
    opt_violating = "Nous activons la salle de repli avec un opérateur unique sans contrôle supplémentaire."
    res = evaluate_clause(clause, normalize(opt_violating), kb_vocabulary)
    assert res is not None
    assert res.verdict == "violates"


def test_english_option_matches_french_clause(kb_vocabulary: Vocabulary):
    clause = CheckClause(
        id="C-FR-01",
        kind="requires",
        when=Matcher(terms_any=("brouillage gnss",)),
        expect=Matcher(terms_any=("autonomie de synchronisation",)),
        message="En cas de brouillage GNSS, une autonomie de synchronisation est requise.",
    )

    # Option in English that satisfies both when and expect
    opt_compliant = "The architecture protects against GNSS jamming with high precision holdover capability."
    res = evaluate_clause(clause, normalize(opt_compliant), kb_vocabulary)
    assert res is not None
    assert res.verdict == "supports"
    assert "brouillage gnss" in res.matched_terms
    assert "autonomie de synchronisation" in res.matched_terms

    # Option in English that triggers when but lacks holdover
    opt_violating = "Standard GPS receiver vulnerable to jamming with no backup clock."
    res = evaluate_clause(clause, normalize(opt_violating), kb_vocabulary)
    assert res is not None
    assert res.verdict == "violates"

