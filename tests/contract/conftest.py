"""Fixtures for contract tests — dual-backend parameterization (kuzu + ladybug)."""

import gc
from collections.abc import Generator
from pathlib import Path

import pytest

from tools.adapters.kuzu_store import make_graph_store
from tools.ports.graph_store import GraphStore

BACKENDS = ["kuzu", "ladybug"]


@pytest.fixture(params=BACKENDS)
def graph_store(request: pytest.FixtureRequest, tmp_path: Path) -> Generator[GraphStore, None, None]:
    """Parametrized fixture yielding a clean GraphStore instance for each backend."""
    backend_name = request.param
    db_path = tmp_path / f"test_db_{backend_name}"
    store = make_graph_store(db_path=db_path, read_only=False, backend=backend_name)
    yield store
    try:
        store.close()
    except Exception:
        pass
    if backend_name == "kuzu":
        from mcp_server.db.kuzu_client import KuzuClient
        KuzuClient.clear_cache()
    gc.collect()


@pytest.fixture(autouse=True)
def _clear_kuzu_cache():
    """Release Kùzu mmap resources after each test to avoid exhausting virtual memory."""
    yield
    from mcp_server.db.kuzu_client import KuzuClient
    KuzuClient.clear_cache()
    gc.collect()
