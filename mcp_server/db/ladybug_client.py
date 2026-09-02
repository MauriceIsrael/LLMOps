"""LadybugDB client for MCP server Cypher query execution."""

from pathlib import Path
from typing import Any

from mcp_server.config import settings
from tools.adapters.ladybug_store import LadybugGraphStore


class LadybugClient:
    """Thread-safe client for LadybugDB delegating to LadybugGraphStore."""

    @classmethod
    def get_database(cls, db_path: str) -> Any:
        return LadybugGraphStore.get_database(db_path)

    @classmethod
    def clear_cache(cls, db_path: str | None = None) -> None:
        LadybugGraphStore.clear_cache(db_path)

    def __init__(self, db_path: Path | str | None = None, read_only: bool = True) -> None:
        self.store = LadybugGraphStore(db_path=db_path or settings.DB_PATH, read_only=read_only)
        self.db_path = self.store.db_path
        self.db = self.store.db
        self.conn = self.store.conn

    def execute_cypher(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        return self.store.execute_cypher(query, params)

    def close(self) -> None:
        self.store.close()

