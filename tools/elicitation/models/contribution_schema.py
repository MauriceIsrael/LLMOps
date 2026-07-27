"""Schéma Pydantic pour les contributions spontanées externes (Unsolicited Contributions)."""

from typing import Any

from pydantic import BaseModel, Field


class Contribution(BaseModel):
    """Structure d'une contribution spontanée externe."""

    id: str
    engagement: str
    contributor: str  # ex: external:m.okonkwo
    title: str
    material_text: str
    attachment_path: str | None = None
    relates_to_hint: str | None = None
    status: str = "submitted"  # submitted, triaged, crystallised, confirmed_by_author, accepted, declined, redirected, kb_promoted
    triage_decision: dict[str, Any] | None = None
    mapped_subjects: list[str] = Field(default_factory=list)
    unmapped_terms: list[str] = Field(default_factory=list)
    proposed_statements: list[dict[str, Any]] = Field(default_factory=list)
