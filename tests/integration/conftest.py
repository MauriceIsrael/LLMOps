"""Integration tests conftest — autouse cache cleanup fixture for LadybugDB / Kùzu DB."""

import gc
import pytest

from mcp_server.db.kuzu_client import KuzuClient
from tools.adapters.ladybug_store import LadybugGraphStore


@pytest.fixture(autouse=True)
def _clear_graph_store_caches():
    yield
    LadybugGraphStore.clear_cache()
    KuzuClient.clear_cache()
    gc.collect()
