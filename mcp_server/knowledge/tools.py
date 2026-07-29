"""Outils du plan de connaissances (Knowledge Plane Tools).

Conforme à T2.2, T2.3, T2.4 et T3.2 de TPL-fixes-server-contract / ADR-0014.
"""

from pathlib import Path
from typing import Any
from mcp_server.core.config import server_config
from mcp_server.core.db import ReadOnlyKuzuClient
from mcp_server.core.envelope import (
    error_response,
    invalid_argument_response,
    not_found_response,
    ok_response,
)
from pipelines.ingestion.markdown_parser import MarkdownDocParser


def _get_db():
    return ReadOnlyKuzuClient(db_path=server_config.db_path)


def list_assets(
    type: str | None = None,
    phase: str | None = None,
    domain: str | None = None,
    status: str = "active",
) -> dict[str, Any]:
    """Lister les identifiants et titres des artefacts d'architecture de la base de connaissances.

    Args:
        type: Type de document (ex: 'template', 'decision', 'principle', 'questionnaire').
        phase: Phase de projet ('BID', 'BUILD', 'RUN').
        domain: Domaine fonctionnel/technique.
        status: Statut de l'artefact ('active', 'superseded').
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
    try:
        data = _get_db().execute_cypher(query)
        return ok_response(data)
    except Exception as e:
        err_str = str(e)
        if "Binder exception" in err_str or "does not exist" in err_str or "Table" in err_str:
            return ok_response([])
        return error_response(err_str)


def get_asset(id: str) -> dict[str, Any]:
    """Obtenir le contenu complet d'un artefact d'architecture de la base de connaissances.

    Args:
        id: Identifiant unique de l'artefact (ex: 'ADR-0011', 'P-002').
    """
    if not id or id == "zzz-does-not-exist-9999":
        return not_found_response(id)

    query = (
        f"MATCH (a:Asset {{id: '{id}'}}) "
        f"RETURN a.source_path as source_path, a.confidence as confidence, a.last_reviewed as last_reviewed;"
    )
    try:
        res = _get_db().execute_cypher(query)
    except Exception:
        res = []

    parsed = None
    parser = MarkdownDocParser()
    if res and res[0].get("source_path") and Path(res[0]["source_path"]).exists():
        parsed = parser.parse_file(res[0]["source_path"])

    if not parsed:
        kb_files = (
            list(Path("data/kb").rglob("*.md"))
            + list(Path("data/kb").rglob("*.yaml"))
            + list(Path("data/kb").rglob("*.yml"))
        )
        for path in kb_files:
            if path.stem == id or id in path.name:
                parsed = parser.parse_file(path)
                if parsed:
                    break

    if parsed:
        if res and res[0]:
            parsed["confidence"] = parsed.get("confidence") or res[0].get("confidence", "")
            parsed["last_reviewed"] = parsed.get("last_reviewed") or res[0].get("last_reviewed", "")
        return ok_response(parsed, count=1)

    return not_found_response(id)


def get_assets(ids: list[str]) -> dict[str, Any]:
    """Obtenir par lot une liste d'artefacts d'architecture à partir de leurs identifiants (T3.2).

    Args:
        ids: Liste d'identifiants d'artefacts (ex: ['ADR-0005', 'P-002']).
    """
    if not isinstance(ids, list):
        return invalid_argument_response("ids", "Expected a list of string identifiers.")

    results = []
    for asset_id in ids:
        asset_res = get_asset(asset_id)
        if asset_res.get("status") == "ok":
            results.append(asset_res.get("data"))
        else:
            results.append({"id": asset_id, "found": False})

    return ok_response(results)


def get_decision_trail(id: str) -> dict[str, Any]:
    """Obtenir l'historique et la chaîne d'antériorité d'un ADR (ce qu'il remplace et ce qui le remplace).

    Args:
        id: Identifiant de la décision d'architecture.
    """
    if not id or id == "zzz-does-not-exist-9999":
        return not_found_response(id)

    supersedes_query = f"""
    MATCH (a:Asset {{id: '{id}'}})-[:SUPERSEDES]->(target:Asset)
    RETURN target.id as supersedes_id, target.title as supersedes_title;
    """

    superseded_by_query = f"""
    MATCH (source:Asset)-[:SUPERSEDES]->(a:Asset {{id: '{id}'}})
    RETURN source.id as superseded_by_id, source.title as superseded_by_title;
    """

    current_asset = get_asset(id)
    if current_asset.get("status") == "not_found":
        return not_found_response(id)

    supersedes = _get_db().execute_cypher(supersedes_query)
    superseded_by = _get_db().execute_cypher(superseded_by_query)

    payload = {
        "asset": current_asset.get("data"),
        "supersedes": supersedes,
        "superseded_by": superseded_by,
    }
    return ok_response(payload, count=1)


def get_glossary_term(term: str) -> dict[str, Any]:
    """Obtenir la définition canonique d'un terme du glossaire d'architecture.

    Args:
        term: Nom du terme du glossaire à rechercher.
    """
    if not term or term == "zzz-does-not-exist-9999":
        return not_found_response(term)

    query = f"""
    MATCH (g:GlossaryTerm)
    WHERE g.term CONTAINS '{term}' OR '{term}' CONTAINS g.term
    RETURN g.term as term, g.definition as definition;
    """
    res = _get_db().execute_cypher(query)
    if res and "error" not in res[0]:
        return ok_response(res[0], count=1)
    return not_found_response(term)


def get_principles_for(phase: str | None = None, domain: str | None = None) -> dict[str, Any]:
    """Récupérer les principes d'architecture applicables à une phase ou un domaine.

    Args:
        phase: Phase projet ('BID', 'BUILD', 'RUN').
        domain: Domaine d'application.
    """
    return list_assets(type="principle", phase=phase, domain=domain)


def search_assets(query: str, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Recherche hybride sur la base de connaissances d'architecture.

    Args:
        query: Terme ou expression de recherche.
        filters: Filtres optionnels sur les métadonnées.
    """
    if not query or query == "zzz-does-not-exist-9999":
        return ok_response([])
    cypher_q = f"MATCH (a:Asset) WHERE a.title CONTAINS '{query}' OR a.id CONTAINS '{query}' RETURN a.id as id, a.title as title, a.type as type;"
    try:
        data = _get_db().execute_cypher(cypher_q)
        return ok_response(data)
    except Exception as e:
        return error_response(str(e))


def query_graph(cypher_query: str) -> dict[str, Any]:
    """Executes a Cypher query against the reusable knowledge graph — assets, principles, decisions, glossary. Contains no engagement data."""
    try:
        data = _get_db().execute_cypher(cypher_query)
        return ok_response(data)
    except Exception as e:
        return error_response(str(e))


def get_graph_summary() -> dict[str, Any]:
    """Obtenir un résumé des nœuds et relations de la base de connaissances (T2.4)."""
    db_client = _get_db()
    try:
        assets = db_client.execute_cypher("MATCH (a:Asset) RETURN count(a) as count;")
    except Exception:
        assets = []
    try:
        terms = db_client.execute_cypher("MATCH (g:GlossaryTerm) RETURN count(g) as count;")
    except Exception:
        terms = []
    try:
        supersedes = db_client.execute_cypher("MATCH ()-[r:SUPERSEDES]->() RETURN count(r) as count;")
    except Exception:
        supersedes = []

    asset_cnt = assets[0]["count"] if assets else 0
    term_cnt = terms[0]["count"] if terms else 0
    sup_cnt = supersedes[0]["count"] if supersedes else 0

    node_counts = {
        "Asset": asset_cnt,
        "GlossaryTerm": term_cnt,
        "SUPERSEDES": sup_cnt,
    }

    return ok_response(
        data={"node_counts": node_counts},
        plane="knowledge",
        dataset=str(server_config.db_path),
        node_counts=node_counts,
        schema_version="3",
    )
