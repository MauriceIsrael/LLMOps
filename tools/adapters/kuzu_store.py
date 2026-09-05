"""Compatibility shim re-exporting LadybugGraphStore as KuzuGraphStore."""

from pathlib import Path

from tools.adapters.ladybug_store import LadybugGraphStore
from tools.ports.graph_store import GraphStore

# Backward compatibility alias
KuzuGraphStore = LadybugGraphStore


def make_graph_store(
    db_path: str | Path | None = "data/kuzu_db", read_only: bool = False, backend: str | None = None
) -> GraphStore:
    """Factory function returning the native LadybugGraphStore instance."""
    return LadybugGraphStore(db_path=str(db_path or "data/kuzu_db"), read_only=read_only)


__all__ = ["GraphStore", "KuzuGraphStore", "LadybugGraphStore", "make_graph_store"]
