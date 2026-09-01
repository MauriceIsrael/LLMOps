"""LadybugDB adapter implementing the GraphStore port interface."""

import gc
from pathlib import Path
from typing import Any

import ladybug as lb

from tools.ports.graph_store import GraphStore


class LadybugGraphStore(GraphStore):
    """Adapter wrapping LadybugDB to fulfill the GraphStore protocol."""

    _db_cache: dict[str, Any] = {}
    _conn_cache: dict[str, Any] = {}

    @classmethod
    def get_database(cls, db_path: str, read_only: bool = False) -> Any:
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

        try:
            db = lb.Database(
                db_path,
                buffer_pool_size=64 * 1024 * 1024,
                max_db_size=1024 * 1024 * 1024,
                read_only=False,
            )
        except Exception as e:
            if "wal" in str(e).lower() or "record type" in str(e).lower():
                wal_file = Path(f"{db_path}.wal")
                if wal_file.exists():
                    wal_file.unlink()
                db = lb.Database(
                    db_path,
                    buffer_pool_size=64 * 1024 * 1024,
                    max_db_size=1024 * 1024 * 1024,
                    read_only=False,
                )
            else:
                raise

        cls._db_cache[cache_key] = db
        return db

    @classmethod
    def clear_cache(cls, db_path: str | None = None) -> None:
        if db_path:
            p_str = str(db_path)
            keys_to_del = [k for k in cls._db_cache if p_str in k or k in p_str]
            for k in keys_to_del:
                db = cls._db_cache.pop(k, None)
                del db
            conn_keys = [k for k in cls._conn_cache if p_str in k or k in p_str]
            for k in conn_keys:
                conn = cls._conn_cache.pop(k, None)
                del conn
        else:
            cls._db_cache.clear()
            cls._conn_cache.clear()
        for _ in range(3):
            gc.collect()

    def __init__(self, db_path: str | Path, read_only: bool = False) -> None:
        p = Path(db_path)
        if p.is_dir() or p.suffix == ".kuzu" or p.name.endswith(".kuzu"):
            # LadybugDB requires a file path, whereas legacy Kuzu used a directory.
            self.db_path = str(p / "database.lbug")
        elif not p.suffix:
            self.db_path = str(p.with_suffix(".lbug"))
        else:
            self.db_path = str(p)

        self.read_only = read_only
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    @property
    def db(self) -> Any:
        return self.get_database(self.db_path, read_only=self.read_only)

    @property
    def conn(self) -> Any:
        if self.db_path not in self._conn_cache:
            self._conn_cache[self.db_path] = lb.Connection(self.db)
        return self._conn_cache[self.db_path]

    def execute_cypher(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        response = self.conn.execute(query, params) if params else self.conn.execute(query)
        cols = response.get_column_names()
        results = []
        while response.has_next():
            row = response.get_next()
            results.append(dict(zip(cols, row, strict=False)))
        del response
        return results

    def close(self) -> None:
        """Routine close does not purge shared process-level database cache."""
        pass

    def __enter__(self) -> "LadybugGraphStore":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
