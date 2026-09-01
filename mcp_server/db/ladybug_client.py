"""LadybugDB client for MCP server Cypher query execution."""

import gc
from pathlib import Path
from typing import Any

import ladybug

from mcp_server.config import settings


class LadybugClient:
    """Thread-safe client for LadybugDB with singleton Database cache per file path."""

    _db_cache: dict[str, Any] = {}

    @classmethod
    def get_database(cls, db_path: str) -> Any:
        if db_path in cls._db_cache:
            db = cls._db_cache[db_path]
            try:
                test_conn = ladybug.Connection(db)
                test_conn.execute("RETURN 1;")
                del test_conn
                return db
            except Exception:
                cls._db_cache.pop(db_path, None)

        db = ladybug.Database(
            db_path,
            buffer_pool_size=64 * 1024 * 1024,
            max_db_size=1024 * 1024 * 1024,
            read_only=False,
        )
        cls._db_cache[db_path] = db
        return db

    def __init__(self, db_path: Path | str | None = None, read_only: bool = True) -> None:
        p = Path(db_path or settings.DB_PATH)
        if p.is_dir() or p.suffix == ".kuzu" or p.name.endswith(".kuzu") or not p.suffix:
            p.mkdir(parents=True, exist_ok=True)
            self.db_path = str(p / "database.lbug")
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            self.db_path = str(p)

        self.db = LadybugClient.get_database(self.db_path)
        self.conn = ladybug.Connection(self.db)

    @classmethod
    def clear_cache(cls, db_path: str | None = None) -> None:
        if db_path and db_path in cls._db_cache:
            cls._db_cache.pop(db_path, None)
        else:
            cls._db_cache.clear()
        gc.collect()

    def execute_cypher(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Executes a parameterized Cypher query and returns the results as a list of dictionaries."""
        try:
            if params:
                query_result = self.conn.execute(query, params)
            else:
                query_result = self.conn.execute(query)

            columns = query_result.get_column_names()
            rows = []
            while query_result.has_next():
                row = query_result.get_next()
                rows.append(dict(zip(columns, row, strict=False)))
            del query_result
            return rows
        except Exception as e:
            raise RuntimeError(f"Cypher execution failed: {e}\nQuery: {query}\nParams: {params}") from e

    def close(self) -> None:
        if hasattr(self, "conn") and self.conn:
            del self.conn
            self.conn = None
        if hasattr(self, "db") and self.db:
            del self.db
            self.db = None
        gc.collect()

