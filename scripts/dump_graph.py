#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

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

EXCLUDED_FIELDS = {
    "updated_at",
    "created_at",
    "extracted_at",
    "reviewed_at",
    "superseded_at",
}


def dump_graph(db_path: str, output_path: str | None = None, backend: str | None = None) -> None:
    if backend is None:
        backend = "ladybug" if (str(db_path).endswith(".lbug") or Path(db_path).is_file()) else "kuzu"

    store = make_graph_store(db_path=db_path, read_only=True, backend=backend)

    # Discover which tables actually exist (ADR-0015: planes are physically separate)
    existing = set()
    try:
        rows = store.execute_cypher("CALL show_tables() RETURN name;")
        existing = {r["name"] for r in rows if r and "name" in r}
    except Exception:
        pass

    data = {
        "nodes": {},
        "relations": {},
        "_meta": {
            "tables": sorted(existing),
            "excluded_fields": sorted(list(EXCLUDED_FIELDS)),
        },
    }

    for node_table in NODE_TABLES:
        if node_table not in existing:
            continue
        query = f"MATCH (n:{node_table}) RETURN n.*"
        results = store.execute_cypher(query)

        cleaned_results = []
        for row in results:
            cleaned_row = {
                k.replace("n.", ""): v
                for k, v in row.items()
                if k.replace("n.", "") not in EXCLUDED_FIELDS
            }
            cleaned_results.append(cleaned_row)

        cleaned_results.sort(key=lambda x: str(x.get("id", x.get("term", ""))))
        if cleaned_results:
            data["nodes"][node_table] = cleaned_results

    for rel_table, (src_table, src_pk, dst_table, dst_pk) in REL_TABLES.items():
        if rel_table not in existing:
            continue
        query = f"MATCH (a:{src_table})-[r:{rel_table}]->(b:{dst_table}) RETURN a.{src_pk} AS _src, b.{dst_pk} AS _dst, r.*"
        results = store.execute_cypher(query)

        cleaned_results = []
        for row in results:
            cleaned_row = {
                k.replace("r.", ""): v
                for k, v in row.items()
                if k.replace("r.", "") not in EXCLUDED_FIELDS
            }
            cleaned_results.append(cleaned_row)

        cleaned_results.sort(key=lambda x: (str(x.get("_src", "")), str(x.get("_dst", ""))))
        if cleaned_results:
            data["relations"][rel_table] = cleaned_results

    json_str = json.dumps(data, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str)

    store.close()
    if backend == "kuzu":
        from mcp_server.db.kuzu_client import KuzuClient
        KuzuClient.clear_cache()
    elif backend == "ladybug":
        from tools.adapters.ladybug_store import LadybugGraphStore
        LadybugGraphStore.clear_cache()

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_str)
    else:
        print(json_str)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deterministic dump of a Kùzu/Ladybug graph database")
    parser.add_argument("--db", required=True, help="Path to the database directory or file")
    parser.add_argument("--out", help="Output JSON file (default: stdout)")
    parser.add_argument("--backend", help="Graph backend ('kuzu' or 'ladybug', auto-detected if omitted)")

    args = parser.parse_args()
    dump_graph(args.db, args.out, args.backend)
