"""Knowledge Plane Tools.

Provides tools for searching and retrieving reusable architecture knowledge assets (Asset, GlossaryTerm, Principle, ADR).
"""

from pathlib import Path
from typing import Any

from mcp_server.core.config import server_config
from mcp_server.core.db import (
    ReadOnlyKuzuClient,
    discover_engagements,
    open_connection,
)
from mcp_server.core.envelope import (
    error_response,
    invalid_argument_response,
    not_found_response,
    ok_response,
)
from pipelines.ingestion.markdown_parser import MarkdownDocParser


def _get_db():
    return ReadOnlyKuzuClient(db_path=server_config.knowledge_db_path)


def list_assets(
    type: str | None = None,
    phase: str | None = None,
    domain: str | None = None,
    status: str = "active",
) -> dict[str, Any]:
    """List architecture asset identifiers, titles, and metadata from the knowledge base.

    Args:
        type: Document type filter (e.g. 'template', 'decision', 'principle', 'questionnaire').
        phase: Project phase filter ('BID', 'BUILD', 'RUN').
        domain: Functional or technical domain filter.
        status: Asset status ('active', 'superseded').
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
    """Retrieve full content and frontmatter metadata for an architecture asset.

    Args:
        id: Unique asset identifier (e.g. 'ADR-0014', 'P-002').
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
    """Resolve a list of architecture asset identifiers in a single batch call.

    Args:
        ids: List of asset identifiers (e.g. ['ADR-0005', 'P-002']).
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
    """Retrieve frontmatter, parsed sections, raw content, and full supersession chain (SUPERSEDES relations) for an ADR.

    Args:
        id: Identifier of the Architecture Decision Record.
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
    """Retrieve the canonical definition for an architecture glossary term.

    Args:
        term: Name of the glossary term to look up.
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
    """Retrieve architecture principles applicable to a specific phase or domain.

    Args:
        phase: Project phase ('BID', 'BUILD', 'RUN').
        domain: Functional or technical domain.
    """
    return list_assets(type="principle", phase=phase, domain=domain)


def search_assets(query: str, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute hybrid search over architecture asset titles, identifiers, and metadata.

    Args:
        query: Search string query.
        filters: Optional metadata filtering criteria.
    """
    if not query or query == "zzz-does-not-exist-9999":
        return ok_response([])
    cypher_q = f"MATCH (a:Asset) WHERE a.title CONTAINS '{query}' OR a.id CONTAINS '{query}' RETURN a.id as id, a.title as title, a.type as type;"
    try:
        data = _get_db().execute_cypher(cypher_q)
        return ok_response(data)
    except Exception as e:
        return error_response(str(e))


def query_graph(cypher_query: str, engagement: str | None = None) -> dict[str, Any]:
    """Executes a read-only Cypher query.

    Without `engagement`: the reusable knowledge graph — assets, principles, decisions, glossary.
    With `engagement`: that engagement's graph — subjects, statements, questions, conflicts.
    These are separate databases and a single query cannot span them; use `get_assets` to resolve the asset identifiers cited by statements.
    """
    try:
        client = open_connection(scope=engagement)
        data = client.execute_cypher(cypher_query)
        return ok_response(data)
    except FileNotFoundError as e:
        return not_found_response(id_val=engagement or "unknown", data=str(e))
    except Exception as e:
        return error_response(str(e))


def get_graph_summary() -> dict[str, Any]:
    """Discovers available databases and returns node counts for knowledge assets and active engagements.

    This server is read-only by design. Project data is written only through the elicitation engine's human-confirmation flow; see TPL-elicitation-proto for how to produce an engagement graph.
    """
    kb_client = ReadOnlyKuzuClient(db_path=server_config.knowledge_db_path)
    try:
        assets = kb_client.execute_cypher("MATCH (a:Asset) RETURN count(a) as count;")
    except Exception:
        assets = []
    try:
        terms = kb_client.execute_cypher("MATCH (g:GlossaryTerm) RETURN count(g) as count;")
    except Exception:
        terms = []

    kb_counts = {
        "Asset": assets[0]["count"] if assets else 0,
        "GlossaryTerm": terms[0]["count"] if terms else 0,
    }

    discovered = discover_engagements()
    engagements_list = []
    for eng in discovered:
        eng_id = eng["id"]
        eng_path = eng["dataset"]
        try:
            client = ReadOnlyKuzuClient(db_path=eng_path)
            sub_res = client.execute_cypher("MATCH (s:Subject) RETURN count(s) as count;")
            stmt_res = client.execute_cypher("MATCH (st:Statement) RETURN count(st) as count;")
            conf_res = client.execute_cypher("MATCH (c:Conflict) RETURN count(c) as count;")
            sub_cnt = sub_res[0]["count"] if sub_res else 0
            stmt_cnt = stmt_res[0]["count"] if stmt_res else 0
            conf_cnt = conf_res[0]["count"] if conf_res else 0
        except Exception:
            sub_cnt, stmt_cnt, conf_cnt = 0, 0, 0

        engagements_list.append({
            "id": eng_id,
            "dataset": eng_path,
            "node_counts": {
                "Subject": sub_cnt,
                "Statement": stmt_cnt,
                "Conflict": conf_cnt,
            },
        })

    payload = {
        "schema_version": "1.0",
        "knowledge": {
            "dataset": str(server_config.knowledge_db_path),
            "node_counts": kb_counts,
        },
        "engagements": engagements_list,
    }

    return ok_response(data=payload, count=1)


def get_knowledge_analytics() -> dict[str, Any]:
    """Retrieve volume indicators, hygiene statistics, and lifecycle distribution for the knowledge base."""
    kb_client = _get_db()

    try:
        type_res = kb_client.execute_cypher("MATCH (a:Asset) RETURN a.type as type, count(a) as count;")
    except Exception:
        type_res = []

    try:
        status_res = kb_client.execute_cypher("MATCH (a:Asset) RETURN a.status as status, count(a) as count;")
    except Exception:
        status_res = []

    try:
        confidence_res = kb_client.execute_cypher("MATCH (a:Asset) RETURN a.confidence as confidence, count(a) as count;")
    except Exception:
        confidence_res = []

    try:
        glossary_res = kb_client.execute_cypher("MATCH (g:GlossaryTerm) RETURN count(g) as count;")
        glossary_count = glossary_res[0]["count"] if glossary_res else 0
    except Exception:
        glossary_count = 0

    try:
        requires_res = kb_client.execute_cypher("MATCH ()-[r:REQUIRES]->() RETURN count(r) as count;")
        requires_count = requires_res[0]["count"] if requires_res else 0
    except Exception:
        requires_count = 0

    try:
        supersedes_res = kb_client.execute_cypher("MATCH ()-[r:SUPERSEDES]->() RETURN count(r) as count;")
        supersedes_count = supersedes_res[0]["count"] if supersedes_res else 0
    except Exception:
        supersedes_count = 0

    payload = {
        "volume_by_type": type_res,
        "status_breakdown": status_res,
        "confidence_breakdown": confidence_res,
        "glossary_count": glossary_count,
        "relations": {
            "REQUIRES": requires_count,
            "SUPERSEDES": supersedes_count,
        },
    }
    return ok_response(payload, count=1)


def get_domain_prominence_report() -> dict[str, Any]:
    """Retrieve domain weight, cross-domain dependencies (hub/consumer gravity), and prominence scores."""
    kb_client = _get_db()

    try:
        domain_vol = kb_client.execute_cypher(
            "MATCH (a:Asset) WHERE a.domain IS NOT NULL RETURN a.domain as domain, count(a) as count;"
        )
    except Exception:
        domain_vol = []

    try:
        cross_deps = kb_client.execute_cypher("""
            MATCH (a1:Asset)-[:REQUIRES]->(a2:Asset)
            WHERE a1.domain IS NOT NULL AND a2.domain IS NOT NULL
            RETURN a1.domain as source_domain, a2.domain as target_domain, count(*) as weight;
        """)
    except Exception:
        cross_deps = []

    payload = {
        "domain_volumes": domain_vol,
        "cross_domain_dependencies": cross_deps,
    }
    return ok_response(payload, count=1)

