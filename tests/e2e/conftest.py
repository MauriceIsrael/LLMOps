"""End-to-end scenarios of the reference demo (examples/). Only tests/e2e may read examples/."""

import gc

import pytest

from mcp_server.db.kuzu_client import KuzuClient
from tools.adapters.ladybug_store import LadybugGraphStore


@pytest.fixture(autouse=True)
def _clear_graph_store_caches():
    """Release cached database handles after each test so that the scenarios, which copy
    database files between acts, always see checkpointed data (same as tests/integration)."""
    yield
    LadybugGraphStore.clear_cache()
    KuzuClient.clear_cache()
    gc.collect()
