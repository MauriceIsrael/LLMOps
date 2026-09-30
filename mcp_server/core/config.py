"""Modèle de configuration du serveur MCP unifié (ServerConfig).

Conforme à T1.3 de TPL-fixes-server-contract / ADR-0014.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerConfig(BaseSettings):
    """Configuration du serveur MCP unifiée résolue à partir des variables d'environnement."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Supporte indifféremment LLMOPS_PLANE ou PLANE
    plane: Literal["knowledge", "engagement", "all"] = Field(
        default="all",
        validation_alias="LLMOPS_PLANE",
    )
    knowledge_db_path: Path = Field(
        default=Path("data/knowledge.lbug"),
        validation_alias="LLMOPS_KNOWLEDGE_DB_PATH",
    )
    db_path: Path = Field(
        default=Path("data/knowledge.lbug"),
        validation_alias="LLMOPS_DB_PATH",
    )
    engagements_dir: Path = Field(
        default=Path("data/engagements"),
        validation_alias="LLMOPS_ENGAGEMENTS_DIR",
    )
    # Default engagement and blueprint of this deployment. No project is hard-coded: they
    # come from the environment or .env (the demo sets them, see Makefile / Dockerfile).
    engagement: str | None = Field(
        default=None,
        validation_alias="LLMOPS_ENGAGEMENT",
    )
    blueprint: str | None = Field(
        default=None,
        validation_alias="LLMOPS_BLUEPRINT",
    )
    kb_dir: Path = Field(
        default=Path("data/kb"),
        validation_alias="LLMOPS_KB_DIR",
    )
    app_name: str = Field(
        default="LLMOps Architecture KB",
        validation_alias="LLMOPS_APP_NAME",
    )
    host: str = Field(
        default="0.0.0.0",
        validation_alias="LLMOPS_HOST",
    )
    port: int = Field(
        default=8000,
        validation_alias="PORT",
    )
    transport: str = Field(
        default="stdio",
        validation_alias="LLMOPS_TRANSPORT",
    )
    env: str = Field(
        default="development",
        validation_alias="LLMOPS_ENV",
    )
    auth_token: str | None = Field(
        default=None,
        validation_alias="LLMOPS_AUTH_TOKEN",
    )
    dataset: str = "ladybug://data/knowledge.lbug"

    # Propriétés de compatibilité majuscules pour settings
    @property
    def DB_PATH(self) -> Path:  # noqa: N802
        return self.knowledge_db_path

    @property
    def KB_DIR(self) -> Path:  # noqa: N802
        return self.kb_dir

    @property
    def TRANSPORT(self) -> str:  # noqa: N802
        return self.transport

    @property
    def HOST(self) -> str:  # noqa: N802
        return self.host

    @property
    def PORT(self) -> int:  # noqa: N802
        return self.port

    @property
    def AUTH_TOKEN(self) -> str | None:  # noqa: N802
        return self.auth_token

    @AUTH_TOKEN.setter
    def AUTH_TOKEN(self, value: str | None) -> None:  # noqa: N802
        self.auth_token = value

    @property
    def APP_NAME(self) -> str:  # noqa: N802
        return self.app_name

    @property
    def DEBUG(self) -> bool:  # noqa: N802
        return self.env == "development"


server_config = ServerConfig()


class DeploymentDefaultMissing(ValueError):  # noqa: N818
    """A command or tool needs an engagement / blueprint and none is configured."""


def resolve_engagement(engagement: str | None = None) -> str | None:
    """Explicit engagement, else ``LLMOPS_ENGAGEMENT`` (environment, then .env); None if unset."""
    import os

    return engagement or os.getenv("LLMOPS_ENGAGEMENT") or server_config.engagement or None


def require_engagement(engagement: str | None = None) -> str:
    eng = resolve_engagement(engagement)
    if not eng:
        raise DeploymentDefaultMissing(
            "No engagement given: pass one explicitly or set LLMOPS_ENGAGEMENT (environment or .env)."
        )
    return eng


def resolve_blueprint_path(blueprint: str | None = None) -> Path | None:
    """Blueprint file from an explicit id or path, else ``LLMOPS_BLUEPRINT``; None if unset.

    An identifier (``BLU-...``) resolves to ``<kb_dir>/blueprints/<id>.yaml``.
    """
    import os

    value = blueprint or os.getenv("LLMOPS_BLUEPRINT") or server_config.blueprint
    if not value:
        return None
    if value.endswith((".yaml", ".yml")) or "/" in value:
        return Path(value)
    return Path(server_config.kb_dir) / "blueprints" / f"{value}.yaml"


def require_blueprint_path(blueprint: str | None = None) -> Path:
    path = resolve_blueprint_path(blueprint)
    if path is None:
        raise DeploymentDefaultMissing(
            "No blueprint given: pass one explicitly or set LLMOPS_BLUEPRINT (environment or .env)."
        )
    return path


def resolve_blueprint_id(blueprint: str | None = None) -> str | None:
    """Blueprint identifier (file stem) from an explicit id or path, else ``LLMOPS_BLUEPRINT``."""
    path = resolve_blueprint_path(blueprint)
    return path.stem if path else None
