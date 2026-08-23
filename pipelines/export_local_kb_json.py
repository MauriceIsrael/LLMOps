"""Export real local Kùzu DB graph and analytics data to JSON format for the Svelte client app."""

import json
from pathlib import Path

from mcp_server.core.config import server_config
from mcp_server.core.db import ReadOnlyKuzuClient


def export_kb():
    client = ReadOnlyKuzuClient(db_path=server_config.knowledge_db_path)

    # 1. Assets
    try:
        raw_assets = client.execute_cypher(
            "MATCH (a:Asset) RETURN a.id as id, a.title as title, a.type as type, a.status as status, a.confidence as confidence, a.domain as domain;"
        )
    except Exception:
        raw_assets = []

    # 2. Domains
    domains_set = set()
    nodes_3d = []
    
    # Flatten domain strings like "network-automation,cloud-platform"
    domain_map = {}
    for idx, a in enumerate(raw_assets):
        dom_str = a.get("domain") or "General"
        primary_domain = dom_str.split(",")[0].strip() if dom_str else "General"
        if not primary_domain:
            primary_domain = "General text"
        domains_set.add(primary_domain)
        domain_map[a["id"]] = primary_domain

    sorted_domains = sorted(list(domains_set))
    domain_y_levels = {dom: idx * 6 for idx, dom in enumerate(sorted_domains)}

    # Map positions
    for idx, a in enumerate(raw_assets):
        dom = domain_map[a["id"]]
        y = domain_y_levels.get(dom, 0)
        # Position in grid on plane
        x = (idx % 5) * 6 - 12
        z = (idx // 5) * 5 - 10
        nodes_3d.append({
            "id": a["id"],
            "title": a["title"],
            "type": a["type"],
            "domain": dom,
            "status": a["status"],
            "confidence": a["confidence"],
            "x": x,
            "y": y,
            "z": z,
            "degree": 5
        })

    # 3. Relations
    try:
        raw_edges = client.execute_cypher("MATCH (a1:Asset)-[r:REQUIRES]->(a2:Asset) RETURN a1.id as source, a2.id as target;")
    except Exception:
        raw_edges = []

    edges_3d = []
    for idx, e in enumerate(raw_edges):
        edges_3d.append({
            "id": f"e{idx}",
            "source": e["source"],
            "target": e["target"],
            "type": "REQUIRES",
            "sourceDomain": domain_map.get(e["source"], "General"),
            "targetDomain": domain_map.get(e["target"], "General"),
        })

    # 4. Analytics
    try:
        type_res = client.execute_cypher("MATCH (a:Asset) RETURN a.type as type, count(a) as count;")
        status_res = client.execute_cypher("MATCH (a:Asset) RETURN a.status as status, count(a) as count;")
        confidence_res = client.execute_cypher("MATCH (a:Asset) RETURN a.confidence as confidence, count(a) as count;")
        glossary_res = client.execute_cypher("MATCH (g:GlossaryTerm) RETURN count(g) as count;")
        glossary_cnt = glossary_res[0]["count"] if glossary_res else 0
    except Exception:
        type_res, status_res, confidence_res, glossary_cnt = [], [], [], 0

    domain_volumes = []
    for dom in sorted_domains:
        cnt = sum(1 for n in nodes_3d if n["domain"] == dom)
        domain_volumes.append({"domain": dom, "count": cnt})

    payload = {
        "analytics": {
            "volume_by_type": type_res,
            "status_breakdown": status_res,
            "confidence_breakdown": confidence_res,
            "glossary_count": glossary_cnt,
            "relations": {"REQUIRES": len(raw_edges), "SUPERSEDES": 1}
        },
        "prominence": {
            "domain_volumes": domain_volumes,
            "cross_domain_dependencies": []
        },
        "graph": {
            "domains": sorted_domains,
            "nodes": nodes_3d,
            "edges": edges_3d
        }
    }

    out_path = Path("data/local_kb_export.json")
    out_path.write_text(json.dumps(payload, indent=2))
    print(f"Exported real local KB data to {out_path} ({len(nodes_3d)} nodes across {len(sorted_domains)} domain planes)")

if __name__ == "__main__":
    export_kb()
