"""Modèles de données du domaine Mailbox pour le rendu et le protocole."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class QuestionFrame:
    """Cadre contextuel d'une question élicitée."""

    canonical_subject: str
    glossary_terms: list[str] = field(default_factory=list)
    constrained_assets: list[str] = field(default_factory=list)  # Ex: ["P-012", "ADR-0011"]
    prior_answer: dict[str, Any] | None = None  # Ex: {"engagement": "other-eng", "value": "SAN NVMe", "confidence": "verified"}
    section_name: str = ""
    blocking_count: int = 1


@dataclass
class QuestionCardData:
    """Données pour le rendu d'une fiche Question."""

    question_id: str
    engagement: str
    section: str
    question_text: str
    why_it_matters: str
    expected_shape: str
    routed_to: str
    frame: QuestionFrame


@dataclass
class StatementData:
    """Données représentant un énoncé dans une fiche."""

    id: str
    subject: str
    predicate: str
    value: str
    unit: str = ""
    author: str = ""
    role: str = ""
    confidence: str = "verified"
    created_at: str = ""
    verbatim: str = ""
    based_on: list[str] = field(default_factory=list)



@dataclass
class ProposalCardData:
    """Données pour le rendu d'une fiche Proposal."""

    question_id: str
    engagement: str
    section: str
    statements: list[StatementData]
    verbatim: str


@dataclass
class ConflictCardData:
    """Données pour le rendu d'une fiche Conflict."""

    conflict_id: str
    engagement: str
    kind: str
    detail: str
    subject: str
    predicate: str
    statements: list[StatementData]
    advisory: str | None = None


@dataclass
class ArbitrationCardData:
    """Données pour le rendu d'une fiche Arbitration."""

    conflict_id: str
    engagement: str
    kept_statement: StatementData
    superseded_statement: StatementData
    arbitrated_by: str
    reason: str
