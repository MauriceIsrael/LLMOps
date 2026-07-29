"""Outils FastMCP pour la navigation graphique et l'exécution de requêtes Cypher dans Kùzu DB."""

from typing import Any

from mcp_server.db.kuzu_client import KuzuClient

def _get_db():
    return KuzuClient()


def query_graph(cypher_query: str) -> list[dict[str, Any]]:
    """Exécuter directement une requête Cypher personnalisée sur le Graphe de Connaissances Kùzu.

    Args:
        cypher_query: Requête Cypher à exécuter (ex: 'MATCH (a:Asset) RETURN a.id, a.title LIMIT 5;').
    """
    return _get_db().execute_cypher(cypher_query)


def get_graph_summary() -> dict[str, Any]:
    """Obtenir un résumé des nœuds et des relations stockés dans Kùzu DB."""
    db_client = _get_db()
    assets = db_client.execute_cypher("MATCH (a:Asset) RETURN count(a) as total_assets;")
    terms = db_client.execute_cypher("MATCH (g:GlossaryTerm) RETURN count(g) as total_glossary_terms;")
    supersedes = db_client.execute_cypher("MATCH ()-[r:SUPERSEDES]->() RETURN count(r) as total_supersedes;")

    return {
        "total_assets": assets[0]["total_assets"] if assets else 0,
        "total_glossary_terms": terms[0]["total_glossary_terms"] if terms else 0,
        "total_supersedes_relations": supersedes[0]["total_supersedes"] if supersedes else 0,
    }
