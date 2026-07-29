"""Validation de stabilité des identifiants et des références inter-plans.

Conforme à T3.4 de TPL-fixes-server-contract / ADR-0014.
"""

from typing import Any
from mcp_server.core.db import ReadOnlyKuzuClient


def validate_identifier_stability(kb_db_path: str, engagement_db_path: str) -> dict[str, Any]:
    """Vérifie qu'aucun identifiant cité dans un engagement n'a disparu de la base de connaissances

    sans lien `SUPERSEDES` explicite.
    """
    kb_client = ReadOnlyKuzuClient(db_path=kb_db_path)
    eng_client = ReadOnlyKuzuClient(db_path=engagement_db_path)

    # Récupérer les identifiants d'actifs actifs et leurs liens de replacement
    active_assets = kb_client.execute_cypher("MATCH (a:Asset) RETURN a.id as id, a.status as status;")
    supersedes = kb_client.execute_cypher("MATCH (s:Asset)-[:SUPERSEDES]->(target:Asset) RETURN target.id as id, s.id as superseded_by;")

    asset_map = {row["id"]: row["status"] for row in active_assets}
    superseded_map = {row["id"]: row["superseded_by"] for row in supersedes}

    # Récupérer tous les énoncés d'engagement
    statements = eng_client.execute_cypher("MATCH (st:Statement) RETURN st.id as id, st.based_on as based_on;")

    violations = []
    for st in statements:
        based_on = st.get("based_on") or []
        if isinstance(based_on, str):
            import json
            try:
                based_on = json.loads(based_on)
            except Exception:
                based_on = []

        for ref in based_on:
            ref_id = ref.get("id") if isinstance(ref, dict) else ref
            if not ref_id:
                continue

            if ref_id not in asset_map:
                if ref_id not in superseded_map:
                    violations.append({
                        "statement_id": st.get("id"),
                        "referenced_id": ref_id,
                        "error": "Identifier disappeared from knowledge base without a SUPERSEDES link.",
                    })

    return {
        "valid": len(violations) == 0,
        "violations": violations,
        "checked_statements": len(statements),
    }
