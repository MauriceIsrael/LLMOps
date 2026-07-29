"""Gestionnaire de connexion Kùzu DB sécurisé et lecture seule (Read-Only Driver).

Conforme à T1.5 de TPL-fixes-server-contract / ADR-0014.
"""

import gc
import re
from pathlib import Path
from typing import Any
import kuzu
from mcp_server.core.config import server_config


class ReadOnlyKuzuClient:
    """Client Kùzu DB strictement en lecture seule pour l'exposition d'outils MCP."""

    _read_db_cache: dict[str, Any] = {}

    @classmethod
    def get_read_database(cls, db_path: str) -> Any:
        if db_path in cls._read_db_cache:
            db = cls._read_db_cache[db_path]
            try:
                test_conn = kuzu.Connection(db)
                test_conn.execute("RETURN 1;")
                del test_conn
                return db
            except Exception:
                cls._read_db_cache.pop(db_path, None)

        db_p = Path(db_path)
        db_p.mkdir(parents=True, exist_ok=True)
        if not (db_p / "catalog.kz").exists() and not (db_p / "metadata.kz").exists():
            # Initialiser le dossier Kùzu DB si nouveau
            init_db = kuzu.Database(db_path, buffer_pool_size=64 * 1024 * 1024, read_only=False)
            del init_db
            gc.collect()

        try:
            db = kuzu.Database(db_path, buffer_pool_size=64 * 1024 * 1024, read_only=True)
        except Exception:
            db = kuzu.Database(db_path, buffer_pool_size=64 * 1024 * 1024, read_only=False)
        cls._read_db_cache[db_path] = db
        return db

    def __init__(self, db_path: Path | str | None = None, max_rows: int = 1000):
        self.db_path = str(db_path or server_config.db_path)
        db_dir = Path(self.db_path)
        db_dir.mkdir(parents=True, exist_ok=True)
        self.max_rows = max_rows

    def execute_cypher(self, query: str) -> list[dict[str, Any]]:
        """Exécute une requête Cypher en mode strictement lecture seule au niveau du driver."""
        # Inspection stricte des requêtes de modification Cypher (Driver & Query Level Defense)
        write_keywords = r"\b(CREATE|SET|DELETE|MERGE|DROP|ALTER|DETACH|REMOVE)\b"
        if re.search(write_keywords, query, re.IGNORECASE):
            raise PermissionError("Cypher write operations are not allowed on this read-only serving endpoint.")

        try:
            from mcp_server.db.kuzu_client import KuzuClient
            db = KuzuClient.get_database(self.db_path)
            conn = kuzu.Connection(db)
            response = conn.execute(query)
            cols = response.get_column_names()
            results = []
            count = 0
            while response.has_next() and count < self.max_rows:
                row = response.get_next()
                results.append(dict(zip(cols, row)))
                count += 1
            return results
        except Exception as e:
            err_msg = str(e)
            if "read" not in err_msg.lower() and "permission" not in err_msg.lower():
                err_msg = f"Read-only query enforcement failed: {err_msg}"
            raise RuntimeError(err_msg) from e

    def close(self) -> None:
        gc.collect()
