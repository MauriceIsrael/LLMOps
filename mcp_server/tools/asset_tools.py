"""Outils FastMCP pour la récupération typée de documents d'architecture et métadonnées."""

from pathlib import Path
from typing import Any

from mcp_server.config import settings
from mcp_server.core.config import server_config
from pipelines.ingestion.markdown_parser import MarkdownDocParser
from tools.adapters.kuzu_store import make_graph_store


def _get_db():
    return make_graph_store(server_config.knowledge_db_path, read_only=True)


def _get_parser():
    return MarkdownDocParser()


def list_assets(
    type: str | None = None,
    phase: str | None = None,
    domain: str | None = None,
    status: str = "active",
) -> list[dict[str, Any]]:
    """Lister les identifiants et titres des artefacts correspondant aux filtres.

    Args:
        type: Type de document (ex: 'template', 'decision', 'principle', 'questionnaire', 'estimate', 'risk-register').
        phase: Phase de projet (ex: 'BID', 'BUILD', 'RUN').
        domain: Domaine fonctionnel/technique (ex: 'ai-assistance', 'telecom', 'delivery').
        status: Statut de l'artefact ('active', 'superseded', etc.).
    """
    conditions = [f"a.status = '{status}'"]
    if type:
        conditions.append(f"a.type = '{type}'")
    if phase:
        conditions.append(f"a.phase CONTAINS '{phase}'")
    if domain:
        conditions.append(f"a.domain CONTAINS '{domain}'")

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    query = (
        f"MATCH (a:Asset){where_clause} "
        f"RETURN a.id as id, a.title as title, a.type as type, a.status as status, "
        f"a.confidence as confidence, a.phase as phase, a.domain as domain, a.last_reviewed as last_reviewed;"
    )

    return _get_db().execute_cypher(query)


def get_asset(id: str) -> dict[str, Any]:
    """Obtenir le contenu complet d'un artefact d'architecture avec ses métadonnées.

    Args:
        id: Identifiant unique de l'artefact (ex: 'ADR-0011', 'QST-core-ems', 'RSK-netdevops-telco').
    """
    # Chercher d'abord le chemin source dans Kùzu DB
    query = (
        f"MATCH (a:Asset {{id: '{id}'}}) "
        f"RETURN a.source_path as source_path, a.confidence as confidence, a.last_reviewed as last_reviewed;"
    )
    res = _get_db().execute_cypher(query)

    parsed = None
    parser = _get_parser()
    if res and res[0].get("source_path") and Path(res[0]["source_path"]).exists():
        parsed = parser.parse_file(res[0]["source_path"])

    if not parsed:
        # Fallback search dans data/kb/
        kb_files = list(settings.KB_DIR.rglob("*.md")) + list(settings.KB_DIR.rglob("*.yaml")) + list(settings.KB_DIR.rglob("*.yml"))
        for path in kb_files:
            if path.stem == id or id in path.name:
                parsed = parser.parse_file(path)
                if parsed:
                    break

    if parsed:
        # Garantir que confidence et last_reviewed sont toujours présents au niveau racine
        if res and res[0]:
            parsed["confidence"] = parsed.get("confidence") or res[0].get("confidence", "")
            parsed["last_reviewed"] = parsed.get("last_reviewed") or res[0].get("last_reviewed", "")
        return parsed

    return {"error": f"Artefact avec l'identifiant '{id}' non trouvé dans la base."}


def get_decision_trail(id: str) -> dict[str, Any]:
    """Obtenir l'historique et la chaîne de décision d'un ADR (ce qu'il remplace et ce qui le remplace).

    Args:
        id: Identifiant de la décision d'architecture.
    """
    supersedes_query = f"""
    MATCH (a:Asset {{id: '{id}'}})-[:SUPERSEDES]->(target:Asset)
    RETURN target.id as supersedes_id, target.title as supersedes_title;
    """

    superseded_by_query = f"""
    MATCH (source:Asset)-[:SUPERSEDES]->(a:Asset {{id: '{id}'}})
    RETURN source.id as superseded_by_id, source.title as superseded_by_title;
    """

    current_asset = get_asset(id)
    supersedes = _get_db().execute_cypher(supersedes_query)
    superseded_by = _get_db().execute_cypher(superseded_by_query)

    return {
        "asset": current_asset,
        "supersedes": supersedes,
        "superseded_by": superseded_by,
    }


def get_glossary_term(term: str) -> dict[str, Any]:
    """Obtenir la définition canonique d'un terme du glossaire d'architecture.

    Args:
        term: Nom du terme du glossaire à rechercher.
    """
    query = f"""
    MATCH (g:GlossaryTerm)
    WHERE g.term CONTAINS '{term}' OR '{term}' CONTAINS g.term
    RETURN g.term as term, g.definition as definition;
    """
    res = _get_db().execute_cypher(query)
    if res and "error" not in res[0]:
        return res[0]
    return {"term": term, "definition": "Terme non trouvé dans le glossaire."}
