"""Fonctions déterministes de rendu Markdown pour les 4 fiches (Cards) de la Mailbox."""

import hashlib
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from tools.elicitation.mailbox.models import (
    ArbitrationCardData,
    ConflictCardData,
    ProposalCardData,
    QuestionCardData,
)

TEMPLATES_DIR = Path(__file__).parent / "templates"
env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), trim_blocks=True, lstrip_blocks=True)


def compute_sha(text: str) -> str:
    """Calcule le hash SHA-256 tronqué à 6 caractères pour l'idempotence."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:6]


def render_question_card(data: QuestionCardData) -> str:
    """Rend la fiche Question au format Markdown portable avec marqueur d'idempotence."""
    template = env.get_template("question.md.j2")
    # Premier passage sans le hash pour calculer le SHA
    raw_content = template.render(
        engagement=data.engagement,
        question_id=data.question_id,
        question_text=data.question_text,
        why_it_matters=data.why_it_matters,
        section=data.section,
        expected_shape=data.expected_shape,
        frame=data.frame,
        content_hash="000000",
    )
    sha = compute_sha(raw_content)
    return template.render(
        engagement=data.engagement,
        question_id=data.question_id,
        question_text=data.question_text,
        why_it_matters=data.why_it_matters,
        section=data.section,
        expected_shape=data.expected_shape,
        frame=data.frame,
        content_hash=sha,
    )


def render_proposal_card(data: ProposalCardData) -> str:
    """Rend la fiche Proposal au format Markdown portable."""
    template = env.get_template("proposal.md.j2")
    raw_content = template.render(
        engagement=data.engagement,
        question_id=data.question_id,
        statements=data.statements,
        verbatim=data.verbatim,
        content_hash="000000",
    )
    sha = compute_sha(raw_content)
    return template.render(
        engagement=data.engagement,
        question_id=data.question_id,
        statements=data.statements,
        verbatim=data.verbatim,
        content_hash=sha,
    )


def render_conflict_card(data: ConflictCardData) -> str:
    """Rend la fiche Conflict au format Markdown portable."""
    template = env.get_template("conflict.md.j2")
    raw_content = template.render(
        engagement=data.engagement,
        conflict_id=data.conflict_id,
        subject=data.subject,
        predicate=data.predicate,
        detail=data.detail,
        statements=data.statements,
        advisory=data.advisory,
        content_hash="000000",
    )
    sha = compute_sha(raw_content)
    return template.render(
        engagement=data.engagement,
        conflict_id=data.conflict_id,
        subject=data.subject,
        predicate=data.predicate,
        detail=data.detail,
        statements=data.statements,
        advisory=data.advisory,
        content_hash=sha,
    )


def render_arbitration_card(data: ArbitrationCardData) -> str:
    """Rend la fiche Arbitration au format Markdown portable."""
    template = env.get_template("arbitration.md.j2")
    raw_content = template.render(
        engagement=data.engagement,
        conflict_id=data.conflict_id,
        kept_statement=data.kept_statement,
        superseded_statement=data.superseded_statement,
        arbitrated_by=data.arbitrated_by,
        reason=data.reason,
        content_hash="000000",
    )
    sha = compute_sha(raw_content)
    return template.render(
        engagement=data.engagement,
        conflict_id=data.conflict_id,
        kept_statement=data.kept_statement,
        superseded_statement=data.superseded_statement,
        arbitrated_by=data.arbitrated_by,
        reason=data.reason,
        content_hash=sha,
    )


def render_maturity_board(engagement: str, board_data: list[dict[str, Any]]) -> str:
    """Rend le tableau de maturité (Maturity Board) de manière déterministe et idempotente."""
    template = env.get_template("maturity_board.md.j2")
    raw_content = template.render(
        engagement=engagement,
        board=board_data,
        content_hash="000000",
    )
    sha = compute_sha(raw_content)
    return template.render(
        engagement=engagement,
        board=board_data,
        content_hash=sha,
    )

