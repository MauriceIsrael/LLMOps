"""Gateway from validated ontology entries to existing glossary/vocabulary format (Issue #171).

Projects validated ontology entries into Vocabulary groups so that
doctrine search, context injection and check_option recognize them.
"""

from __future__ import annotations

from pathlib import Path

from pipelines.doctrine.text import Vocabulary
from pipelines.ontology.loader import load_ontology_entries


def project_ontology_to_vocabulary(
    ontology_dir: str | Path = "data/kb/ontology",
    vocab: Vocabulary | None = None,
) -> Vocabulary:
    """Project validated ontology entries into a Vocabulary instance.

    Only entries with status 'validated' are projected.
    Draft and rejected entries are ignored.
    """
    if vocab is None:
        vocab = Vocabulary()

    p = Path(ontology_dir)
    if not p.is_dir():
        return vocab

    entries = load_ontology_entries(p)
    for entry in entries:
        if entry.status == "validated":
            phrases = [entry.term] + list(entry.synonyms)
            vocab.add_group(phrases)

    return vocab

