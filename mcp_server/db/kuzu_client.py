"""Client Kùzu DB pour l'exécution des requêtes du serveur FastMCP."""

from pathlib import Path
from typing import Any
import kuzu
from mcp_server.config import settings


class KuzuClient:
    """Client de lecture/requêtage thread-safe pour Kùzu DB."""

    def __init__(self, db_path: Path | str | None = None, read_only: bool = True) -> None:
        self.db_path = str(db_path or settings.DB_PATH)
        db_dir = Path(self.db_path)

        if read_only and db_dir.exists():
            try:
                self.db = kuzu.Database(self.db_path, read_only=True)
            except Exception:
                self.db = kuzu.Database(self.db_path, read_only=False)
        else:
            db_dir.mkdir(parents=True, exist_ok=True)
            self.db = kuzu.Database(self.db_path, read_only=False)

        self.conn = kuzu.Connection(self.db)



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
