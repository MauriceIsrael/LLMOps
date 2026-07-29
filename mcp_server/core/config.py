"""Modèle de configuration du serveur MCP (ServerConfig).

Conforme à T1.3 de TPL-fixes-server-contract / ADR-0014.
"""

from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerConfig(BaseSettings):
    """Configuration du serveur MCP résolue à partir des variables d'environnement."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    plane: Literal["knowledge", "engagement"] = "knowledge"
    db_path: Path = Path("data/knowledge.kuzu")
    knowledge_db_path: Path = Path("data/knowledge.kuzu")
    engagements_dir: Path = Path("data/engagements")
    engagement: str | None = "nordwave-mcx-2027"
    app_name: str = "LLMOps Architecture KB"
    auth_token: str = "llmops-token-2026-sec-98a41f"
    host: str = "0.0.0.0"
    port: int = 8000
    dataset: str = "kuzu://data/knowledge.kuzu"


server_config = ServerConfig()
