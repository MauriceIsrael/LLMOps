"""Fixtures for contract tests — ensure Kùzu DB cache is cleared between tests."""

import gc

import pytest

from mcp_server.db.kuzu_client import KuzuClient


@pytest.fixture(autouse=True)
def _clear_kuzu_cache():
    """Release Kùzu mmap resources after each test to avoid exhausting virtual memory."""
    yield
    KuzuClient.clear_cache()
    gc.collect()
