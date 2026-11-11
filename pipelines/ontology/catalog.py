"""Catalog metatheory and clause-to-leaf governance utilities for Archinex ontology (Issue #184).

Provides:
- Formal predicate definitions including 'satisfies_clause'.
- Bidirectional clause-leaf resolution:
  * Given a clause URN, find all leaves satisfying it.
  * Given a leaf URN, find all clauses governing it.
- Clause index generator (by_clause, by_leaf).
- Mathematical integrity validator for URN links.
"""

from __future__ import annotations

import re
from typing import Any

VALID_PREDICATES: tuple[str, ...] = (
    "requires_aspect",
    "implemented_by",
    "depends_on",
    "constrains",
    "conflicts_with",
    "satisfies_clause",
)

PREDICATE_SATISFIES_CLAUSE = "satisfies_clause"

CLAUSE_URN_PATTERN = re.compile(r"^urn:(archinex|llmops):kb:clause:[A-Za-z0-9_.:-]+$")
LEAF_URN_PATTERN = re.compile(r"^urn:(archinex|llmops):ontology:[A-Za-z0-9_.:-]+$")


def build_clause_index(
    entities: dict[str, Any], triplets: list[dict[str, Any]]
) -> dict[str, dict[str, list[str]]]:
    """Build bidirectional index between clause URNs and technical leaf URNs."""
    by_clause: dict[str, list[str]] = {}
    by_leaf: dict[str, list[str]] = {}

    # 1. From leaf entities governed_by_clauses metadata
    for urn, entity in entities.items():
        if entity.get("kind") == "leaf":
            clauses = entity.get("governed_by_clauses") or []
            if clauses:
                by_leaf[urn] = list(sorted(set(clauses)))
                for c in clauses:
                    by_clause.setdefault(c, [])
                    if urn not in by_clause[c]:
                        by_clause[c].append(urn)

    # 2. From satisfies_clause triplets (ensure full synchronization)
    for t in triplets:
        if t.get("predicate") == PREDICATE_SATISFIES_CLAUSE:
            leaf_urn = str(t.get("subject", ""))
            clause_urn = str(t.get("object", ""))
            if leaf_urn and clause_urn:
                by_leaf.setdefault(leaf_urn, [])
                if clause_urn not in by_leaf[leaf_urn]:
                    by_leaf[leaf_urn].append(clause_urn)
                by_clause.setdefault(clause_urn, [])
                if leaf_urn not in by_clause[clause_urn]:
                    by_clause[clause_urn].append(leaf_urn)

    # Sort deterministically
    sorted_by_clause = {k: sorted(v) for k, v in sorted(by_clause.items())}
    sorted_by_leaf = {k: sorted(v) for k, v in sorted(by_leaf.items())}

    return {
        "by_clause": sorted_by_clause,
        "by_leaf": sorted_by_leaf,
    }


def resolve_leaves_by_clause(
    catalog: dict[str, Any], clause_urn: str
) -> dict[str, Any]:
    """Retrieve all technical leaves that satisfy a given doctrinal clause URN."""
    entities = catalog.get("entities", {})
    triplets = catalog.get("triplets", [])
    index = catalog.get("clause_index") or build_clause_index(entities, triplets)

    leaf_urns = index.get("by_clause", {}).get(clause_urn, [])

    matching_entities = {
        urn: entities[urn] for urn in leaf_urns if urn in entities
    }
    matching_triplets = [
        t
        for t in triplets
        if t.get("predicate") == PREDICATE_SATISFIES_CLAUSE
        and t.get("object") == clause_urn
    ]

    return {
        "status": "ok",
        "experimental": True,
        "clause": clause_urn,
        "satisfying_leaves": sorted(leaf_urns),
        "entities": matching_entities,
        "triplets": matching_triplets,
    }


def resolve_clauses_by_leaf(
    catalog: dict[str, Any], leaf_urn: str
) -> dict[str, Any]:
    """Retrieve all doctrinal clauses that justify a given technical leaf URN."""
    entities = catalog.get("entities", {})
    triplets = catalog.get("triplets", [])
    index = catalog.get("clause_index") or build_clause_index(entities, triplets)

    clause_urns = index.get("by_leaf", {}).get(leaf_urn, [])

    entity = entities.get(leaf_urn)
    matching_triplets = [
        t
        for t in triplets
        if t.get("predicate") == PREDICATE_SATISFIES_CLAUSE
        and t.get("subject") == leaf_urn
    ]

    return {
        "status": "ok",
        "experimental": True,
        "leaf": leaf_urn,
        "governing_clauses": sorted(clause_urns),
        "entity": entity,
        "triplets": matching_triplets,
    }


def validate_clause_leaf_integrity(catalog: dict[str, Any]) -> list[str]:
    """Validate mathematical end-to-end integrity between leaf entities and doctrinal clauses.

    Checks:
    - Every satisfies_clause triplet has subject in entities (with kind == 'leaf').
    - Every satisfies_clause triplet has object matching a valid clause URN.
    - Every satisfies_clause triplet has a non-empty rationale.
    - Consistency: for each clause in entity['governed_by_clauses'], a corresponding
      satisfies_clause triplet exists.
    - Reverse consistency: for each satisfies_clause triplet, the clause appears in
      entity['governed_by_clauses'].

    Returns:
        List of error messages, or an empty list if perfectly valid.
    """
    errors: list[str] = []
    entities = catalog.get("entities", {})
    triplets = catalog.get("triplets", [])

    triplet_pairs: set[tuple[str, str]] = set()

    for t in triplets:
        t_id = t.get("id", "unknown")
        pred = t.get("predicate")
        if pred == PREDICATE_SATISFIES_CLAUSE:
            sub = t.get("subject", "")
            obj = t.get("object", "")
            rationale = t.get("rationale", "")

            if not sub or sub not in entities:
                errors.append(f"Triplet {t_id}: subject '{sub}' not found in entities")
                continue

            entity = entities[sub]
            if entity.get("kind") != "leaf":
                errors.append(f"Triplet {t_id}: subject '{sub}' is kind '{entity.get('kind')}', must be 'leaf'")

            if not obj or not CLAUSE_URN_PATTERN.match(obj):
                errors.append(f"Triplet {t_id}: object '{obj}' is not a valid clause URN")

            if not rationale or not str(rationale).strip():
                errors.append(f"Triplet {t_id}: missing or empty rationale")

            triplet_pairs.add((sub, obj))

            # Verify clause in leaf.governed_by_clauses
            gov_clauses = entity.get("governed_by_clauses") or []
            if obj not in gov_clauses:
                errors.append(
                    f"Triplet {t_id}: clause '{obj}' not declared in leaf '{sub}' governed_by_clauses"
                )

    # Reverse check: every clause in leaf.governed_by_clauses must have a triplet
    for urn, entity in entities.items():
        if entity.get("kind") == "leaf":
            gov_clauses = entity.get("governed_by_clauses") or []
            for clause in gov_clauses:
                if not CLAUSE_URN_PATTERN.match(clause):
                    errors.append(f"Leaf '{urn}': invalid clause URN '{clause}' in governed_by_clauses")
                if (urn, clause) not in triplet_pairs:
                    errors.append(
                        f"Leaf '{urn}': clause '{clause}' declared in governed_by_clauses but missing satisfies_clause triplet"
                    )

    return errors
