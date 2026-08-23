"""LadybugDB adapter implementing the GraphStore port interface."""

import gc
from pathlib import Path
from typing import Any

from tools.ports.graph_store import GraphStore

try:
    import ladybug as lb
except ImportError:
    try:
        import kuzu as lb  # Fallback for transition if ladybug package is not yet compiled/installed
    except ImportError:
        lb = None


class LadybugGraphStore(GraphStore):
    """Adapter wrapping LadybugDB to fulfill the GraphStore protocol."""

    _db_cache: dict[str, Any] = {}

    @classmethod
    def get_database(cls, db_path: str) -> Any:
        if lb is None:
            raise RuntimeError("Neither 'ladybug' nor fallback 'kuzu' package is installed.")

        if db_path in cls._db_cache:
            db = cls._db_cache[db_path]
            try:
                test_conn = lb.Connection(db)
                test_conn.execute("RETURN 1;")
                del test_conn
                return db
            except Exception:
                cls._db_cache.pop(db_path, None)

        db = lb.Database(db_path, buffer_pool_size=64 * 1024 * 1024, read_only=False)
        cls._db_cache[db_path] = db
        return db

    @classmethod
    def clear_cache(cls, db_path: str | None = None) -> None:
        if db_path and db_path in cls._db_cache:
            cls._db_cache.pop(db_path, None)
        else:
            cls._db_cache.clear()
        gc.collect()

    def __init__(self, db_path: str | Path, read_only: bool = False) -> None:
        p = Path(db_path)
        if p.is_dir():
            # LadybugDB requires a file path, whereas Kuzu uses a directory.
            self.db_path = str(p / "database.lbug")
        elif not p.suffix:
            self.db_path = str(p.with_suffix(".lbug"))
        else:
            self.db_path = str(p)

        self.read_only = read_only
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        if lb is None:
            raise RuntimeError("LadybugDB driver ('ladybug') is not installed.")

        self.db = LadybugGraphStore.get_database(self.db_path)
        self.conn = lb.Connection(self.db)

    def execute_cypher(self, query: str) -> list[dict[str, Any]]:
        conn = lb.Connection(self.db)
        response = conn.execute(query)
        cols = response.get_column_names()
        results = []
        while response.has_next():
            row = response.get_next()
            results.append(dict(zip(cols, row)))
        return results

    def close(self) -> None:
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

    def __enter__(self) -> "LadybugGraphStore":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
