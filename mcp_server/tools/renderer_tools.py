"""Outils FastMCP dédiés au moteur de rendu (Renderer Tools).

Fournit des payloads structurés et prêts à afficher (JSON, Graph, Mermaid)
pour les interfaces web, générateurs PDF, visualiseurs de diagrammes et dashboards.
"""

from typing import Any

from mcp_server.core.envelope import ok_response
from mcp_server.db.kuzu_client import KuzuClient
from tools.elicitation.repository import ElicitationRepository


def _get_db():
    return KuzuClient()


def get_render_payload(engagement: str = "nordwave-mcx-2027", db_path: str | None = None) -> dict[str, Any]:
    """Obtenir l'intégralité du document d'architecture et de ses données de synthèse pour le rendu.

    Args:
        engagement: Identifiant de l'engagement (ex: 'nordwave-mcx-2027').
        db_path: Chemin d'accès optionnel à la base Kùzu DB.
    """
    db_p = db_path or _get_db().db_path
    repo = ElicitationRepository(db_path=db_p)
    board = repo.get_subjects_maturity_board(engagement=engagement)
    statements = repo.get_active_statements(engagement=engagement)
    conflicts = repo.get_conflicts(engagement=engagement, status="open")
    uncertainties = repo.get_uncertainties(engagement=engagement)

    # Calcul du statut global
    unripe = [b for b in board if b.get("level") in ("L0_named", "L1_framed", "L2_decomposed")]
    is_provisional = len(conflicts) > 0 or len(unripe) > 0

    repo.close()

    payload = {
        "engagement": engagement,
        "status": "provisional" if is_provisional else "final",
        "is_provisional": is_provisional,
        "maturity_board": board,
        "active_statements": statements,
        "open_conflicts": conflicts,
        "uncertainties": uncertainties,
        "unripe_subjects": [u["subject"] for u in unripe],
    }
    return ok_response(payload)


def get_diagram_graph(engagement: str = "nordwave-mcx-2027", format: str = "json", db_path: str | None = None) -> dict[str, Any]:
    """Obtenir le graphe d'architecture sous forme de nœuds/liens ou code Mermaid prêt à être rendu.

    Args:
        engagement: Identifiant de l'engagement (ex: 'nordwave-mcx-2027').
        format: Format de restitution ('json' pour nœuds/arêtes, ou 'mermaid' pour code Mermaid).
        db_path: Chemin d'accès optionnel à la base Kùzu DB.
    """
    db_p = db_path or _get_db().db_path
    repo = ElicitationRepository(db_path=db_p)
    board = repo.get_subjects_maturity_board(engagement=engagement)
    statements = repo.get_active_statements(engagement=engagement)
    conflicts = repo.get_conflicts(engagement=engagement, status="open")
    repo.close()

    nodes = []
    node_ids = set()

    for sub in board:
        nid = sub["subject"]
        if nid not in node_ids:
            nodes.append({
                "id": nid,
                "label": nid,
                "type": "Subject",
                "level": sub.get("level", "L0_named"),
                "origin": sub.get("origin", "declared"),
            })
            node_ids.add(nid)

    edges = []
    for st in statements:
        src = st.get("subject", "general")
        val = st.get("value", "")
        pred = st.get("predicate", "about")
        sid = st.get("id", "S")

        # Détecter si la valeur mentionne un sous-sujet
        for n in node_ids:
            if n in val and n != src:
                edges.append({
                    "id": f"{sid}-{n}",
                    "source": src,
                    "target": n,
                    "predicate": pred,
                    "label": pred,
                    "statement_id": sid,
                })

    for c in conflicts:
        cid = c.get("id")
        nodes.append({
            "id": cid,
            "label": f"Conflit {cid}",
            "type": "Conflict",
            "detail": c.get("detail", ""),
        })
        for st_id in c.get("statement_ids", []):
            edges.append({
                "id": f"{cid}-{st_id}",
                "source": cid,
                "target": st_id,
                "predicate": "INVOLVES",
                "label": "involves",
            })

    # Génération du code Mermaid si demandé
    mermaid_lines = ["flowchart TD"]
    for n in nodes:
        if n["type"] == "Subject":
            mermaid_lines.append(f'    {n["id"]}["{n["label"]} ({n.get("level", "")})"]')
        elif n["type"] == "Conflict":
            mermaid_lines.append(f'    {n["id"]}{{"⚠️ {n["label"]}"}}')

    for e in edges:
        mermaid_lines.append(f'    {e["source"]} -->|"{e["label"]}"| {e["target"]}')

    mermaid_code = "\n".join(mermaid_lines)

    payload = {
        "engagement": engagement,
        "format": format,
        "nodes": nodes,
        "edges": edges,
        "mermaid": mermaid_code,
    }
    return ok_response(payload)


def get_subject_trajectory_tool(engagement: str = "nordwave-mcx-2027", subject: str = "mcx-services", db_path: str | None = None) -> dict[str, Any]:
    """Obtenir la trajectoire d'avancement par niveau de maturité pour un sujet (timeline).

    Args:
        engagement: Identifiant de l'engagement (ex: 'nordwave-mcx-2027').
        subject: Nom du sujet d'architecture (ex: 'mcx-services').
        db_path: Chemin d'accès optionnel à la base Kùzu DB.
    """
    db_p = db_path or _get_db().db_path
    repo = ElicitationRepository(db_path=db_p)
    trajectory = repo.get_subject_trajectory(engagement=engagement, subject=subject)
    repo.close()
    return ok_response(trajectory)
