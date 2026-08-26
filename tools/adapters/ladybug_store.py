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
    def get_database(cls, db_path: str, read_only: bool = False) -> Any:
        if lb is None:
            raise RuntimeError("Neither 'ladybug' nor fallback 'kuzu' package is installed.")

        cache_key = f"{db_path}_{read_only}"
        if cache_key in cls._db_cache:
            db = cls._db_cache[cache_key]
            try:
                test_conn = lb.Connection(db)
                test_conn.execute("RETURN 1;")
                del test_conn
                return db
            except Exception:
                cls._db_cache.pop(cache_key, None)

        db = lb.Database(db_path, buffer_pool_size=64 * 1024 * 1024, read_only=read_only)
        cls._db_cache[cache_key] = db
        return db

    @classmethod
    def clear_cache(cls, db_path: str | None = None) -> None:
        if db_path:
            keys_to_del = [k for k in cls._db_cache if k.startswith(str(db_path))]
            for k in keys_to_del:
                db = cls._db_cache.pop(k, None)
                del db
        else:
            cls._db_cache.clear()
        gc.collect()

    def __init__(self, db_path: str | Path, read_only: bool = False) -> None:
        p = Path(db_path)
        if p.is_dir() or p.suffix == ".kuzu" or p.name.endswith(".kuzu"):
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

        self.db = self.get_database(self.db_path, read_only=self.read_only)
        self.conn = lb.Connection(self.db)

    def execute_cypher(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        response = self.conn.execute(query, params) if params else self.conn.execute(query)
        cols = response.get_column_names()
        results = []
        while response.has_next():
            row = response.get_next()
            results.append(dict(zip(cols, row)))
        return results

    def close(self) -> None:
        if hasattr(self, "conn") and self.conn is not None:
            try:
                del self.conn
            except Exception:
                pass
            self.conn = None
        if hasattr(self, "db") and self.db is not None:
            try:
                del self.db
            except Exception:
                pass
            self.db = None

    def __enter__(self) -> "LadybugGraphStore":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
