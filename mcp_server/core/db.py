"""Connection router, pooling, and database discovery manager under ADR-0015.

Layout:
  data/knowledge.kuzu                 (knowledge plane: assets, glossary)
  data/engagements/<id>.kuzu          (engagement plane: subjects, statements, questions)
"""

import gc
import re
from pathlib import Path
from typing import Any

from mcp_server.core.auth import authorise
from mcp_server.core.config import server_config
from tools.adapters.kuzu_store import make_graph_store


def validate_engagement_id(engagement_id: str) -> str:
    """Validates engagement identifier format.
    Must be lowercase, alphanumeric and hyphens only ([a-z0-9-]+).
    Rejects path separators (/ or \\) and dot segments (..).
    """
    if not engagement_id or not isinstance(engagement_id, str):
        raise ValueError("Engagement identifier must be a non-empty string.")
    if not re.match(r"^[a-z0-9-]+$", engagement_id):
        raise ValueError(
            f"Invalid engagement identifier '{engagement_id}'. Must contain only lowercase alphanumeric characters and hyphens."
        )
    return engagement_id


def get_engagement_path(engagement_id: str, base_dir: Path | str | None = None) -> Path:
    """Resolves an engagement identifier to its .kuzu database path."""
    valid_id = validate_engagement_id(engagement_id)
    eng_dir = Path(base_dir or server_config.engagements_dir)
    return eng_dir / f"{valid_id}.kuzu"


def discover_engagements(base_dir: Path | str | None = None) -> list[dict[str, Any]]:
    """Dynamically discovers engagement databases present in data/engagements/."""
    eng_dir = Path(base_dir or server_config.engagements_dir)
    if not eng_dir.exists():
        return []

    discovered = []
    for path in eng_dir.glob("*.kuzu"):
        eng_id = path.stem
        if re.match(r"^[a-z0-9-]+$", eng_id):
            discovered.append({
                "id": eng_id,
                "dataset": str(path),
                "path": path,
            })
    return sorted(discovered, key=lambda x: x["id"])


class ReadOnlyKuzuClient:
    """Read-only driver wrapper around graph DB connections implementing GraphStore protocol."""

    _read_db_cache: dict[str, Any] = {}

    @classmethod
    def get_read_database(cls, db_path: str | Path) -> Any:
        db_path_str = str(db_path)
        from mcp_server.db.kuzu_client import KuzuClient
        return KuzuClient.get_database(db_path_str)

    def __init__(self, db_path: Path | str | None = None, max_rows: int = 1000):
        self.db_path = str(db_path or server_config.knowledge_db_path)
        db_dir = Path(self.db_path)
        db_dir.mkdir(parents=True, exist_ok=True)
        self.max_rows = max_rows

    def execute_cypher(self, query: str) -> list[dict[str, Any]]:
        """Executes a read-only Cypher query."""
        write_keywords = r"\b(CREATE|SET|DELETE|MERGE|DROP|ALTER|DETACH|REMOVE)\b"
        if re.search(write_keywords, query, re.IGNORECASE):
            raise PermissionError("Cypher write operations are not allowed on this read-only serving endpoint.")

        try:
            store = make_graph_store(self.db_path, read_only=True)
            results = store.execute_cypher(query)
            if self.max_rows and len(results) > self.max_rows:
                return results[: self.max_rows]
            return results
        except Exception as e:
            err_msg = str(e)
            if "read" not in err_msg.lower() and "permission" not in err_msg.lower():
                err_msg = f"Read-only query enforcement failed: {err_msg}"
            raise RuntimeError(err_msg) from e

    def close(self) -> None:
        gc.collect()


def open_connection(scope: str | None = None, caller: str = "default_user") -> ReadOnlyKuzuClient:
    """Resolves a scope to a read-only connection.
    Order of operations:
    1. Authorisation first (before checking path existence).
    2. Identifier resolution second.
    3. Connection third.
    """
    if scope is None:
        return ReadOnlyKuzuClient(db_path=server_config.knowledge_db_path)

    # 1. Authorisation first
    authorise(caller, scope)

    # 2. Resolution second
    path = get_engagement_path(scope)
    if not path.exists():
        raise FileNotFoundError(f"Engagement database not found for scope '{scope}' at {path}")

    # 3. Connection third
    return ReadOnlyKuzuClient(db_path=path)
