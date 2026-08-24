#!/usr/bin/env python3
"""Export graph database contents (nodes & relationships) to canonical JSON data files.

Usage:
  python scripts/export_graph.py --db data/knowledge.kuzu --out /tmp/export_knowledge/
  python scripts/export_graph.py --db data/engagements/nordwave-mcx-2027.kuzu --out /tmp/export_engagement/
"""

import argparse
import json
from pathlib import Path
from typing import Any

from tools.adapters.kuzu_store import make_graph_store

NODE_TABLES = [
    "Asset",
    "GlossaryTerm",
    "Subject",
    "Statement",
    "Question",
    "Conflict",
    "Uncertainty",
]

REL_TABLES = {
    # rel_name: (src_table, src_pk, dst_table, dst_pk)
    "SUPERSEDES": ("Asset", "id", "Asset", "id"),
    "REQUIRES": ("Asset", "id", "Asset", "id"),
    "DEFINES": ("Asset", "id", "GlossaryTerm", "term"),
    "ABOUT": ("Statement", "id", "Subject", "id"),
    "ANSWERS": ("Statement", "id", "Question", "id"),
    "TARGETS": ("Question", "id", "Subject", "id"),
    "INVOLVES": ("Conflict", "id", "Statement", "id"),
}


def export_graph(db_path: str, out_dir: str, backend: str = "kuzu") -> dict[str, Any]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    store = make_graph_store(db_path=db_path, read_only=True, backend=backend)

    # Discover tables in source DB
    tables_res = store.execute_cypher("CALL show_tables() RETURN name;")
    existing_tables = {r["name"] for r in tables_res if r and "name" in r}

    manifest = {
        "source_db": db_path,
        "backend": backend,
        "nodes": [],
        "relations": [],
    }

    # Export Node Tables
    for node_table in NODE_TABLES:
        if node_table not in existing_tables:
            continue

        query = f"MATCH (n:{node_table}) RETURN n.*"
        results = store.execute_cypher(query)

        cleaned_nodes = []
        for row in results:
            cleaned_row = {k.replace("n.", ""): v for k, v in row.items()}
            cleaned_nodes.append(cleaned_row)

        cleaned_nodes.sort(key=lambda x: str(x.get("id", x.get("term", ""))))

        node_file = out_path / f"nodes_{node_table}.json"
        node_file.write_text(
            json.dumps(cleaned_nodes, indent=2, sort_keys=True, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        manifest["nodes"].append({"table": node_table, "count": len(cleaned_nodes), "file": node_file.name})

    # Export Relation Tables
    for rel_table, (src_table, src_pk, dst_table, dst_pk) in REL_TABLES.items():
        if rel_table not in existing_tables:
            continue

        query = f"MATCH (a:{src_table})-[r:{rel_table}]->(b:{dst_table}) RETURN a.{src_pk} AS _src, b.{dst_pk} AS _dst, r.*"
        results = store.execute_cypher(query)

        cleaned_rels = []
        for row in results:
            cleaned_row = {k.replace("r.", ""): v for k, v in row.items()}
            cleaned_rels.append(cleaned_row)

        cleaned_rels.sort(key=lambda x: (str(x.get("_src", "")), str(x.get("_dst", ""))))

        rel_file = out_path / f"rels_{rel_table}.json"
        rel_file.write_text(
            json.dumps(cleaned_rels, indent=2, sort_keys=True, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        manifest["relations"].append({"table": rel_table, "count": len(cleaned_rels), "file": rel_file.name})

    manifest_file = out_path / "manifest.json"
    manifest_file.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )

    store.close()
    return manifest


if __name__ == "__main__":
    import os
    parser = argparse.ArgumentParser(description="Export graph database to data directory")
    parser.add_argument("--db", required=True, help="Path to source graph database")
    parser.add_argument("--out", required=True, help="Output directory for exported JSON files")
    parser.add_argument("--backend", default="kuzu", help="Source graph backend (default: kuzu)")

    args = parser.parse_args()
    summary = export_graph(args.db, args.out, args.backend)
    print(f"✅ Export completed to {args.out}: {summary['nodes']} nodes, {summary['relations']} relations")
    os._exit(0)
