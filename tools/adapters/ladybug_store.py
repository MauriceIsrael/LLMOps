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
        cache_key = str(Path(db_path).resolve())
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
                cache_key,
                buffer_pool_size=64 * 1024 * 1024,
                max_db_size=1024 * 1024 * 1024,
                read_only=False,
            )
        except Exception as e:
            if "wal" in str(e).lower() or "record type" in str(e).lower():
                wal_file = Path(f"{cache_key}.wal")
                if wal_file.exists():
                    wal_file.unlink()
                db = lb.Database(
                    cache_key,
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
            canon = str(Path(db_path).resolve())
            keys_to_del = [k for k in cls._db_cache if k.startswith(canon)]
            for k in keys_to_del:
                db = cls._db_cache.pop(k, None)
                del db
            conn_keys = [k for k in cls._conn_cache if k.startswith(canon)]
            for k in conn_keys:
                conn = cls._conn_cache.pop(k, None)
                del conn
        else:
            cls._db_cache.clear()
            cls._conn_cache.clear()
        gc.collect()

    def __init__(self, db_path: str | Path, read_only: bool = False) -> None:
        p = Path(db_path).resolve()
        if p.suffix == ".kuzu" or p.name.endswith(".kuzu"):
            lbug_companion = p.with_suffix(".lbug")
            if lbug_companion.exists() and lbug_companion.is_file():
                self.db_path = str(lbug_companion)
            elif (p / "database.lbug").exists():
                self.db_path = str(p / "database.lbug")
            else:
                self.db_path = str(lbug_companion)
        elif p.is_dir():
            if (p / "database.lbug").exists():
                self.db_path = str(p / "database.lbug")
            else:
                self.db_path = str(p.with_suffix(".lbug"))
        elif not p.suffix:
            self.db_path = str(p.with_suffix(".lbug"))
        else:
            self.db_path = str(p)

        self.read_only = read_only
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.db = self.get_database(self.db_path, read_only=self.read_only)
        if self.db_path in self._conn_cache:
            self.conn = self._conn_cache[self.db_path]
        else:
            self.conn = lb.Connection(self.db)
            self._conn_cache[self.db_path] = self.conn

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
