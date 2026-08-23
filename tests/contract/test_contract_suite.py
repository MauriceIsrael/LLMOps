"""Contract tests for GraphStore backends (Kùzu & LadybugDB).

Tests core Cypher DDL, DML, MERGE idempotency, graph traversal, and null handling.
Runs against all configured backends via the graph_store fixture.
"""

import pytest

from tools.ports.graph_store import GraphStore


@pytest.mark.deterministic
def test_contract_ddl_and_show_tables(graph_store: GraphStore):
    """Verify DDL creation and table discovery via CALL show_tables()."""
    graph_store.execute_cypher(
        "CREATE NODE TABLE Person (id STRING, name STRING, age INT64, PRIMARY KEY(id));"
    )
    graph_store.execute_cypher(
        "CREATE NODE TABLE Company (id STRING, title STRING, PRIMARY KEY(id));"
    )
    graph_store.execute_cypher(
        "CREATE REL TABLE WORKS_AT (FROM Person TO Company);"
    )

    tables = graph_store.execute_cypher("CALL show_tables() RETURN name;")
    table_names = {t["name"] for t in tables if t and "name" in t}

    assert "Person" in table_names
    assert "Company" in table_names
    assert "WORKS_AT" in table_names


@pytest.mark.deterministic
def test_contract_merge_idempotency(graph_store: GraphStore):
    """Verify MERGE creates a node on first call and updates on subsequent calls."""
    graph_store.execute_cypher(
        "CREATE NODE TABLE Item (id STRING, name STRING, score INT64, PRIMARY KEY(id));"
    )

    # First MERGE (Insert)
    graph_store.execute_cypher(
        "MERGE (i:Item {id: 'item-1'}) SET i.name = 'Widget', i.score = 10;"
    )
    res1 = graph_store.execute_cypher("MATCH (i:Item) RETURN count(i.id) as cnt;")
    assert res1[0]["cnt"] == 1

    # Second MERGE (Update existing)
    graph_store.execute_cypher(
        "MERGE (i:Item {id: 'item-1'}) SET i.name = 'Widget', i.score = 20;"
    )
    res2 = graph_store.execute_cypher("MATCH (i:Item {id: 'item-1'}) RETURN i.score as score;")
    assert res2[0]["score"] == 20

    res_count = graph_store.execute_cypher("MATCH (i:Item) RETURN count(i.id) as cnt;")
    assert res_count[0]["cnt"] == 1


@pytest.mark.deterministic
def test_contract_graph_traversal(graph_store: GraphStore):
    """Verify graph traversal over node and relationship tables."""
    graph_store.execute_cypher("CREATE NODE TABLE Asset (id STRING, title STRING, PRIMARY KEY(id));")
    graph_store.execute_cypher("CREATE REL TABLE SUPERSEDES (FROM Asset TO Asset);")

    graph_store.execute_cypher("CREATE (a:Asset {id: 'ADR-001', title: 'Monolith'});")
    graph_store.execute_cypher("CREATE (a:Asset {id: 'ADR-002', title: 'Microservices'});")
    graph_store.execute_cypher(
        "MATCH (a1:Asset {id: 'ADR-002'}), (a2:Asset {id: 'ADR-001'}) MERGE (a1)-[:SUPERSEDES]->(a2);"
    )

    query = "MATCH (a1:Asset)-[:SUPERSEDES]->(a2:Asset) RETURN a1.id as src, a2.id as dst;"
    rows = graph_store.execute_cypher(query)

    assert len(rows) == 1
    assert rows[0]["src"] == "ADR-002"
    assert rows[0]["dst"] == "ADR-001"


@pytest.mark.deterministic
def test_contract_optional_match_and_nulls(graph_store: GraphStore):
    """Verify OPTIONAL MATCH and NULL handling."""
    graph_store.execute_cypher("CREATE NODE TABLE Subject (id STRING, name STRING, PRIMARY KEY(id));")
    graph_store.execute_cypher("CREATE NODE TABLE Statement (id STRING, val STRING, PRIMARY KEY(id));")
    graph_store.execute_cypher("CREATE REL TABLE ABOUT (FROM Statement TO Subject);")

    graph_store.execute_cypher("CREATE (s:Subject {id: 'sub-1', name: 'Auth'});")
    graph_store.execute_cypher("CREATE (st:Statement {id: 'st-1', val: 'OAuth2'});")

    # OPTIONAL MATCH with no relationship present
    rows = graph_store.execute_cypher(
        "MATCH (st:Statement {id: 'st-1'}) OPTIONAL MATCH (st)-[:ABOUT]->(sub:Subject) RETURN st.id as st_id, sub.name as sub_name;"
    )

    assert len(rows) == 1
    assert rows[0]["st_id"] == "st-1"
    assert rows[0]["sub_name"] is None


@pytest.mark.deterministic
def test_contract_alter_table(graph_store: GraphStore):
    """Verify ALTER TABLE ADD column behavior."""
    graph_store.execute_cypher("CREATE NODE TABLE Feature (id STRING, PRIMARY KEY(id));")
    graph_store.execute_cypher("CREATE (f:Feature {id: 'feat-1'});")

    graph_store.execute_cypher("ALTER TABLE Feature ADD status STRING DEFAULT 'active';")
    rows = graph_store.execute_cypher("MATCH (f:Feature {id: 'feat-1'}) RETURN f.status as status;")

    assert len(rows) == 1
    assert rows[0]["status"] in ("active", None, "")
