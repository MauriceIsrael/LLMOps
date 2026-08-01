"""Tests unitaires pour le client Kùzu DB."""

import pytest

from mcp_server.db.kuzu_client import KuzuClient


@pytest.fixture
def temp_kuzu_client(tmp_path) -> KuzuClient:
    db_dir = tmp_path / "kuzu_test_db"
    return KuzuClient(db_path=db_dir)


@pytest.mark.deterministic
def test_kuzu_client_query_execution(temp_kuzu_client: KuzuClient) -> None:
    temp_kuzu_client.execute_cypher("CREATE NODE TABLE Test (id INT64, PRIMARY KEY(id));")
    temp_kuzu_client.execute_cypher("CREATE (t:Test {id: 42});")
    res = temp_kuzu_client.execute_cypher("MATCH (t:Test) RETURN t.id;")
    assert len(res) == 1
    assert res[0]["t.id"] == 42
