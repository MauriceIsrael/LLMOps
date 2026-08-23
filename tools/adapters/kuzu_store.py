"""Kùzu DB adapter implementing the GraphStore port interface."""

import os
from pathlib import Path
from typing import Any

from mcp_server.db.kuzu_client import KuzuClient
from tools.ports.graph_store import GraphStore


class KuzuGraphStore(GraphStore):
    """Adapter wrapping KuzuClient to fulfill the GraphStore protocol."""

    def __init__(self, db_path: str | Path, read_only: bool = False) -> None:
        self.db_path = str(db_path)
        self.read_only = read_only
        self._client = KuzuClient(db_path=self.db_path, read_only=read_only)

    def execute_cypher(self, query: str) -> list[dict[str, Any]]:
        return self._client.execute_cypher(query)

    def close(self) -> None:
        if hasattr(self, "_client") and self._client:
            self._client.close()

    def __enter__(self) -> "KuzuGraphStore":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()


def make_graph_store(
    db_path: str | Path, read_only: bool = False, backend: str | None = None
) -> GraphStore:
    """Factory function for creating GraphStore instances based on environment or argument."""
    selected_backend = (backend or os.getenv("GRAPH_BACKEND", "kuzu")).lower()

    if selected_backend == "kuzu":
        return KuzuGraphStore(db_path=db_path, read_only=read_only)
    elif selected_backend == "ladybug":
        from tools.adapters.ladybug_store import LadybugGraphStore

        return LadybugGraphStore(db_path=db_path, read_only=read_only)
    else:
        raise ValueError(
            f"Unknown graph backend '{selected_backend}'. Supported options: 'kuzu', 'ladybug'."
        )
