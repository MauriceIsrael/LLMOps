"""Configuration centralisée du serveur FastMCP et de Kùzu DB."""

from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Charger automatiquement les variables d'environnement depuis le fichier .env
load_dotenv()


class Settings(BaseSettings):
    """Paramètres globaux du serveur FastMCP."""

    APP_NAME: str = "LLMOps-Architecture-KB"
    KB_DIR: Path = Path("data/kb")
    DB_PATH: Path = Path("data/kuzu_db")
    DEBUG: bool = False
    TRANSPORT: str = "stdio"  # "stdio" pour CLI/Cursor local, "sse" pour Docker/Cloud Run
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    class Config:
        env_prefix = "LLMOPS_"
        extra = "ignore"


settings = Settings()

