"""Client Kùzu DB pour l'exécution des requêtes du serveur FastMCP."""

from pathlib import Path
from typing import Any

import kuzu

from mcp_server.config import settings


class KuzuClient:
    """Client de lecture/requêtage thread-safe pour Kùzu DB avec cache de connexion par chemin."""

    _cache: dict[str, tuple[Any, Any]] = {}

    def __init__(self, db_path: Path | str | None = None, read_only: bool = True) -> None:
        self.db_path = str(db_path or settings.DB_PATH)
        db_dir = Path(self.db_path)

        if self.db_path not in KuzuClient._cache:
            db_dir.mkdir(parents=True, exist_ok=True)
            db = kuzu.Database(self.db_path, read_only=False)
            conn = kuzu.Connection(db)
            KuzuClient._cache[self.db_path] = (db, conn)

        self.db, self.conn = KuzuClient._cache[self.db_path]

    @classmethod
    def clear_cache(cls, db_path: str | None = None) -> None:
        if db_path and db_path in cls._cache:
            db, conn = cls._cache.pop(db_path)
            del conn
            del db
        else:
            for p, (db, conn) in list(cls._cache.items()):
                del conn
                del db
            cls._cache.clear()

    def execute_cypher(self, query: str) -> list[dict[str, Any]]:
        """Exécute une requête Cypher et retourne les résultats sous forme de liste de dictionnaires."""
        try:
            response = self.conn.execute(query)
            cols = response.get_column_names()
            results = []
            while response.has_next():
                row = response.get_next()
                results.append(dict(zip(cols, row)))
            return results
        except Exception as e:
            return [{"error": str(e)}]

    def close(self) -> None:
        """Ferme la connexion et libère les ressources Kùzu DB."""
        if hasattr(self, "conn"):
            del self.conn
        if hasattr(self, "db"):
            del self.db
        KuzuClient.clear_cache(self.db_path)


