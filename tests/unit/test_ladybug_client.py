"""Tests unitaires pour le client LadybugDB."""

import pytest

from mcp_server.db.ladybug_client import LadybugClient


@pytest.fixture
def temp_ladybug_client(tmp_path) -> LadybugClient:
    db_dir = tmp_path / "ladybug_test_db"
    return LadybugClient(db_path=db_dir)


@pytest.mark.deterministic
def test_ladybug_client_query_execution(temp_ladybug_client: LadybugClient) -> None:
    temp_ladybug_client.execute_cypher("CREATE NODE TABLE Test (id INT64, PRIMARY KEY(id));")
    temp_ladybug_client.execute_cypher("CREATE (t:Test {id: 42});")
    res = temp_ladybug_client.execute_cypher("MATCH (t:Test) RETURN t.id;")
    assert len(res) == 1
    assert res[0]["t.id"] == 42

