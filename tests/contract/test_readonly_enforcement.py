"""Contract test for read-only database enforcement (P0-2 remediation)."""

import pytest

from tools.adapters.kuzu_store import make_graph_store

pytestmark = pytest.mark.deterministic


def test_readonly_store_rejects_cypher_writes(tmp_path):
    """Ensure a read_only=True database store rejects write operations."""
    db_file = tmp_path / "test_ro.lbug"

    # 1. Initialize schema in read-write mode
    rw_store = make_graph_store(db_file, read_only=False)
    rw_store.execute_cypher("CREATE NODE TABLE Item (id STRING, PRIMARY KEY(id));")
    rw_store.execute_cypher("CREATE (:Item {id: 'seed-1'});")
    res = rw_store.execute_cypher("MATCH (i:Item) RETURN count(i) as c;")
    assert res[0]["c"] == 1
    rw_store.close()

    # 2. Open in read-only mode and attempt write
    ro_store = make_graph_store(db_file, read_only=True)
    read_res = ro_store.execute_cypher("MATCH (i:Item) RETURN i.id as id;")
    assert len(read_res) == 1
    assert read_res[0]["id"] == "seed-1"

    with pytest.raises(Exception) as exc_info:
        ro_store.execute_cypher("CREATE (:Item {id: 'forbidden-write'});")

    err_msg = str(exc_info.value).lower()
    assert "read" in err_msg or "permission" in err_msg or "cannot" in err_msg
    ro_store.close()


def test_readonly_client_whitelist_and_literals(tmp_path):
    """Ensure ReadOnlyLadybugClient permits safe queries containing keywords in string literals and rejects forbidden keywords."""
    from mcp_server.core.db import ReadOnlyLadybugClient

    db_file = tmp_path / "test_client_ro.lbug"
    rw_store = make_graph_store(db_file, read_only=False)
    rw_store.execute_cypher("CREATE NODE TABLE Asset (id STRING, domain STRING, PRIMARY KEY(id));")
    rw_store.execute_cypher("CREATE (:Asset {id: 'a1', domain: 'data-merge-pipeline'});")
    rw_store.close()

    client = ReadOnlyLadybugClient(db_path=db_file)

    # 1. Query containing 'merge' inside literal string should SUCCEED
    query_with_literal = "MATCH (a:Asset) WHERE a.domain CONTAINS 'merge' RETURN a.id as id;"
    res = client.execute_cypher(query_with_literal)
    assert len(res) == 1
    assert res[0]["id"] == "a1"

    # 2. Query starting with forbidden write operations must be REJECTED
    forbidden_queries = [
        "CREATE (:Asset {id: 'hack'});",
        "MERGE (a:Asset {id: 'hack'}) RETURN a;",
        "DELETE (a:Asset);",
        "DROP TABLE Asset;",
        "COPY Asset FROM 'data.csv';",
        "EXPORT DATABASE 'backup';",
        "IMPORT DATABASE 'dump';",
        "INSTALL extension_xyz;",
        "LOAD EXTENSION 'xyz';",
        "ATTACH 'other.db' AS other;",
        "CALL custom_unsafe_procedure();",
    ]
    for bad_q in forbidden_queries:
        with pytest.raises(PermissionError):
            client.execute_cypher(bad_q)

    # 3. Safe CALL procedure is permitted (table_info)
    info_res = client.execute_cypher("CALL table_info('Asset') RETURN *;")
    assert isinstance(info_res, list)

    client.close()
