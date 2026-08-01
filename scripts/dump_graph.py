#!/usr/bin/env python3
import argparse
import json
import sys

from mcp_server.db.kuzu_client import KuzuClient

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
    "SUPERSEDES": ("Asset", "Asset"),
    "REQUIRES": ("Asset", "Asset"),
    "DEFINES": ("Asset", "GlossaryTerm"),
    "ABOUT": ("Statement", "Subject"),
    "ANSWERS": ("Statement", "Question"),
    "TARGETS": ("Question", "Subject"),
    "INVOLVES": ("Conflict", "Statement"),
}

EXCLUDED_FIELDS = {
    "updated_at",
    "created_at",
    "extracted_at",
    "reviewed_at",
    "superseded_at",
}


def dump_graph(db_path: str, output_path: str | None = None) -> None:
    client = KuzuClient(db_path=db_path)
    
    data = {
        "nodes": {},
        "relations": {},
        "_meta": {
            "tables": NODE_TABLES + list(REL_TABLES.keys()),
            "excluded_fields": sorted(list(EXCLUDED_FIELDS))
        }
    }
    
    for node_table in NODE_TABLES:
        query = f"MATCH (n:{node_table}) RETURN n.*"
        results = client.execute_cypher(query)
        
        cleaned_results = []
        for row in results:
            cleaned_row = {
                k.replace("n.", ""): v 
                for k, v in row.items() 
                if k.replace("n.", "") not in EXCLUDED_FIELDS
            }
            cleaned_results.append(cleaned_row)
            
        cleaned_results.sort(key=lambda x: str(x.get("id", "")))
        if cleaned_results:
            data["nodes"][node_table] = cleaned_results
            
    for rel_table, (src_table, dst_table) in REL_TABLES.items():
        query = f"MATCH (a:{src_table})-[r:{rel_table}]->(b:{dst_table}) RETURN a.id AS _src, b.id AS _dst, r.*"
        results = client.execute_cypher(query)
        
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
    
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(json_str)
    else:
        print(json_str)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deterministic dump of a Kùzu/Ladybug graph database")
    parser.add_argument("--db", required=True, help="Path to the database directory")
    parser.add_argument("--out", help="Output JSON file (default: stdout)")
    
    args = parser.parse_args()
    dump_graph(args.db, args.out)
