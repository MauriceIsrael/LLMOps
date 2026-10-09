"""Module helper pour le chargement et la liaison des blueprints d'architecture."""

from pathlib import Path
from typing import Any

from tools.elicitation.models.blueprint_schema import Blueprint, load_blueprint
from tools.elicitation.repository import ElicitationRepository
from tools.elicitation.resolve import database_path

__all__ = ["bind_blueprint", "load_blueprint", "Blueprint"]


def bind_blueprint(target: Any = None, engagement: str | None = None, blueprint: Any = None, db_path: str | Path | None = None) -> None:
    """Lie un blueprint à un engagement dans le repository."""
    from mcp_server.core.config import require_engagement

    engagement = require_engagement(engagement)
    if isinstance(target, ElicitationRepository):
        repo = target
        bp = blueprint
    else:
        bp = target or blueprint
        repo = ElicitationRepository(db_path=database_path(db_path, engagement))

    if bp is not None:
        repo.bind_blueprint_to_engagement(bp, engagement=engagement)
