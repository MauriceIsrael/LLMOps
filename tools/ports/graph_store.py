"""Port interface for graph database access."""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class GraphStore(Protocol):
    """Abstract interface for graph database operations (Kùzu / LadybugDB)."""

    def execute_cypher(self, query: str) -> list[dict[str, Any]]:
        """Execute a Cypher query and return results as a list of dictionaries."""
        ...

    def close(self) -> None:
        """Close connections and release database resources."""
        ...
