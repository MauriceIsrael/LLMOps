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
from mcp_server.core.exceptions import EngagementNotFound, QueryRejected, SchemaError
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
    """Resolves an engagement identifier to its .lbug (or legacy .kuzu) database path."""
    valid_id = validate_engagement_id(engagement_id)
    eng_dir = Path(base_dir or server_config.engagements_dir)
    lbug_path = eng_dir / f"{valid_id}.lbug"
    if lbug_path.exists():
        return lbug_path
    kuzu_path = eng_dir / f"{valid_id}.kuzu"
    if kuzu_path.exists():
        return kuzu_path
    return lbug_path


def discover_engagements(base_dir: Path | str | None = None) -> list[dict[str, Any]]:
    """Dynamically discovers engagement databases present in data/engagements/."""
    eng_dir = Path(base_dir or server_config.engagements_dir)
    if not eng_dir.exists():
        return []

    discovered: dict[str, dict[str, Any]] = {}
    for path in eng_dir.glob("*.lbug"):
        eng_id = path.stem
        if re.match(r"^[a-z0-9-]+$", eng_id):
            discovered[eng_id] = {
                "id": eng_id,
                "dataset": str(path),
                "path": path,
            }
    for path in eng_dir.glob("*.kuzu"):
        eng_id = path.stem
        if eng_id not in discovered and re.match(r"^[a-z0-9-]+$", eng_id):
            discovered[eng_id] = {
                "id": eng_id,
                "dataset": str(path),
                "path": path,
            }
    return sorted(discovered.values(), key=lambda x: x["id"])


class ReadOnlyLadybugClient:
    """Read-only driver wrapper around graph DB connections implementing GraphStore protocol."""

    _read_db_cache: dict[str, Any] = {}

    @classmethod
    def get_read_database(cls, db_path: str | Path) -> Any:
        db_path_str = str(db_path)
        from mcp_server.db.ladybug_client import LadybugClient
        return LadybugClient.get_database(db_path_str)

    def __init__(self, db_path: Path | str | None = None, max_rows: int = 1000):
        self.db_path = str(db_path or server_config.knowledge_db_path)
        p = Path(self.db_path)
        if p.suffix and p.suffix != ".kuzu":
            p.parent.mkdir(parents=True, exist_ok=True)
        else:
            p.mkdir(parents=True, exist_ok=True)
        self.max_rows = max_rows

    @staticmethod
    def _strip_comments_and_strings(query: str) -> str:
        # Strip line comments // ... and /* ... */
        q = re.sub(r"//.*$", "", query, flags=re.MULTILINE)
        q = re.sub(r"/\*[\s\S]*?\*/", "", q)
        # Strip string literals single and double quoted
        q = re.sub(r"'[^'\\]*(?:\\.[^'\\]*)*'", "''", q)
        q = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', q)
        return q

    def execute_cypher(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Executes a read-only Cypher query with strict whitelist & blacklist defense in depth."""
        cleaned = self._strip_comments_and_strings(query).strip()
        if not cleaned:
            return []

        # 1. Premier mot-clé significatif (liste blanche structurelle)
        first_token_match = re.match(r"^([A-Za-z]+)", cleaned)
        if not first_token_match:
            raise QueryRejected("Invalid Cypher query format.")
        first_keyword = first_token_match.group(1).upper()
        allowed_initial_keywords = {"MATCH", "RETURN", "WITH", "UNWIND", "CALL"}
        if first_keyword not in allowed_initial_keywords:
            raise QueryRejected(
                f"Cypher statement starting with '{first_keyword}' is not permitted on this read-only endpoint."
            )

        # Si CALL, vérifier que la procédure est autorisée en lecture
        if first_keyword == "CALL":
            call_match = re.match(r"^CALL\s+([A-Za-z0-9_]+)", cleaned, re.IGNORECASE)
            proc_name = call_match.group(1).lower() if call_match else ""
            allowed_procedures = {"table_info", "show_tables"}
            if proc_name not in allowed_procedures:
                raise QueryRejected(f"CALL procedure '{proc_name}' is not permitted.")

        # 2. Mots-clés interdits d'écriture et d'administration (hors littéraux de chaîne)
        forbidden_keywords = (
            r"\b(CREATE|SET|DELETE|MERGE|DROP|ALTER|DETACH|REMOVE|COPY|EXPORT|IMPORT|INSTALL|LOAD|ATTACH)\b"
        )
        if re.search(forbidden_keywords, cleaned, re.IGNORECASE):
            raise QueryRejected(
                "Cypher write, administrative, or data-transfer operations are not allowed on this read-only serving endpoint."
            )

        # Injecter une clause LIMIT dans la requête elle-même si absente
        query_to_exec = query.strip().rstrip(";")
        if self.max_rows and not re.search(r"\bLIMIT\b", query_to_exec, re.IGNORECASE):
            query_to_exec = f"{query_to_exec} LIMIT {self.max_rows}"

        store = make_graph_store(self.db_path, read_only=True)
        try:
            results = store.execute_cypher(query_to_exec, params)
            if self.max_rows and len(results) > self.max_rows:
                return results[: self.max_rows]
            return results
        except PermissionError:
            raise
        except Exception as e:
            err_msg = str(e)
            if "binder exception" in err_msg.lower() or "does not exist" in err_msg.lower():
                raise SchemaError(f"Database schema resolution error: {err_msg}") from e
            if "read" not in err_msg.lower() and "permission" not in err_msg.lower():
                err_msg = f"Read-only query enforcement failed: {err_msg}"
            raise RuntimeError(err_msg) from e

    def close(self) -> None:
        gc.collect()


# Backward compatibility alias
ReadOnlyKuzuClient = ReadOnlyLadybugClient


def open_connection(scope: str | None = None, caller: str | None = None) -> ReadOnlyLadybugClient:
    """Resolves a scope to a read-only connection.
    Order of operations:
    1. Authorisation first (resolves context caller if caller is None).
    2. Identifier resolution second.
    3. Connection third.
    """
    if scope is None:
        return ReadOnlyKuzuClient(db_path=server_config.knowledge_db_path)

    # 1. Authorisation first
    authorise(caller=caller, engagement=scope)

    # 2. Resolution second
    path = get_engagement_path(scope)
    if not path.exists():
        raise EngagementNotFound(scope, f"Engagement database not found for scope '{scope}' at {path}")

    # 3. Connection third
    return ReadOnlyKuzuClient(db_path=path)
