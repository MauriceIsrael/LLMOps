"""Client Kùzu DB pour l'exécution des requêtes du serveur FastMCP."""

import gc
from pathlib import Path
from typing import Any

import kuzu

from mcp_server.config import settings


class KuzuClient:
    """Client de lecture/requêtage thread-safe pour Kùzu DB avec singleton Database par chemin."""

    _db_cache: dict[str, Any] = {}

    @classmethod
    def get_database(cls, db_path: str) -> Any:
        if db_path in cls._db_cache:
            db = cls._db_cache[db_path]
            try:
                test_conn = kuzu.Connection(db)
                test_conn.execute("RETURN 1;")
                del test_conn
                return db
            except Exception:
                cls._db_cache.pop(db_path, None)

        db = kuzu.Database(db_path, buffer_pool_size=64 * 1024 * 1024, read_only=False)
        cls._db_cache[db_path] = db
        return db

    def __init__(self, db_path: Path | str | None = None, read_only: bool = True) -> None:
        self.db_path = str(db_path or settings.DB_PATH)
        db_dir = Path(self.db_path)
        if db_dir.suffix and db_dir.suffix != ".kuzu":
            db_dir.parent.mkdir(parents=True, exist_ok=True)
        else:
            db_dir.mkdir(parents=True, exist_ok=True)

        self.db = KuzuClient.get_database(self.db_path)
        self.conn = kuzu.Connection(self.db)

    @classmethod
    def clear_cache(cls, db_path: str | None = None) -> None:
        if db_path and db_path in cls._db_cache:
            cls._db_cache.pop(db_path, None)
        else:
            cls._db_cache.clear()
        gc.collect()

    def execute_cypher(self, query: str) -> list[dict[str, Any]]:
        """Exécute une requête Cypher et retourne les résultats sous forme de liste de dictionnaires."""
        conn = kuzu.Connection(self.db)
        response = conn.execute(query)
        cols = response.get_column_names()
        results = []
        while response.has_next():
            row = response.get_next()
            results.append(dict(zip(cols, row)))
        return results

    def close(self) -> None:
        """Ferme la connexion et libère les ressources Kùzu DB."""
        if hasattr(self, "conn"):
            try:
                del self.conn
            except Exception:
                pass
        if hasattr(self, "db"):
            try:
                del self.db
            except Exception:
                pass
        gc.collect()


