#!/usr/bin/env python3
"""Import exported graph data into a target graph database (LadybugDB or Kùzu DB).

Usage:
  python scripts/import_graph.py --dir /tmp/export_knowledge/ --db data/knowledge.lbug --backend ladybug
  python scripts/import_graph.py --dir /tmp/export_engagement/ --db data/engagements/nordwave-mcx-2027.lbug --backend ladybug
"""

import argparse
import json
from pathlib import Path
from typing import Any

from pipelines.ingestion.graph_loader import KuzuGraphLoader
from tools.adapters.kuzu_store import make_graph_store
from tools.elicitation.db_schema import ElicitationSchemaInitializer


def _esc(val: Any) -> str:
    """Escape single quotes and newlines for Cypher query parameters."""
    return str(val or "").replace("'", "\\'").replace("\n", " ").replace("\r", " ")


def import_graph(in_dir: str, db_path: str, backend: str = "ladybug") -> dict[str, Any]:
    in_path = Path(in_dir)
    manifest_file = in_path / "manifest.json"

    if not manifest_file.exists():
        raise FileNotFoundError(f"Manifest file not found in export directory: {manifest_file}")

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    store = make_graph_store(db_path=db_path, read_only=False, backend=backend)

    # Initialize schema based on plane type
    node_tables = [entry["table"] for entry in manifest.get("nodes", [])]

    if "Asset" in node_tables or "GlossaryTerm" in node_tables:
        loader = KuzuGraphLoader(db_path=db_path, graph_store=store)
        del loader

    if any(t in node_tables for t in ["Subject", "Statement", "Question", "Conflict", "Uncertainty"]):
        initializer = ElicitationSchemaInitializer(db_path=db_path, graph_store=store)
        del initializer

    summary = {"backend": backend, "nodes_imported": 0, "relations_imported": 0}

    # Import Node Tables
    for entry in manifest.get("nodes", []):
        table_name = entry["table"]
        node_file = in_path / entry["file"]
        if not node_file.exists():
            continue

        nodes_data = json.loads(node_file.read_text(encoding="utf-8"))

        for node in nodes_data:
            if table_name == "Asset":
                query = f"""
                MERGE (a:Asset {{id: '{_esc(node.get("id"))}'}})
                SET a.title = '{_esc(node.get("title"))}',
                    a.type = '{_esc(node.get("type"))}',
                    a.status = '{_esc(node.get("status"))}',
                    a.confidence = '{_esc(node.get("confidence"))}',
                    a.phase = '{_esc(node.get("phase"))}',
                    a.domain = '{_esc(node.get("domain"))}',
                    a.last_reviewed = '{_esc(node.get("last_reviewed"))}',
                    a.owner = '{_esc(node.get("owner"))}',
                    a.source_path = '{_esc(node.get("source_path"))}';
                """
            elif table_name == "GlossaryTerm":
                query = f"""
                MERGE (g:GlossaryTerm {{term: '{_esc(node.get("term"))}'}})
                SET g.definition = '{_esc(node.get("definition"))}';
                """
            elif table_name == "Subject":
                query = f"""
                MERGE (s:Subject {{id: '{_esc(node.get("id"))}'}})
                SET s.name = '{_esc(node.get("name"))}',
                    s.engagement = '{_esc(node.get("engagement"))}',
                    s.definition = '{_esc(node.get("definition"))}',
                    s.level = '{_esc(node.get("level"))}',
                    s.origin = '{_esc(node.get("origin"))}',
                    s.updated_at = '{_esc(node.get("updated_at"))}';
                """
            elif table_name == "Statement":
                query = f"""
                MERGE (st:Statement {{id: '{_esc(node.get("id"))}'}})
                SET st.engagement = '{_esc(node.get("engagement"))}',
                    st.section = '{_esc(node.get("section"))}',
                    st.subject = '{_esc(node.get("subject"))}',
                    st.predicate = '{_esc(node.get("predicate"))}',
                    st.value = '{_esc(node.get("value"))}',
                    st.unit = '{_esc(node.get("unit"))}',
                    st.author = '{_esc(node.get("author"))}',
                    st.role = '{_esc(node.get("role"))}',
                    st.confidence = '{_esc(node.get("confidence"))}',
                    st.verbatim = '{_esc(node.get("verbatim"))}',
                    st.status = '{_esc(node.get("status"))}',
                    st.based_on = '{_esc(node.get("based_on"))}',
                    st.created_at = '{_esc(node.get("created_at"))}';
                """
            elif table_name == "Question":
                query = f"""
                MERGE (q:Question {{id: '{_esc(node.get("id"))}'}})
                SET q.engagement = '{_esc(node.get("engagement"))}',
                    q.gap_type = '{_esc(node.get("gap_type"))}',
                    q.section = '{_esc(node.get("section"))}',
                    q.question = '{_esc(node.get("question"))}',
                    q.why_it_matters = '{_esc(node.get("why_it_matters"))}',
                    q.expected_shape = '{_esc(node.get("expected_shape"))}',
                    q.routed_to = '{_esc(node.get("routed_to"))}',
                    q.status = '{_esc(node.get("status"))}',
                    q.created_at = '{_esc(node.get("created_at"))}';
                """
            elif table_name == "Conflict":
                query = f"""
                MERGE (c:Conflict {{id: '{_esc(node.get("id"))}'}})
                SET c.kind = '{_esc(node.get("kind"))}',
                    c.detail = '{_esc(node.get("detail"))}',
                    c.status = '{_esc(node.get("status"))}',
                    c.origin = '{_esc(node.get("origin"))}',
                    c.resolution = '{_esc(node.get("resolution"))}',
                    c.arbitrated_by = '{_esc(node.get("arbitrated_by"))}';
                """
            elif table_name == "Uncertainty":
                query = f"""
                MERGE (u:Uncertainty {{id: '{_esc(node.get("id"))}'}})
                SET u.engagement = '{_esc(node.get("engagement"))}',
                    u.subject = '{_esc(node.get("subject"))}',
                    u.text = '{_esc(node.get("text"))}';
                """
            else:
                continue

            store.execute_cypher(query)
            summary["nodes_imported"] += 1

    # Import Relation Tables
    for entry in manifest.get("relations", []):
        table_name = entry["table"]
        rel_file = in_path / entry["file"]
        if not rel_file.exists():
            continue

        rels_data = json.loads(rel_file.read_text(encoding="utf-8"))

        for rel in rels_data:
            src, dst = _esc(rel.get("_src")), _esc(rel.get("_dst"))

            if table_name == "SUPERSEDES":
                query = f"MATCH (a1:Asset {{id: '{src}'}}), (a2:Asset {{id: '{dst}'}}) MERGE (a1)-[:SUPERSEDES]->(a2);"
            elif table_name == "REQUIRES":
                query = f"MATCH (a1:Asset {{id: '{src}'}}), (a2:Asset {{id: '{dst}'}}) MERGE (a1)-[:REQUIRES]->(a2);"
            elif table_name == "DEFINES":
                query = f"MATCH (a:Asset {{id: '{src}'}}), (g:GlossaryTerm {{term: '{dst}'}}) MERGE (a)-[:DEFINES]->(g);"
            elif table_name == "ABOUT":
                query = f"MATCH (st:Statement {{id: '{src}'}}), (sub:Subject {{id: '{dst}'}}) MERGE (st)-[:ABOUT]->(sub);"
            elif table_name == "ANSWERS":
                query = f"MATCH (st:Statement {{id: '{src}'}}), (q:Question {{id: '{dst}'}}) MERGE (st)-[:ANSWERS]->(q);"
            elif table_name == "TARGETS":
                query = f"MATCH (q:Question {{id: '{src}'}}), (sub:Subject {{id: '{dst}'}}) MERGE (q)-[:TARGETS]->(sub);"
            elif table_name == "INVOLVES":
                query = f"MATCH (c:Conflict {{id: '{src}'}}), (st:Statement {{id: '{dst}'}}) MERGE (c)-[:INVOLVES]->(st);"
            else:
                continue

            store.execute_cypher(query)
            summary["relations_imported"] += 1

    store.close()
    return summary


if __name__ == "__main__":
    import os
    parser = argparse.ArgumentParser(description="Import graph data into LadybugDB or Kùzu DB")
    parser.add_argument("--dir", required=True, help="Input directory containing exported JSON files")
    parser.add_argument("--db", required=True, help="Target database path")
    parser.add_argument("--backend", default="ladybug", help="Target graph backend (default: ladybug)")

    args = parser.parse_args()
    summary = import_graph(args.dir, args.db, args.backend)
    print(f"✅ Import completed to {args.db}: {summary['nodes_imported']} nodes, {summary['relations_imported']} relations imported")
    os._exit(0)
