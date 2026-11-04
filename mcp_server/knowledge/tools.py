"""Knowledge Plane Tools.

Provides tools for searching and retrieving reusable architecture knowledge assets (Asset, GlossaryTerm, Principle, ADR).
"""

import logging
import os
from pathlib import Path
from typing import Any

from mcp_server.core.config import server_config
from mcp_server.core.db import (
    ReadOnlyKuzuClient,
    discover_engagements,
    guard_engagement,
    open_connection,
)
from mcp_server.core.envelope import (
    handle_exception_response,
    invalid_argument_response,
    not_found_response,
    ok_response,
)
from mcp_server.core.version import CONTRACT_VERSION
from pipelines.ingestion.markdown_parser import MarkdownDocParser

logger = logging.getLogger(__name__)


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
    conditions = ["a.status = $status"]
    params: dict[str, Any] = {"status": status}
    if type:
        conditions.append("a.type = $type")
        params["type"] = type
    if phase:
        conditions.append("a.phase CONTAINS $phase")
        params["phase"] = phase
    if domain:
        conditions.append("a.domain CONTAINS $domain")
        params["domain"] = domain

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    query = (
        f"MATCH (a:Asset){where_clause} "
        f"RETURN a.id as id, a.title as title, a.type as type, a.status as status, "
        f"a.confidence as confidence, a.phase as phase, a.domain as domain, a.last_reviewed as last_reviewed;"
    )
    try:
        data = _get_db().execute_cypher(query, params)
        return ok_response(data)
    except Exception as e:
        return handle_exception_response(e, context_action="list_assets")


SNAPSHOTS_DIR = Path("data/snapshots")


def resolve_asset_reference(id: str, version: str | None = None, snapshot: str | None = None) -> dict[str, Any]:
    """Resolve a citable reference ``{knowledgeKey, version}`` from a sealed snapshot (K3), never from the live base.

    ``id`` is a typed key (``decision:ADR-0001``) or a bare identifier; ``snapshot`` designates the snapshot (default: the
    latest). A version the snapshot does not hold is refused with the version it holds, never answered with other content.
    """
    from pipelines.knowledge_ref import ResolutionError, load_snapshot, resolve

    if not id:
        return invalid_argument_response("id", "A knowledge key is required.")
    try:
        return ok_response(resolve(load_snapshot(SNAPSHOTS_DIR, snapshot), id, version), count=1)
    except ResolutionError as err:
        if err.reason == "invalid_snapshot_id":
            return invalid_argument_response("snapshot", str(err))
        if err.reason in ("snapshot_corrupt", "content_corrupt"):
            return {"status": "error", "reason": err.reason, "error": str(err), **err.detail}
        return {"status": "not_found", "id": id, "reason": err.reason, "error": str(err), **err.detail}


def get_asset(id: str, version: str | None = None, snapshot: str | None = None) -> dict[str, Any]:
    """Retrieve full content and frontmatter metadata for an architecture asset.

    Without ``version`` nor ``snapshot`` the **live** base is read (current state, not citable: ``resolved_from`` says so).
    With either, the asset is resolved from a sealed snapshot (K3): the same ``{knowledgeKey, version}`` always yields the
    same bytes, and a version the snapshot does not hold is refused (see ``resolve_asset_reference``).

    Args:
        id: Unique asset identifier (e.g. 'ADR-0014', 'P-002') or typed key ('decision:ADR-0014').
        version: Revision to resolve, from the snapshot.
        snapshot: Snapshot identifier to resolve from (default: the latest sealed snapshot).
    """
    if not id:
        return not_found_response(id)
    if version is not None or snapshot is not None:
        return resolve_asset_reference(id, version, snapshot)

    query = (
        "MATCH (a:Asset {id: $id}) "
        "RETURN a.id as id, a.title as title, a.type as type, a.status as status, "
        "a.confidence as confidence, a.phase as phase, a.domain as domain, "
        "a.last_reviewed as last_reviewed, a.owner as owner, a.source_path as source_path, "
        "a.version as version, a.markdown_content as markdown_content, a.sha256 as sha256, "
        "a.external_ref as external_ref;"
    )
    try:
        res = _get_db().execute_cypher(query, {"id": id})
    except Exception:
        res = []

    if res and res[0] and res[0].get("id"):
        row = res[0]
        markdown_content = row.get("markdown_content") or ""
        parser = MarkdownDocParser()
        parsed = parser.parse_content(markdown_content, source_path=row.get("source_path", "")) if markdown_content else None
        if not parsed and row.get("source_path") and Path(row["source_path"]).exists():
            parsed = parser.parse_file(row["source_path"])

        if parsed:
            parsed["confidence"] = row.get("confidence") or parsed.get("confidence", "")
            parsed["last_reviewed"] = row.get("last_reviewed") or parsed.get("last_reviewed", "")
            parsed["version"] = row.get("version") or parsed.get("version", "1.0.0")
            parsed["external_ref"] = row.get("external_ref") or f"KH:{id}@v{parsed['version']}"
            parsed["resolved_from"] = "live-base"
            return ok_response(parsed, count=1)

    # Fallback disk search if database row missing
    parser = MarkdownDocParser()
    kb_files = (
        list(Path("data/kb").rglob("*.md"))
        + list(Path("data/kb").rglob("*.yaml"))
        + list(Path("data/kb").rglob("*.yml"))
    )
    for path in kb_files:
        if path.stem == id or id in path.name:
            parsed = parser.parse_file(path)
            if parsed:
                parsed["external_ref"] = f"KH:{id}@v{parsed.get('version', '1.0.0')}"
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
    if not id:
        return not_found_response(id)

    supersedes_query = """
    MATCH (a:Asset {id: $id})-[:SUPERSEDES]->(target:Asset)
    RETURN target.id as supersedes_id, target.title as supersedes_title;
    """

    superseded_by_query = """
    MATCH (source:Asset)-[:SUPERSEDES]->(a:Asset {id: $id})
    RETURN source.id as superseded_by_id, source.title as superseded_by_title;
    """

    current_asset = get_asset(id)
    if current_asset.get("status") == "not_found":
        return not_found_response(id)

    supersedes = _get_db().execute_cypher(supersedes_query, {"id": id})
    superseded_by = _get_db().execute_cypher(superseded_by_query, {"id": id})

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
    if not term:
        return not_found_response(term)

    query = """
    MATCH (g:GlossaryTerm)
    WHERE g.term CONTAINS $term OR $term CONTAINS g.term
    RETURN g.term as term, g.definition as definition;
    """
    res = _get_db().execute_cypher(query, {"term": term})
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
    if not query:
        return ok_response([])
    cypher_q = "MATCH (a:Asset) WHERE a.title CONTAINS $query OR a.id CONTAINS $query RETURN a.id as id, a.title as title, a.type as type;"
    try:
        data = _get_db().execute_cypher(cypher_q, {"query": query})
        return ok_response(data)
    except Exception as e:
        return handle_exception_response(e, context_action="search_assets")


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
        return handle_exception_response(e, context_action="query_graph")


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
        "Asset": next(iter(assets[0].values())) if assets and isinstance(assets[0], dict) and assets[0] else 0,
        "GlossaryTerm": next(iter(terms[0].values())) if terms and isinstance(terms[0], dict) and terms[0] else 0,
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
            "dataset": Path(eng_path).as_posix(),  # the same text on every OS: a fixture generated on Windows stays valid on Linux
            "node_counts": {
                "Subject": sub_cnt,
                "Statement": stmt_cnt,
                "Conflict": conf_cnt,
            },
        })

    payload = {
        "schema_version": CONTRACT_VERSION,
        "knowledge": {
            "dataset": Path(server_config.knowledge_db_path).as_posix(),
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


def _framework_metadata() -> dict[str, dict[str, str]]:
    """Descriptive metadata of the frameworks: data/kb/controls/frameworks.yaml (KB data, not code)."""
    import yaml

    path = Path(server_config.kb_dir) / "controls" / "frameworks.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(k): {kk: str(vv) for kk, vv in (v or {}).items()} for k, v in data.items()}


def list_frameworks() -> dict[str, Any]:
    """List regulatory and security frameworks embedded in the knowledge base along with their versions and control counts."""
    kb_client = _get_db()
    try:
        from pipelines.frameworks.coverage import _controls, framework_coverage

        query = """
        MATCH (c:Control)
        RETURN c.framework as framework, c.version as version, count(c) as control_count;
        """
        rows = kb_client.execute_cypher(query)
        meta = _framework_metadata()
        controls_by_fw = _controls(Path(server_config.kb_dir))
        from pipelines.publication.history import get_framework_sources
        fw_sources = get_framework_sources(Path(server_config.kb_dir))
        res = []
        for r in rows:
            fw = r.get("framework", "")
            info = meta.get(fw, {"title": fw, "jurisdiction": "Unknown", "description": ""})
            cov = framework_coverage(fw, server_config.kb_dir)
            fw_ctrls = controls_by_fw.get(fw.lower(), [])
            validated_controls = [
                {
                    "id": str(c["id"]),
                    "validated_by": [str(v) for v in (c.get("validated_by") or [])],
                    "validated_at": str(c["validated_at"]) if c.get("validated_at") else None,
                }
                for c in fw_ctrls
                if c.get("id") and c.get("validated_by")
            ]
            fw_info = fw_sources.get(fw.upper()) or {}
            res.append({
                "framework": fw,
                "version": r.get("version", "1.0.0"),
                "title": info["title"],
                "jurisdiction": info["jurisdiction"],
                "description": info["description"],
                "control_count": r.get("control_count", 0),
                "status": cov["status"],
                "expected": cov["expected"],
                "present": cov["present"],
                "validated": cov["validated"],
                "declared_by": cov["declared_by"],
                "declared_at": cov["declared_at"],
                "provisional": cov["provisional"],
                "validated_controls": validated_controls,
                "ingested_source": fw_info.get("ingested_source"),
                "source_sha256": fw_info.get("source_sha256"),
                "associated_publications": fw_info.get("associated_publications") or [],
            })
        return ok_response(res, count=len(res))
    except Exception as e:
        return handle_exception_response(e, context_action="list_frameworks")


def list_controls(
    framework: str | None = None,
    domain: str | None = None,
    severity: str | None = None,
) -> dict[str, Any]:
    """List security and compliance controls with optional filtering by framework, domain, or severity.

    Args:
        framework: Framework code filter (e.g. 'NIS2', '3GPP').
        domain: Security domain filter (e.g. 'resilience', 'cryptography', 'supply-chain').
        severity: Severity level ('mandatory', 'recommended').
    """
    conditions = []
    params: dict[str, Any] = {}
    if framework:
        conditions.append("c.framework = $framework")
        params["framework"] = framework
    if domain:
        conditions.append("c.domain CONTAINS $domain")
        params["domain"] = domain
    if severity:
        conditions.append("c.severity = $severity")
        params["severity"] = severity

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    query = (
        f"MATCH (c:Control){where_clause} "
        f"OPTIONAL MATCH (a:Asset)-[:IMPLEMENTS]->(c) "
        f"RETURN c.id as id, c.framework as framework, c.version as version, c.title as title, "
        f"c.domain as domain, c.severity as severity, c.status as status, c.target_entities as target_entities, "
        f"c.external_ref as external_ref, collect(a.id) as implemented_by;"
    )
    try:
        rows = _get_db().execute_cypher(query, params)
        return ok_response(rows, count=len(rows))
    except Exception as e:
        return handle_exception_response(e, context_action="list_controls")


def get_compliance_trail(control_id: str) -> dict[str, Any]:
    """Retrieve full compliance traceability for a specific control: regulatory text, criteria, and implementing patterns/principles/ADRs.

    Args:
        control_id: The control identifier (e.g. 'NIS2-ART21-2C', '3GPP-TS33179-KMS').
    """
    if not control_id or not isinstance(control_id, str):
        return invalid_argument_response("control_id", "control_id must be a non-empty string.")

    kb_client = _get_db()
    try:
        ctrl_res = kb_client.execute_cypher(
            "MATCH (c:Control {id: $id}) RETURN c.id as id, c.framework as framework, c.version as version, "
            "c.title as title, c.domain as domain, c.severity as severity, c.external_ref as external_ref, "
            "c.target_entities as target_entities, c.markdown_content as markdown_content;",
            {"id": control_id},
        )
        if not ctrl_res:
            return not_found_response(f"Control '{control_id}' not found.")

        ctrl = ctrl_res[0]

        impl_res = kb_client.execute_cypher(
            """
            MATCH (a:Asset)-[:IMPLEMENTS]->(c:Control {id: $id})
            RETURN a.id as id, a.title as title, a.type as type, a.confidence as confidence, a.status as status;
            """,
            {"id": control_id},
        )

        patterns = [a for a in impl_res if a.get("type") == "pattern"]
        principles = [a for a in impl_res if a.get("type") == "principle"]
        decisions = [a for a in impl_res if a.get("type") in ("decision", "adr")]
        others = [a for a in impl_res if a.get("type") not in ("pattern", "principle", "decision", "adr")]

        trail = {
            "control": ctrl,
            "implementing_patterns": patterns,
            "governing_principles": principles,
            "candidate_decisions": decisions,
            "other_assets": others,
            "total_coverage": len(impl_res),
        }
        return ok_response(trail, count=1)
    except Exception as e:
        return handle_exception_response(e, context_action="get_compliance_trail")


def get_compliance_matrix(engagement: str, framework: str) -> dict[str, Any]:
    """Evaluate compliance coverage of an engagement project against a regulatory framework.

    Args:
        engagement: Engagement identifier (e.g. 'my-engagement-2027').
        framework: Regulatory framework code (e.g. 'NIS2', '3GPP').
    """
    kb_client = _get_db()
    try:
        ctrls = kb_client.execute_cypher(
            "MATCH (c:Control {framework: $fw}) "
            "OPTIONAL MATCH (a:Asset)-[:IMPLEMENTS]->(c) "
            "RETURN c.id as id, c.title as title, c.severity as severity, collect(a.id) as implementing_assets;",
            {"fw": framework},
        )
        if not ctrls:
            return not_found_response(f"No controls found for framework '{framework}'.")

        eng_conn = open_connection(scope=engagement)
        stmt_rows = eng_conn.execute_cypher(
            "MATCH (s:Statement {status: 'active'}) "
            "RETURN s.id as id, s.value as value, s.verbatim as verbatim, s.subject as subject, s.predicate as predicate, "
            "s.based_on as based_on, s.confidence as confidence;"
        )

        matrix = []
        covered_count = 0
        for c in ctrls:
            c_id = c["id"]
            impl_assets = set(c.get("implementing_assets") or [])
            matching_statements = []
            for stmt in stmt_rows:
                based_on = str(stmt.get("based_on") or "")
                val = str(stmt.get("value") or "")
                verb = str(stmt.get("verbatim") or "")
                if c_id in based_on or c_id in val or c_id in verb or any(a in based_on for a in impl_assets):
                    matching_statements.append({
                        "statement_id": stmt["id"],
                        "subject": stmt["subject"],
                        "value": val,
                        "confidence": stmt["confidence"],
                    })

            status = "covered" if matching_statements else "unaddressed"
            if status == "covered":
                covered_count += 1

            matrix.append({
                "control_id": c_id,
                "title": c["title"],
                "severity": c["severity"],
                "status": status,
                "implementing_kb_assets": list(impl_assets),
                "satisfying_statements": matching_statements,
            })

        total = len(ctrls)
        coverage_pct = round((covered_count / total) * 100, 1) if total > 0 else 0.0

        summary = {
            "engagement": engagement,
            "framework": framework,
            "total_controls": total,
            "covered_controls": covered_count,
            "unaddressed_controls": total - covered_count,
            "coverage_percentage": coverage_pct,
            "matrix": matrix,
        }
        return ok_response(summary, count=1)
    except Exception as e:
        return handle_exception_response(e, context_action="get_compliance_matrix")


def suggest_knowledge_improvement(
    title: str,
    rationale: str,
    suggested_change: str,
    author: str = "external-contributor",
    contact_email: str | None = None,
    source_engagement: str | None = None,
) -> dict[str, Any]:
    """Submit a suggestion to improve the architecture knowledge base.

    The proposal will be archived, reviewed by the Knowledge Hub owner (Maurice Israel),
    and evaluated for promotion into the enterprise standard via the Harvest loop.
    It is also queued as a KB candidate (kind 'rex'); its id is returned as 'candidate_id'.

    Args:
        title: Short descriptive title of the suggested knowledge improvement.
        rationale: Why this change or pattern is needed and the architectural value it provides.
        suggested_change: Markdown description of the proposed asset, ADR amendment, or pattern.
        author: Name or identifier of the contributor.
        contact_email: Optional email address to receive feedback on the review.
        source_engagement: Optional engagement or project where this pattern was proven.
    """
    return _suggest_knowledge_improvement(
        title, rationale, suggested_change, author, contact_email, source_engagement, system="mcp"
    )


def _suggest_knowledge_improvement(
    title: str,
    rationale: str,
    suggested_change: str,
    author: str = "external-contributor",
    contact_email: str | None = None,
    source_engagement: str | None = None,
    system: str = "mcp",
) -> dict[str, Any]:
    if not title or not title.strip():
        return invalid_argument_response("title", "title must not be empty")
    if not rationale or not rationale.strip():
        return invalid_argument_response("rationale", "rationale must not be empty")
    if not suggested_change or not suggested_change.strip():
        return invalid_argument_response("suggested_change", "suggested_change must not be empty")

    from mcp_server.core.notifier import notify_owner_of_suggestion

    res = notify_owner_of_suggestion(
        title=title.strip(),
        rationale=rationale.strip(),
        suggested_change=suggested_change.strip(),
        author=author.strip(),
        contact=contact_email.strip() if contact_email else None,
        source_engagement=source_engagement.strip() if source_engagement else None,
    )

    # Contract 1.2: the suggestion also enters the KB candidate queue (kind 'rex').
    try:
        from pipelines.kb_candidates.service import rex_payload

        candidate = _candidate_service().submit(
            rex_payload(
                title=title.strip(),
                rationale=rationale.strip(),
                suggested_change=suggested_change.strip(),
                author=author.strip() or None,
                contact=contact_email.strip() if contact_email else None,
                source_engagement=source_engagement.strip() if source_engagement else None,
                system=system,
            ),
            actor=_actor(),
        )
        res["candidate_id"] = candidate["id"]
    except Exception as exc:  # the suggestion itself must never fail because of the queue
        import logging

        logging.getLogger("mcp_server").warning("KB candidate creation failed for suggestion: %s", exc)
    return ok_response(res, count=1)


def list_skills(domain: str | None = None) -> dict[str, Any]:
    """List canonical technical skills, expertises, and expected competencies from the knowledge base.

    Args:
        domain: Optional filter by technical domain (e.g. 'security-cryptography', 'telecom-core').
    """
    skills_dir = Path("data/kb/skills")
    if not skills_dir.exists():
        return ok_response([])

    parser = MarkdownDocParser()
    skills = []
    for f in sorted(skills_dir.glob("*.md")):
        doc = parser.parse_file(str(f))
        if not doc:
            continue
        meta = doc.get("frontmatter", {})
        if domain and meta.get("domain") != domain:
            continue
        skills.append({
            "id": doc.get("id", f.stem),
            "title": doc.get("title", f.stem),
            "domain": meta.get("domain", "general"),
            "criticality": meta.get("criticality", "medium"),
            "status": meta.get("status", "active"),
            "keywords": meta.get("keywords", []),
            "description": doc.get("raw_body", "")[:300].strip(),
        })

    return ok_response(skills, count=len(skills))


def get_skills_matrix(
    engagement: str | None = None,
    blueprint_path: str | None = None,
) -> dict[str, Any]:
    """Calculate the staffing skill coverage matrix and risk index for an engagement.

    Args:
        engagement: Target engagement identifier (default: the deployment's LLMOPS_ENGAGEMENT).
        blueprint_path: Optional path or id of the architecture blueprint (default: LLMOPS_BLUEPRINT).
    """
    from mcp_server.core.config import resolve_blueprint_path, resolve_engagement
    from tools.elicitation.mailbox.roster import RosterManager
    from tools.elicitation.models.blueprint_schema import load_blueprint

    engagement = resolve_engagement(engagement)
    if not engagement:
        return invalid_argument_response("engagement", "No engagement given and LLMOPS_ENGAGEMENT is not set.")
    guard_engagement(engagement)  # K9
    bp_path = resolve_blueprint_path(blueprint_path)
    if bp_path is None:
        return invalid_argument_response("blueprint_path", "No blueprint given and LLMOPS_BLUEPRINT is not set.")
    bp = load_blueprint(bp_path)
    mgr = RosterManager(engagement=engagement)
    covered = mgr.get_all_covered_skills()

    required_skills_map = {}
    all_required: set[str] = set()
    for sec in bp.sections:
        s_skills = getattr(sec, "required_skills", [])
        if s_skills:
            required_skills_map[sec.id] = {
                "title": sec.title,
                "required_skills": s_skills,
                "missing_skills": [s for s in s_skills if s not in covered],
                "covered": all(s in covered for s in s_skills),
            }
            all_required.update(s_skills)

    uncovered = all_required - covered
    coverage_pct = round((len(all_required - uncovered) / len(all_required)) * 100, 1) if all_required else 100.0
    risk_level = "low" if coverage_pct == 100.0 else ("moderate" if coverage_pct >= 75.0 else "high")

    payload = {
        "engagement": engagement,
        "coverage_percentage": coverage_pct,
        "risk_level": risk_level,
        "total_required_skills": len(all_required),
        "covered_skills_count": len(all_required - uncovered),
        "missing_skills": sorted(list(uncovered)),
        "external_contractors": mgr.external_contractors,
        "sections": required_skills_map,
    }
    return ok_response(payload, count=len(required_skills_map))


def shred_rfp(
    rfp_text: str,
    engagement: str = "default",
    persist: bool = True,
) -> dict[str, Any]:
    """Deconstruct an RFP / tender document into atomic requirements and map them to KB assets.

    Args:
        rfp_text: Raw or Markdown RFP text containing client specifications and requirements.
        engagement: Engagement identifier (default: 'default' or project name).
        persist: Whether to store requirements into the engagement graph.
    """
    if not rfp_text.strip():
        return invalid_argument_response("rfp_text", "rfp_text cannot be empty.")
    if persist:
        guard_engagement(engagement, action="contribute")  # K9/K14: before anything is written under data/engagements/

    try:
        from pipelines.rfp_shredder import RFPShredder

        shredder = RFPShredder(kb_dir="data/kb")
        requirements = shredder.shred_text(rfp_text, engagement=engagement)
        matrix = shredder.build_compliance_matrix(requirements)

        if persist:
            eng_path = server_config.engagements_dir / f"{engagement}.lbug"
            shredder.persist_to_engagement(
                engagement=engagement,
                requirements=requirements,
                db_path=eng_path,
            )

        return ok_response(matrix, count=len(requirements))
    except Exception as e:
        return handle_exception_response(e, context_action="shred_rfp")


def generate_zero_draft_hld(
    engagement: str = "default",
    project_title: str | None = None,
    client_name: str = "Client RFP",
    language: str = "fr",
) -> dict[str, Any]:
    """Generate a structured High-Level Design (HLD) zero-draft from KB assets and RFP requirements in FR or EN.

    Args:
        engagement: Target engagement identifier.
        project_title: Title of the architecture project (optional, defaults to standard title in chosen language).
        client_name: Name of the client or recipient.
        language: Target document language ('fr' or 'en', defaults to 'fr').
    """
    guard_engagement(engagement)  # K9
    try:
        from tools.elicitation.zero_draft import ZeroDraftAssembler

        eng_path = server_config.engagements_dir / f"{engagement}.lbug"
        assembler = ZeroDraftAssembler(
            db_path=eng_path,
            kb_dir="data/kb",
        )
        hld_result = assembler.generate_zero_draft_hld(
            engagement=engagement,
            project_title=project_title,
            client_name=client_name,
            language=language,
        )
        return ok_response(hld_result)
    except Exception as e:
        return handle_exception_response(e, context_action="generate_zero_draft_hld")


def get_rfp_compliance_matrix(
    engagement: str = "default",
) -> dict[str, Any]:
    """Retrieve the triangular compliance matrix (RFP Requirements vs KB Assets vs Controls).

    Args:
        engagement: Target engagement identifier.
    """
    guard_engagement(engagement)  # K9
    try:
        from tools.elicitation.repository import ElicitationRepository

        eng_path = server_config.engagements_dir / f"{engagement}.lbug"
        if not eng_path.exists():
            return ok_response({
                "engagement": engagement,
                "total_requirements": 0,
                "covered": 0,
                "partially_covered": 0,
                "gaps": 0,
                "coverage_rate": 0.0,
                "requirements": [],
            }, count=0)

        repo = ElicitationRepository(db_path=eng_path)
        reqs = repo.get_requirements(engagement)
        total = len(reqs)
        covered = sum(1 for r in reqs if r.get("status") == "covered")
        partial = sum(1 for r in reqs if r.get("status") == "partially_covered")
        gaps = sum(1 for r in reqs if r.get("status") == "gap")

        coverage_rate = round((covered / total * 100), 1) if total > 0 else 0.0

        payload = {
            "engagement": engagement,
            "total_requirements": total,
            "covered": covered,
            "partially_covered": partial,
            "gaps": gaps,
            "coverage_rate": coverage_rate,
            "requirements": reqs,
        }
        return ok_response(payload, count=total)
    except Exception as e:
        return handle_exception_response(e, context_action="get_rfp_compliance_matrix")


def get_rfp_coverage_gaps(
    engagement: str = "default",
    rfp_text: str | None = None,
) -> dict[str, Any]:
    """Analyze KB coverage blind spots (coverage gaps) on an RFP (Issue #133).

    Identifies chapters, sections, and thematic categories with zero or low KB coverage,
    assesses blind spot severity, and suggests candidate frameworks and standards to ingest.

    Args:
        engagement: Target engagement identifier (loads persisted requirements if rfp_text is omitted).
        rfp_text: Optional raw/markdown text of the tender to shred and analyze on the fly.
    """
    guard_engagement(engagement)  # K9
    try:
        from pipelines.rfp_shredder import RFPShredder, compute_rfp_coverage_gaps

        if rfp_text and rfp_text.strip():
            shredder = RFPShredder(kb_dir=server_config.kb_dir)
            requirements = shredder.shred_text(rfp_text, engagement=engagement)
            gaps_report = compute_rfp_coverage_gaps(requirements, kb_dir=server_config.kb_dir)
            gaps_report["engagement"] = engagement
            return ok_response(gaps_report, count=len(gaps_report.get("blind_spots", [])))

        from tools.elicitation.repository import ElicitationRepository

        eng_path = server_config.engagements_dir / f"{engagement}.lbug"
        if not eng_path.exists():
            empty_report = compute_rfp_coverage_gaps([], kb_dir=server_config.kb_dir)
            empty_report["engagement"] = engagement
            return ok_response(empty_report, count=0)

        repo = ElicitationRepository(db_path=eng_path)
        reqs = repo.get_requirements(engagement)
        gaps_report = compute_rfp_coverage_gaps(reqs, kb_dir=server_config.kb_dir)
        gaps_report["engagement"] = engagement
        return ok_response(gaps_report, count=len(gaps_report.get("blind_spots", [])))
    except Exception as e:
        return handle_exception_response(e, context_action="get_rfp_coverage_gaps")


def trigger_rfp_elicitation(
    engagement: str = "default",
) -> dict[str, Any]:
    """Trigger targeted elicitation questions specifically for uncovered RFP requirements (gaps).

    Args:
        engagement: Target engagement identifier.
    """
    guard_engagement(engagement, action="contribute")  # K9/K14
    try:
        from tools.elicitation.zero_draft import ZeroDraftAssembler

        eng_path = server_config.engagements_dir / f"{engagement}.lbug"
        assembler = ZeroDraftAssembler(
            db_path=eng_path,
            kb_dir="data/kb",
        )
        result = assembler.trigger_targeted_elicitation(engagement=engagement)
        return ok_response(result, count=result.get("questions_created", 0))
    except Exception as e:
        return handle_exception_response(e, context_action="trigger_rfp_elicitation")







# ---------------------------------------------------------------------------
# Doctrine context & option judge (contract 1.1) — deterministic, no LLM.
# ---------------------------------------------------------------------------

def _doctrine_index():
    from pipelines.doctrine import load_index

    client = _get_db()
    return load_index(lambda q, p: client.execute_cypher(q, p), server_config.kb_dir)


def _latest_snapshot_id() -> str | None:
    import json

    latest = Path("data/snapshots/latest.json")
    if not latest.exists():
        return None
    try:
        return json.loads(latest.read_text(encoding="utf-8")).get("snapshot_id")
    except Exception:
        return None


def _str_list(value: Any, name: str) -> list[str] | dict[str, Any]:
    """Normalize a list-of-strings argument (a comma-separated string is accepted)."""
    if value is None:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return [v.strip() for v in value if v.strip()]
    return invalid_argument_response(name, f"'{name}' must be a list of strings.")


def _hybrid_weight() -> float | None:
    """``KB_HYBRID_WEIGHT`` in [0, 1]: weighted mean of semantic and lexical relevance; unset: their maximum."""
    from pipelines.doctrine.context import DEFAULT_HYBRID_WEIGHT

    raw = os.getenv("KB_HYBRID_WEIGHT", "").strip()
    try:
        value = float(raw) if raw else None
    except ValueError:
        value = None
    return value if value is not None and 0.0 <= value <= 1.0 else DEFAULT_HYBRID_WEIGHT


def _semantic_relevance(subject: str) -> tuple[dict[str, float] | None, dict[str, Any] | None]:
    """Calibrated semantic relevance of every active asset for ``subject`` with the server's local model, or
    ``(None, None)`` when the model is off or absent (the doctrine context then stays lexical). Never raises."""
    try:
        from pipelines.similarity.encoder import reference_encoder
        from pipelines.similarity.semantic import scorer_for

        encoder, status = reference_encoder()
        if encoder is None:
            return None, None
        scores = scorer_for(encoder).scores(server_config.kb_dir, subject)
        return ({ref: s["semantic"] for ref, s in scores.items()},
                {"model": status["model"], "version": status["version"], "sha256": status["sha256"], "local": True})
    except Exception as exc:  # the lexical ranking is always available
        logger.warning("semantic relevance unavailable, lexical ranking: %s", exc)
        return None, None


def get_doctrine_context(
    subject: str,
    domains: list[str] | None = None,
    frameworks: list[str] | None = None,
    phase: str | None = None,
    max_items: int = 20,
    max_chars: int = 8000,
) -> dict[str, Any]:
    """Return the doctrine that applies to a subject: active principles, required regulatory
    controls, patterns and ADRs, ranked deterministically, with bounded excerpts.

    Args:
        subject: Free text describing the architecture subject (required).
        domains: Optional filter on asset domains (a parent domain matches its sub-domains).
        frameworks: Required regulatory frameworks (e.g. 'NIS2'); all their active controls are included.
        phase: Optional phase filter ('BID', 'BUILD', 'RUN').
        max_items: Maximum number of items (default 20).
        max_chars: Total character budget of the excerpts (default 8000).
    """
    if not subject or not isinstance(subject, str) or not subject.strip():
        return invalid_argument_response("subject", "Parameter 'subject' is required.")
    doms = _str_list(domains, "domains")
    if isinstance(doms, dict):
        return doms
    fws = _str_list(frameworks, "frameworks")
    if isinstance(fws, dict):
        return fws
    if not isinstance(max_items, int) or isinstance(max_items, bool) or not 1 <= max_items <= 200:
        return invalid_argument_response("max_items", "'max_items' must be an integer between 1 and 200.")
    if not isinstance(max_chars, int) or isinstance(max_chars, bool) or not 200 <= max_chars <= 100000:
        return invalid_argument_response("max_chars", "'max_chars' must be an integer between 200 and 100000.")
    try:
        from pipelines.doctrine import build_doctrine_context

        semantic, embedding = _semantic_relevance(subject.strip())
        payload = build_doctrine_context(
            _doctrine_index(),
            subject=subject.strip(),
            domains=doms,
            frameworks=fws,
            phase=phase.strip() if isinstance(phase, str) and phase.strip() else None,
            max_items=max_items,
            max_chars=max_chars,
            snapshot_id=_latest_snapshot_id(),
            semantic=semantic,
            weight=_hybrid_weight(),
            embedding=embedding,
        )
        return ok_response(payload, count=len(payload["items"]))
    except Exception as e:
        return handle_exception_response(e, context_action="get_doctrine_context")


def check_option(
    option: dict[str, Any],
    subject: str | None = None,
    domains: list[str] | None = None,
    frameworks: list[str] | None = None,
) -> dict[str, Any]:
    """Judge an architecture option against the doctrine with deterministic check clauses.

    Returns one verdict per relevant asset: 'supports' or 'violates' when a structured
    check clause applies, 'unassessed' otherwise (to be judged client-side). Every active
    control of a required framework is always returned, at least as 'unassessed'.

    Args:
        option: {"title": str (required), "description": str, "statements": [{"subject", "predicate", "value"}]}.
        subject: Optional free text describing the architecture subject.
        domains: Optional filter on asset domains for the relevant (unassessed) doctrine.
        frameworks: Required regulatory frameworks (e.g. ['NIS2', 'SecNumCloud']).
    """
    if not isinstance(option, dict):
        return invalid_argument_response("option", "'option' must be an object with a 'title'.")
    title = option.get("title")
    if not isinstance(title, str) or not title.strip():
        return invalid_argument_response("option.title", "'option.title' is required.")
    if option.get("statements") is not None and not isinstance(option.get("statements"), list):
        return invalid_argument_response("option.statements", "'option.statements' must be a list.")
    if subject is not None and not isinstance(subject, str):
        return invalid_argument_response("subject", "'subject' must be a string.")
    doms = _str_list(domains, "domains")
    if isinstance(doms, dict):
        return doms
    fws = _str_list(frameworks, "frameworks")
    if isinstance(fws, dict):
        return fws
    try:
        from pipelines.doctrine import check_option as judge

        payload = judge(
            _doctrine_index(),
            option=option,
            subject=subject,
            domains=doms,
            frameworks=fws,
            snapshot_id=_latest_snapshot_id(),
        )
        return ok_response(payload, count=len(payload["verdicts"]))
    except Exception as e:
        return handle_exception_response(e, context_action="check_option")


# ---------------------------------------------------------------------------
# KB candidate cycle (contract 1.2) — queue, automatic checks, human review.
# ---------------------------------------------------------------------------

def _candidate_service():
    from pipelines.kb_candidates.service import CandidateService

    return CandidateService(kb_dir=server_config.kb_dir, doctrine_index_loader=_doctrine_index)


def _actor() -> str:
    """Identity for the candidate history, without ever recording a raw token.

    A person acting through a signed assertion or delegating client (``X-Actor-Token`` or
    ``X-Actor-Email`` with a ``kb:delegate`` token) is recorded by owner handle, or by e-mail
    when not in the registry.
    """
    import hashlib

    from mcp_server.core.auth import delegated_actor_email, get_current_caller, resolve_actor

    actor = resolve_actor()
    if actor:
        return actor.handle if actor.handle else (f"email:{actor.email}" if actor.email else "unknown")

    email = delegated_actor_email()
    if email:
        owner = _candidate_service().owners().by_email(email)
        return owner.handle if owner else f"email:{email}"

    caller = get_current_caller() or "anonymous"
    if caller in ("server_admin", "system", "admin", "default_user", "local_dev", "anonymous"):
        return caller
    return "token:" + hashlib.sha256(caller.encode("utf-8")).hexdigest()[:10]


def _candidate_error(exc: Exception) -> dict[str, Any]:
    from pipelines.kb_candidates.service import CandidateStateError

    res = invalid_argument_response(getattr(exc, "argument", "candidate"), getattr(exc, "reason", str(exc)))
    if isinstance(exc, CandidateStateError):
        res["conflict"] = True
    return res


def submit_kb_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Submit a knowledge base candidate (new asset, amendment, return of experience,
    framework ingestion). Automatic checks run immediately; the candidate then waits for a
    human review by the owner of its domain (status 'in_review') or is blocked ('checks_failed').

    Args:
        candidate: see schemas/kb_candidate.schema.json — required: kind, title, proposed_content,
            source.system; asset_type (except kind 'rex'); target_asset_id for an amendment.
    """
    from pipelines.kb_candidates.model import CandidateError

    try:
        created = _candidate_service().submit(candidate, actor=_actor())
        return ok_response(created, count=1)
    except CandidateError as exc:
        return _candidate_error(exc)
    except Exception as e:
        return handle_exception_response(e, context_action="submit_kb_candidate")


def import_proposal_snapshot(envelope: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
    """Read a sealed snapshot of proposals published by a suite application into candidates (K7, contract 1.33).

    The snapshot is verified whole (schema, canonical-json v1 seal, no duplicate candidate) and refused as a whole when it does not
    verify (``400``, ``problems``). Each proposal then goes through the ordinary cycle: automatic checks and review by a person;
    nothing becomes active here. Idempotent: a candidate already read from the same ``snapshotId`` is reported in ``skipped``.
    """
    from pipelines.kb_candidates.proposals import ProposalSnapshotError, import_snapshot

    try:
        res = import_snapshot(_candidate_service(), envelope, actor=_actor(), dry_run=bool(dry_run))
        return ok_response(res, count=len(res["imported"]))
    except ProposalSnapshotError as exc:
        return {**invalid_argument_response("snapshot", str(exc)),
                "problems": [{"code": p.code, "path": p.path, "message": p.message} for p in exc.problems]}
    except Exception as e:
        return handle_exception_response(e, context_action="import_proposal_snapshot")


def list_kb_candidates(
    status: str | None = None,
    source: str | None = None,
    domain: str | None = None,
    engagement: str | None = None,
) -> dict[str, Any]:
    """List knowledge base candidates, newest first.

    Args:
        status: proposed | checks_failed | in_review | accepted | rejected | published.
        source: Source system (archinex, document-studio, mcp, cli-ingestion).
        domain: Domain filter (a parent domain matches its sub-domains).
        engagement: Source engagement.
    """
    from mcp_server.core.auth import has_scope
    from pipelines.kb_candidates.service import REVIEW_SCOPE, redact

    try:
        items = _candidate_service().find(status=status, source=source, domain=domain, engagement=engagement)
        if not has_scope(REVIEW_SCOPE):
            items = [redact(c) for c in items]
        return ok_response(items, count=len(items))
    except Exception as e:
        return handle_exception_response(e, context_action="list_kb_candidates")


def get_kb_candidate(candidate_id: str) -> dict[str, Any]:
    """Retrieve a knowledge base candidate with its checks, review and history.

    Args:
        candidate_id: Candidate identifier (e.g. 'CAND-20261001-0007').
    """
    from mcp_server.core.auth import has_scope
    from pipelines.kb_candidates.model import CandidateNotFoundError
    from pipelines.kb_candidates.service import REVIEW_SCOPE, redact

    try:
        candidate = _candidate_service().get(candidate_id)
    except CandidateNotFoundError:
        return not_found_response(candidate_id)
    except Exception as e:
        return handle_exception_response(e, context_action="get_kb_candidate")
    return ok_response(candidate if has_scope(REVIEW_SCOPE) else redact(candidate), count=1)


def review_kb_candidate(
    candidate_id: str,
    action: str,
    reviewer: str,
    reason: str | None = None,
    amended_content: str | None = None,
) -> dict[str, Any]:
    """Review a knowledge base candidate (requires the 'kb:review' token scope).

    Args:
        candidate_id: Candidate identifier.
        action: 'accept', 'amend' (accept a modified content) or 'reject'.
        reviewer: Owner handle of the reviewer (declared in data/kb/owners.yaml).
        reason: Motive — required to amend or reject, and to accept content that conflicts with the doctrine.
        amended_content: Full replacement content (front matter + Markdown) for 'amend'.
    """
    from mcp_server.core.auth import delegated_actor_email, has_scope
    from pipelines.kb_candidates.model import CandidateError, CandidateNotFoundError
    from pipelines.kb_candidates.service import REVIEW_SCOPE

    if not has_scope(REVIEW_SCOPE):
        return {"status": "unauthorized", "reason": f"The '{REVIEW_SCOPE}' token scope is required to review candidates."}
    try:
        from mcp_server.core.auth import (
            delegated_actor_email,
            require_distinct_reviewer,
            resolve_actor,
        )

        actor = resolve_actor()
        if actor:
            service = _candidate_service()
            registry = service.owners()
            owner = registry.owners.get(actor.handle)
            if owner is None and actor.email:
                owner = registry.by_email(actor.email)
            if owner is None and actor.auth_method != "assertion":
                return {"status": "unauthorized", "reason": f"'{actor.email or actor.handle}' is not a registered expert."}
            if (reviewer or "").strip() not in ("", actor.handle):
                return {"status": "unauthorized", "reason": "'reviewer' does not match the authenticated expert."}
            reviewer = actor.handle
            candidate = service.get(candidate_id)
            require_distinct_reviewer(reviewer, candidate, reviewer_email=actor.email)
            if not service.may_review(actor.handle, candidate):
                return {"status": "unauthorized",
                        "reason": f"{actor.handle} does not own the domain of this candidate and is not assigned to it."}
        else:
            email = delegated_actor_email()
            if email:
                service = _candidate_service()
                owner = service.owners().by_email(email)
                if owner is None:
                    return {"status": "unauthorized", "reason": f"'{email}' is not a registered expert."}
                if (reviewer or "").strip() not in ("", owner.handle):
                    return {"status": "unauthorized", "reason": "'reviewer' does not match the authenticated expert."}
                reviewer = owner.handle
                candidate = service.get(candidate_id)
                require_distinct_reviewer(reviewer, candidate, reviewer_email=email)
                if not service.may_review(owner.handle, candidate):
                    return {"status": "unauthorized",
                            "reason": f"{owner.handle} does not own the domain of this candidate and is not assigned to it."}

        reviewed = _candidate_service().review(
            candidate_id, action, reviewer, reason=reason, amended_content=amended_content, actor=_actor()
        )
        return ok_response(reviewed, count=1)
    except CandidateNotFoundError:
        return not_found_response(candidate_id)
    except CandidateError as exc:
        return _candidate_error(exc)
    except Exception as e:
        return handle_exception_response(e, context_action="review_kb_candidate")


def get_kb_me() -> dict[str, Any]:
    """Expert the calling client acts for (contract 1.4 / 1.37).

    Requires an assertion token (X-Actor-Token) or a token with the 'kb:delegate' scope and an
    ``X-Actor-Email`` header naming an expert of the registry. Returns the handle, e-mail, KB roles,
    domain roles, active delegations, owned domains and the number of candidates waiting for review.
    """
    from mcp_server.core.auth import delegated_actor_email, resolve_actor
    from pipelines.governance.rbac import get_delegation_store

    try:
        actor = resolve_actor()
        if not actor:
            email = delegated_actor_email()
            if not email:
                return {"status": "unauthorized",
                        "reason": "No acting expert: send X-Actor-Email or X-Actor-Token with a token carrying the 'kb:delegate' scope."}
            service = _candidate_service()
            registry = service.owners()
            owner = registry.by_email(email)
            if owner is None:
                return {"status": "unauthorized", "reason": f"'{email}' is not a registered expert."}
            pending = [
                c for c in service.find(status="in_review")
                if registry.can_review(owner.handle, c.get("domain") or [])
                and (c.get("review") or {}).get("reviewer") != owner.handle
            ]
            return ok_response({
                "handle": owner.handle,
                "email": owner.email,
                "kb_roles": sorted({"kb:review", *owner.roles}),
                "owned_domains": registry.owned_domains(owner.handle),
                "pending_reviews": len(pending),
            }, count=1)

        service = _candidate_service()
        registry = service.owners()
        owner = registry.owners.get(actor.handle)
        roles = sorted({"kb:review", *actor.roles, *(owner.roles if owner else ())})
        owned_domains = registry.owned_domains(actor.handle)
        delegations = get_delegation_store().list_delegations(delegate=actor.handle, active_only=True)
        pending = [
            c for c in service.find(status="in_review")
            if service.may_review(actor.handle, c)
            and (c.get("review") or {}).get("reviewer") != actor.handle
        ]
        return ok_response({
            "handle": actor.handle,
            "email": actor.email,
            "kb_roles": roles,
            "domain_roles": actor.domain_roles,
            "owned_domains": owned_domains,
            "active_delegations": delegations,
            "pending_reviews": len(pending),
            "auth_method": actor.auth_method,
        }, count=1)
    except Exception as e:
        return handle_exception_response(e, context_action="get_kb_me")


# ---------------------------------------------------------------------------
# Review and solicitation of experts (contract 1.5).
# ---------------------------------------------------------------------------

def _governance_error(exc: Exception) -> dict[str, Any]:
    from pipelines.kb_candidates.service import CandidateForbiddenError, GovernanceUnavailableError

    if isinstance(exc, CandidateForbiddenError):
        return {"status": "unauthorized", "reason": exc.reason}
    if isinstance(exc, GovernanceUnavailableError):
        return {"status": "unavailable", "reason": exc.reason}
    return _candidate_error(exc)


def _acting_expert(need_review_scope: bool = True) -> tuple[Any, Any] | dict[str, Any]:
    """(service, owner) of the acting expert, or an ``unauthorized`` envelope."""
    from mcp_server.core.auth import delegated_actor_email, has_scope, resolve_actor
    from pipelines.kb_candidates.owners import Owner
    from pipelines.kb_candidates.service import REVIEW_SCOPE

    if need_review_scope and not has_scope(REVIEW_SCOPE):
        return {"status": "unauthorized", "reason": f"The '{REVIEW_SCOPE}' token scope is required."}

    actor = resolve_actor()
    service = _candidate_service()
    if actor:
        owner = service.owners().owners.get(actor.handle)
        if owner is None:
            if actor.email:
                owner = service.owners().by_email(actor.email)
            if owner is None:
                owner = Owner(handle=actor.handle, email=actor.email, roles=actor.roles)
        return service, owner

    email = delegated_actor_email()
    if not email:
        return {"status": "unauthorized",
                "reason": "No acting expert: send X-Actor-Email or X-Actor-Token with a token carrying the 'kb:delegate' scope."}
    owner = service.owners().by_email(email)
    if owner is None:
        return {"status": "unauthorized", "reason": f"'{email}' is not a registered expert."}
    return service, owner


def get_review_inbox() -> dict[str, Any]:
    """Candidates waiting for the acting expert (contract 1.5), oldest first, with a due date.

    Requires the 'kb:review' scope and an acting expert (see ``get_kb_me``). Reasons: 'review'
    (assigned), 'second_review' (a second reviewer is required), 'advice' (asked for an opinion).
    """
    try:
        who = _acting_expert()
        if isinstance(who, dict):
            return who
        service, owner = who
        items = service.inbox(owner.handle)
        return ok_response({"handle": owner.handle, "items": items}, count=len(items))
    except Exception as e:
        return handle_exception_response(e, context_action="get_review_inbox")


def assign_kb_candidate(candidate_id: str, handle: str, reason: str | None = None) -> dict[str, Any]:
    """Reassign a candidate in review to another owner (acting expert: current owner or 'kb:maintain').

    Args:
        candidate_id: Candidate identifier.
        handle: Owner handle receiving the candidate.
        reason: Motive of the reassignment.
    """
    from pipelines.kb_candidates.model import CandidateError, CandidateNotFoundError

    try:
        who = _acting_expert()
        if isinstance(who, dict):
            return who
        service, owner = who
        return ok_response(service.assign(candidate_id, handle, owner.handle, reason), count=1)
    except CandidateNotFoundError:
        return not_found_response(candidate_id)
    except CandidateError as exc:
        return _governance_error(exc)
    except Exception as e:
        return handle_exception_response(e, context_action="assign_kb_candidate")


def request_kb_review(candidate_id: str, handle: str, kind: str = "second_review", message: str | None = None,
                      due_at: str | None = None) -> dict[str, Any]:
    """Ask a specific expert for a second review or an advisory opinion on a candidate in review.

    Needs the governance database. Args:
        candidate_id: Candidate identifier.
        handle: Owner handle asked.
        kind: 'second_review' or 'advice' (an opinion is not a decision).
        message: Message to the expert.
        due_at: Due date (UTC, e.g. '2026-10-01T09:00:00Z'); default 5 business days.
    """
    from pipelines.kb_candidates.model import CandidateError, CandidateNotFoundError

    try:
        who = _acting_expert()
        if isinstance(who, dict):
            return who
        service, owner = who
        return ok_response(service.request_review(candidate_id, handle, kind, owner.handle, message, due_at), count=1)
    except CandidateNotFoundError:
        return not_found_response(candidate_id)
    except CandidateError as exc:
        return _governance_error(exc)
    except Exception as e:
        return handle_exception_response(e, context_action="request_kb_review")


def comment_kb_candidate(candidate_id: str, body: str) -> dict[str, Any]:
    """Add a comment to the discussion of a candidate (a comment is not a decision).

    Needs the governance database and the 'kb:review' scope; the author is the acting expert
    (or the calling token when there is none).

    Args:
        candidate_id: Candidate identifier.
        body: Comment text.
    """
    from mcp_server.core.auth import has_scope
    from pipelines.kb_candidates.model import CandidateError, CandidateNotFoundError
    from pipelines.kb_candidates.service import REVIEW_SCOPE

    try:
        if not has_scope(REVIEW_SCOPE):
            return {"status": "unauthorized", "reason": f"The '{REVIEW_SCOPE}' token scope is required."}
        return ok_response(_candidate_service().comment(candidate_id, body, _actor()), count=1)
    except CandidateNotFoundError:
        return not_found_response(candidate_id)
    except CandidateError as exc:
        return _governance_error(exc)
    except Exception as e:
        return handle_exception_response(e, context_action="comment_kb_candidate")


def list_kb_comments(candidate_id: str) -> dict[str, Any]:
    """Discussion of a candidate, oldest first (requires the 'kb:review' scope)."""
    from mcp_server.core.auth import has_scope
    from pipelines.kb_candidates.model import CandidateNotFoundError
    from pipelines.kb_candidates.service import REVIEW_SCOPE

    if not has_scope(REVIEW_SCOPE):
        return {"status": "unauthorized", "reason": f"The '{REVIEW_SCOPE}' token scope is required."}
    try:
        items = _candidate_service().comments(candidate_id)
        return ok_response(items, count=len(items))
    except CandidateNotFoundError:
        return not_found_response(candidate_id)
    except Exception as e:
        return handle_exception_response(e, context_action="list_kb_comments")


def get_governance_events(since: int = 0, limit: int = 100) -> dict[str, Any]:
    """Append-only feed of governance events after the cursor ``since`` (requires 'kb:review').

    Each event has ``recipients`` (owner handles who must act or be informed). Poll with the
    returned ``next_cursor``. Needs the governance database.
    """
    from mcp_server.core.auth import has_scope
    from pipelines.governance.log import get_log
    from pipelines.kb_candidates.service import REVIEW_SCOPE

    if not has_scope(REVIEW_SCOPE):
        return {"status": "unauthorized", "reason": f"The '{REVIEW_SCOPE}' token scope is required."}
    try:
        log = get_log()
        if log is None:
            return {"status": "unavailable", "reason": "this feature needs the governance database."}
        feed = log.events_since(max(int(since), 0), min(max(int(limit), 1), 500))
        return ok_response(feed, count=len(feed["events"]))
    except Exception as e:
        return handle_exception_response(e, context_action="get_governance_events")


def list_domain_owners() -> dict[str, Any]:
    """Registry of domain owners: owners (without notification secrets), domains, default owner."""
    try:
        registry = _candidate_service().owners()
        return ok_response({
            "owners": [o.public_dict() for o in sorted(registry.owners.values(), key=lambda o: o.handle)],
            "domains": dict(sorted(registry.domains.items())),
            "default_owner": registry.default_owner,
        }, count=len(registry.owners))
    except Exception as e:
        return handle_exception_response(e, context_action="list_domain_owners")


def update_domain_owners(payload: dict[str, Any]) -> dict[str, Any]:
    """Replace the owners registry (REST ``PUT /api/knowledge/owners``; not an MCP tool).

    Allowed to an acting expert with the 'kb:admin' role, or to a token carrying the
    'kb:admin' scope when no expert acts (bootstrap). Needs the governance database; every
    change is journalled (``owners.updated``).
    """
    from mcp_server.core.auth import delegated_actor_email, has_scope
    from pipelines.governance.log import get_log
    from pipelines.governance.registry import registry_from_payload, save_registry

    try:
        service = _candidate_service()
        email = delegated_actor_email()
        if email:
            owner = service.owners().by_email(email)
            if owner is None or "kb:admin" not in owner.roles:
                return {"status": "unauthorized", "reason": "the 'kb:admin' role is required to edit the registry."}
            actor = owner.handle
        elif has_scope("kb:admin"):
            actor = _actor()
        else:
            return {"status": "unauthorized", "reason": "the 'kb:admin' role or token scope is required."}
        log = get_log()
        if log is None:
            return {"status": "unavailable", "reason": "this feature needs the governance database."}
        current = service.owners()
        for item in payload.get("owners") or []:  # the public view omits notification secrets: keep them
            existing = current.owners.get(str(item.get("handle"))) if isinstance(item, dict) else None
            if existing is not None:
                item.setdefault("discord_webhook", existing.discord_webhook)
                item.setdefault("ntfy_topic", existing.ntfy_topic)
        try:
            registry = registry_from_payload(payload)
        except ValueError as exc:
            return invalid_argument_response("owners", str(exc))
        save_registry(registry)
        log.emit("owners.updated", None, actor, [registry.default_owner], owners=len(registry.owners))
        return ok_response({"owners": len(registry.owners), "domains": len(registry.domains),
                            "default_owner": registry.default_owner}, count=1)
    except Exception as e:
        return handle_exception_response(e, context_action="update_domain_owners")


# ---------------------------------------------------------------------------
# Doctrine workshop and evaluations (contract 1.6) — REST only, no MCP tool.
# ---------------------------------------------------------------------------

def _eval_error(exc: Exception) -> dict[str, Any] | None:
    from pipelines.governance.evals import EvalError, EvalNotFoundError

    if isinstance(exc, EvalError):
        return invalid_argument_response(exc.argument, exc.reason)
    if isinstance(exc, EvalNotFoundError):
        return not_found_response(str(exc))
    return None


def _eval_store():
    from pipelines.governance.evals import EvalStore
    from pipelines.governance.store import database_url

    return EvalStore() if database_url() else None


_NO_DB = {"status": "unavailable", "reason": "this feature needs the governance database."}


def _actor_with_role(*roles: str) -> tuple[Any, Any] | dict[str, Any]:
    """(service, owner) of an acting expert holding one of ``roles`` (``kb:maintain`` always suffices)."""
    who = _acting_expert()
    if isinstance(who, dict):
        return who
    service, owner = who
    if not ({*roles, "kb:maintain"} & set(owner.roles)):
        return {"status": "unauthorized", "reason": f"{owner.handle} needs the '{roles[0]}' role."}
    return service, owner


def _evaluator() -> tuple[Any, Any] | dict[str, Any]:
    return _actor_with_role("kb:evaluate")


def get_asset_template(asset_type: str) -> dict[str, Any]:
    """Structured template of an asset type (fields with vocabularies, expected sections, skeleton)."""
    from pipelines.kb_candidates.templates import TYPES, asset_template

    try:
        tpl = asset_template(asset_type, server_config.kb_dir)
        if tpl is None:
            return not_found_response(f"{asset_type} (expected one of {list(TYPES)})")
        return ok_response(tpl, count=1)
    except Exception as e:
        return handle_exception_response(e, context_action="get_asset_template")


def validate_kb_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Dry run of the automatic checks on a submission: nothing is created, nobody is notified."""
    from pipelines.kb_candidates.model import CandidateError

    try:
        return ok_response(_candidate_service().dry_run(candidate, actor=_actor()), count=1)
    except CandidateError as exc:
        return _candidate_error(exc)
    except Exception as e:
        return handle_exception_response(e, context_action="validate_kb_candidate")


def simulate_checks(body: dict[str, Any]) -> dict[str, Any]:
    """Evaluate proposed clauses of an asset against the evaluation cases and free options.

    Body: ``{asset_id, checks: [...], dataset?: 'check_option_v1', only_validated?: bool,
    options?: [{title, description, subject?}], frameworks?: [...]}``. Deterministic; no write.
    """
    import json

    from pipelines.doctrine.simulate import simulate

    try:
        asset_id, checks = body.get("asset_id"), body.get("checks")
        if not isinstance(asset_id, str) or not asset_id.strip():
            return invalid_argument_response("asset_id", "'asset_id' is required.")
        if not isinstance(checks, list):
            return invalid_argument_response("checks", "'checks' must be a list of clauses.")
        options = body.get("options") or []
        if not isinstance(options, list) or not all(isinstance(o, dict) and str(o.get("title") or "").strip() for o in options):
            return invalid_argument_response("options", "'options' must be a list of objects with a 'title'.")
        dataset = body.get("dataset", "check_option_v1")
        cases: list[dict[str, Any]] = []
        if dataset:
            store = _eval_store()
            if store is not None and store.has_dataset(dataset):
                cases = store.cases(dataset)
            elif dataset == "check_option_v1":
                path = Path("tests/evals/datasets/check_option_v1.jsonl")
                if path.is_file():
                    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            else:
                return not_found_response(str(dataset))
        if body.get("only_validated"):
            cases = [c for c in cases if c.get("annotation_status") == "validated"]
        fws = _str_list(body.get("frameworks"), "frameworks")
        if isinstance(fws, dict):
            return fws
        result = simulate(_doctrine_index(), asset_id.strip(), checks, cases, options, fws)
        return ok_response(result, count=len(result["cases"]))
    except LookupError as exc:
        return not_found_response(str(exc))
    except ValueError as exc:
        return invalid_argument_response("checks", str(exc))
    except Exception as e:
        return handle_exception_response(e, context_action="simulate_checks")


def get_eval_dataset(dataset: str) -> dict[str, Any]:
    """Cases of an evaluation dataset with their annotation status (requires 'kb:review')."""
    from mcp_server.core.auth import has_scope
    from pipelines.kb_candidates.service import REVIEW_SCOPE

    if not has_scope(REVIEW_SCOPE):
        return {"status": "unauthorized", "reason": f"The '{REVIEW_SCOPE}' token scope is required."}
    store = _eval_store()
    if store is None:
        return _NO_DB
    try:
        cases = store.cases(dataset)
        validated = sum(1 for c in cases if c["annotation_status"] == "validated")
        return ok_response({"dataset": dataset, "cases": cases, "validated": validated, "runs": store.runs(dataset)[:10]},
                           count=len(cases))
    except Exception as e:
        return _eval_error(e) or handle_exception_response(e, context_action="get_eval_dataset")


def annotate_eval_case(dataset: str, case_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Annotate a case: ``{expected?: {typed_id: violates|supports}, annotation_status?}``.

    Requires an acting expert with the 'kb:evaluate' role; the annotator is that expert.
    """
    who = _evaluator()
    if isinstance(who, dict):
        return who
    store = _eval_store()
    if store is None:
        return _NO_DB
    _, owner = who
    if body.get("expected") is None and body.get("annotation_status") is None:
        # An unknown payload must not look like a successful annotation (silent no-op).
        return invalid_argument_response("body", "send 'expected' and/or 'annotation_status'.")
    try:
        case = store.annotate(dataset, case_id, owner.handle, body.get("expected"), body.get("annotation_status"))
        from pipelines.governance.log import get_log

        log = get_log()
        if log is not None:
            log.emit("eval.updated", None, owner.handle, [], dataset=dataset, case_id=case_id,
                     annotation_status=case["annotation_status"])
        return ok_response(case, count=1)
    except Exception as e:
        return _eval_error(e) or handle_exception_response(e, context_action="annotate_eval_case")


def add_eval_case(dataset: str, body: dict[str, Any]) -> dict[str, Any]:
    """New case ``{option, subject?, frameworks?, sector?, expected}`` in status 'proposed' ('kb:evaluate')."""
    who = _evaluator()
    if isinstance(who, dict):
        return who
    store = _eval_store()
    if store is None:
        return _NO_DB
    try:
        return ok_response(store.add_case(dataset, body, who[1].handle), count=1)
    except Exception as e:
        return _eval_error(e) or handle_exception_response(e, context_action="add_eval_case")


def run_eval(dataset: str, validated_only: bool = False) -> dict[str, Any]:
    """Run the option judge on the dataset ('kb:evaluate'); the run is stored and announced (``eval.updated``)."""
    from pipelines.doctrine.evaluation import evaluate_cases, summarize
    from pipelines.doctrine.simulate import judge_for
    from pipelines.governance.log import get_log

    who = _evaluator()
    if isinstance(who, dict):
        return who
    store = _eval_store()
    if store is None:
        return _NO_DB
    try:
        cases = [c for c in store.cases(dataset) if c.get("expected")]
        if validated_only:
            cases = [c for c in cases if c["annotation_status"] == "validated"]
        metrics = summarize(evaluate_cases(cases, judge_for(_doctrine_index())))
        metrics["validated_only"] = validated_only
        run = store.save_run(dataset, who[1].handle, metrics)
        log = get_log()
        if log is not None:
            log.emit("eval.updated", None, who[1].handle, [], dataset=dataset, run_id=run["id"],
                     violation_recall=round(metrics["violation_recall"], 4))
        return ok_response(run, count=1)
    except Exception as e:
        return _eval_error(e) or handle_exception_response(e, context_action="run_eval")


def get_eval_run(dataset: str, run_id: int) -> dict[str, Any]:
    """A stored evaluation run (requires 'kb:review')."""
    from mcp_server.core.auth import has_scope
    from pipelines.kb_candidates.service import REVIEW_SCOPE

    if not has_scope(REVIEW_SCOPE):
        return {"status": "unauthorized", "reason": f"The '{REVIEW_SCOPE}' token scope is required."}
    store = _eval_store()
    if store is None:
        return _NO_DB
    try:
        return ok_response(store.run(dataset, run_id), count=1)
    except Exception as e:
        return _eval_error(e) or handle_exception_response(e, context_action="get_eval_run")


def submit_verdict_feedback(body: dict[str, Any]) -> dict[str, Any]:
    """Human feedback on a verdict of ``check_option`` (any authenticated client).

    Body: ``{typed_id, check_id?, feedback: wrong_violation|missed_violation|correct, justification,
    option: {title, description?}, subject?, frameworks?}``. Stored for an evaluator to convert.
    """
    store = _eval_store()
    if store is None:
        return _NO_DB
    try:
        reporter = _actor()
        context = {"option": body.get("option"), "subject": body.get("subject"), "frameworks": body.get("frameworks") or []}
        fb = store.add_feedback(reporter, str(body.get("typed_id") or ""), str(body.get("feedback") or ""),
                                str(body.get("justification") or ""), context, body.get("check_id"))
        return ok_response(fb, count=1)
    except Exception as e:
        return _eval_error(e) or handle_exception_response(e, context_action="submit_verdict_feedback")


def list_verdict_feedback(status: str | None = None) -> dict[str, Any]:
    """Verdict feedback waiting for an evaluator (requires 'kb:review')."""
    from mcp_server.core.auth import has_scope
    from pipelines.kb_candidates.service import REVIEW_SCOPE

    if not has_scope(REVIEW_SCOPE):
        return {"status": "unauthorized", "reason": f"The '{REVIEW_SCOPE}' token scope is required."}
    store = _eval_store()
    if store is None:
        return _NO_DB
    try:
        items = store.list_feedback(status or None)
        return ok_response(items, count=len(items))
    except Exception as e:
        return handle_exception_response(e, context_action="list_verdict_feedback")


def convert_verdict_feedback(feedback_id: int, body: dict[str, Any]) -> dict[str, Any]:
    """Convert feedback ('kb:evaluate'): ``{to: 'eval_case', dataset, expected: violates|supports}``,
    ``{to: 'amendment', target_asset_id, asset_type, proposed_content}`` or ``{to: 'dismiss'}``."""
    from pipelines.governance.evals import EvalError
    from pipelines.kb_candidates.model import CandidateError

    who = _evaluator()
    if isinstance(who, dict):
        return who
    service, owner = who
    store = _eval_store()
    if store is None:
        return _NO_DB
    try:
        fb = store.feedback(feedback_id)
        if fb["status"] != "open":
            return {**invalid_argument_response("status", f"feedback already {fb['status']}."), "conflict": True}
        target = body.get("to")
        if target == "eval_case":
            case = store.add_case(str(body.get("dataset") or "check_option_v1"), {
                "option": fb["option"], "subject": fb.get("subject"), "frameworks": fb.get("frameworks"),
                "expected": {fb["typed_id"]: body.get("expected")}}, owner.handle)
            return ok_response(store.close_feedback(feedback_id, "converted", f"eval_case:{case['id']}"), count=1)
        if target == "amendment":
            candidate = service.submit({
                "kind": "amendment", "asset_type": body.get("asset_type"), "target_asset_id": body.get("target_asset_id"),
                "title": f"Verdict feedback on {fb['typed_id']}", "rationale": fb["justification"],
                "proposed_content": body.get("proposed_content"),
                "source": {"system": "archinex", "author": owner.handle},
            }, actor=owner.handle)
            return ok_response(store.close_feedback(feedback_id, "converted", f"candidate:{candidate['id']}"), count=1)
        if target == "dismiss":
            return ok_response(store.close_feedback(feedback_id, "dismissed"), count=1)
        return invalid_argument_response("to", "'to' must be 'eval_case', 'amendment' or 'dismiss'.")
    except (EvalError, CandidateError) as exc:
        return invalid_argument_response(getattr(exc, "argument", "body"), getattr(exc, "reason", str(exc)))
    except Exception as e:
        return _eval_error(e) or handle_exception_response(e, context_action="convert_verdict_feedback")


# ---------------------------------------------------------------------------
# Framework ingestion through the API (contract 1.7) — REST only.
# ---------------------------------------------------------------------------

def _ingestion_service(service: Any = None):
    from pipelines.frameworks.api import IngestionService
    from pipelines.governance.store import database_url

    if not database_url():
        return None
    return IngestionService(server_config.kb_dir, service)


def _ingestion_error(exc: Exception) -> dict[str, Any] | None:
    from pipelines.frameworks.api import IngestionError, IngestionNotFoundError

    if isinstance(exc, IngestionError):
        res = invalid_argument_response(exc.argument, exc.reason)
        if getattr(exc, "conflict", False):
            res["conflict"] = True
        return res
    if isinstance(exc, IngestionNotFoundError):
        return not_found_response(str(exc))
    return None


def create_framework_ingestion(framework: str, version: str, tag: str, filename: str, data: bytes) -> dict[str, Any]:
    """Upload a regulatory source and split it into draft requirements ('kb:maintain').

    The extraction runs in a bounded subprocess (20 MB, 120 s). The framework needs a splitter
    (``pipelines/frameworks/splitters/<framework>.yaml``). Re-ingesting a new version or source
    resets the coverage declaration.
    """
    from pipelines.governance.log import get_log

    who = _actor_with_role("kb:maintain")
    if isinstance(who, dict):
        return who
    ingestion = _ingestion_service(who[0])
    if ingestion is None:
        return _NO_DB
    try:
        created = ingestion.create(framework, version, tag, filename, data, who[1].handle)
        log = get_log()
        if log is not None:
            log.emit("coverage.changed", None, who[1].handle, [], framework=created["framework"],
                     reason="ingested", version=created["version"])
        return ok_response(created, count=created["total"])
    except Exception as e:
        return _ingestion_error(e) or handle_exception_response(e, context_action="create_framework_ingestion")


def list_framework_ingestions(status: str | None = None) -> dict[str, Any]:
    """Ingestions in progress or done, and the frameworks that have a splitter (requires 'kb:review')."""
    from mcp_server.core.auth import has_scope
    from pipelines.frameworks.api import supported_frameworks
    from pipelines.kb_candidates.service import REVIEW_SCOPE

    if not has_scope(REVIEW_SCOPE):
        return {"status": "unauthorized", "reason": f"The '{REVIEW_SCOPE}' token scope is required."}
    ingestion = _ingestion_service()
    if ingestion is None:
        return _NO_DB
    try:
        items = ingestion.list(status=status)
        return ok_response({"ingestions": items, "splitters": supported_frameworks()}, count=len(items))
    except Exception as e:
        return _ingestion_error(e) or handle_exception_response(e, context_action="list_framework_ingestions")


def get_framework_ingestion(ingestion_id: int) -> dict[str, Any]:
    """Requirements of an ingestion with legal text, proposals and the decision of each row ('kb:review')."""
    from mcp_server.core.auth import has_scope
    from pipelines.kb_candidates.service import REVIEW_SCOPE

    if not has_scope(REVIEW_SCOPE):
        return {"status": "unauthorized", "reason": f"The '{REVIEW_SCOPE}' token scope is required."}
    ingestion = _ingestion_service()
    if ingestion is None:
        return _NO_DB
    try:
        res = ingestion.get(ingestion_id)
        return ok_response(res, count=res["total"])
    except Exception as e:
        return _ingestion_error(e) or handle_exception_response(e, context_action="get_framework_ingestion")


def decide_ingestion_row(ingestion_id: int, requirement_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Decision on one requirement: ``{decision: accept|amend|reject|'', links?, acceptance_criteria?, comment?}``.

    The reviewer is the acting expert, who must own the domain of the requirement (or be a maintainer).
    """
    who = _acting_expert()
    if isinstance(who, dict):
        return who
    service, owner = who
    ingestion = _ingestion_service(service)
    if ingestion is None:
        return _NO_DB
    try:
        row = ingestion._row(ingestion_id, requirement_id)
        if not service.owners().can_review(owner.handle, row.get("domain") or []):
            return {"status": "unauthorized", "reason": f"{owner.handle} does not own the domain of {requirement_id}."}
        return ok_response(ingestion.decide(ingestion_id, requirement_id, owner.handle, body), count=1)
    except Exception as e:
        return _ingestion_error(e) or handle_exception_response(e, context_action="decide_ingestion_row")


def add_ingestion_link_proposals(ingestion_id: int, body: dict[str, Any]) -> dict[str, Any]:
    """Links proposed by the client's own LLM (stored as 'llm-derived'; unknown asset ids are dropped).

    Body: ``{model?, proposals: [{requirement_id, satisfied_by: [ids], acceptance_criteria: [text]}]}``.
    """
    who = _actor_with_role("kb:maintain")
    if isinstance(who, dict):
        return who
    ingestion = _ingestion_service(who[0])
    if ingestion is None:
        return _NO_DB
    try:
        return ok_response(ingestion.add_link_proposals(ingestion_id, body.get("proposals"), body.get("model")), count=1)
    except Exception as e:
        return _ingestion_error(e) or handle_exception_response(e, context_action="add_ingestion_link_proposals")


def apply_framework_ingestion(ingestion_id: int) -> dict[str, Any]:
    """Same as ``kb apply-review``: create the reviewed candidates and promote the accepted ones ('kb:maintain')."""
    who = _actor_with_role("kb:maintain")
    if isinstance(who, dict):
        return who
    ingestion = _ingestion_service(who[0])
    if ingestion is None:
        return _NO_DB
    try:
        return ok_response(ingestion.apply(ingestion_id, who[1].handle), count=1)
    except Exception as e:
        return _ingestion_error(e) or handle_exception_response(e, context_action="apply_framework_ingestion")


def abandon_framework_ingestion(ingestion_id: int, reason: str) -> dict[str, Any]:
    """Mark an unapplied ingestion as ``abandoned`` ('kb:maintain', mandatory reason)."""
    from pipelines.governance.log import get_log

    who = _actor_with_role("kb:maintain")
    if isinstance(who, dict):
        return who
    ingestion = _ingestion_service(who[0])
    if ingestion is None:
        return _NO_DB
    try:
        abandoned = ingestion.abandon(ingestion_id, who[1].handle, reason)
        log = get_log()
        if log is not None:
            log.emit(
                "ingestion.abandoned",
                None,
                who[1].handle,
                [],
                ingestion_id=ingestion_id,
                framework=abandoned["framework"],
                version=abandoned["version"],
                reason=abandoned["abandon_reason"],
            )
        return ok_response(abandoned, count=abandoned["total"])
    except Exception as e:
        return _ingestion_error(e) or handle_exception_response(e, context_action="abandon_framework_ingestion")


def declare_framework_coverage(framework: str) -> dict[str, Any]:
    """Declare a framework covered, as the acting expert; refused with the list of what is missing (409)."""
    from mcp_server.core.auth import resolve_actor
    from pipelines.frameworks.coverage import (
        CoverageDeclarationError,
        declare_coverage,
        framework_primary_domain,
    )
    from pipelines.governance.audit import get_governance_audit
    from pipelines.governance.log import get_log
    from pipelines.governance.rbac import expert_can_review_domain

    who = _acting_expert()
    if isinstance(who, dict):
        return who
    service, owner = who
    actor = resolve_actor()
    audit = get_governance_audit()
    method = actor.auth_method if actor else "header"
    try:
        # Declaring a framework covered answers for its content: the owner of its primary domain, a maintainer, or an expert
        # holding the review role on that domain (assertion claim or delegation) may do it; no one else (issue #90).
        primary = framework_primary_domain(framework, server_config.kb_dir)
        if not expert_can_review_domain(owner.handle, [primary] if primary else [], service.owners(),
                                        domain_roles=actor.domain_roles if actor else None):
            reason = (f"{owner.handle} does not own the primary domain '{primary}' of {framework} and holds no 'kb:maintain' role."
                      if primary else f"{framework} has no control: only a maintainer may declare it.")
            audit.record(owner.handle, "declare_framework_coverage", "denied", resource=framework,
                         detail={"reason": reason, "primary_domain": primary}, auth_method=method)
            return {"status": "unauthorized", "reason": reason}
        try:
            cov = declare_coverage(framework, owner.handle, server_config.kb_dir)
        except CoverageDeclarationError as exc:
            return {**invalid_argument_response("framework", str(exc)), "conflict": True}
        audit.record(owner.handle, "declare_framework_coverage", "allowed", resource=framework,
                     detail={"primary_domain": primary}, auth_method=method)
        log = get_log()
        if log is not None:
            log.emit("coverage.changed", None, owner.handle, [], framework=framework, reason="declared")
        return ok_response(cov, count=1)
    except Exception as e:
        return handle_exception_response(e, context_action="declare_framework_coverage")


# ---------------------------------------------------------------------------
# Promotion, publication and health (contract 1.8) — REST only.
# ---------------------------------------------------------------------------

def promote_kb_candidate(candidate_id: str) -> dict[str, Any]:
    """Write an accepted candidate into the knowledge base on the server ('kb:maintain').

    ``warnings`` contains ``ephemeral-storage`` on a demo deployment: the promoted asset is lost
    at the next restart unless the maintainer exports it.
    """
    from pipelines.kb_candidates.confidence import NotPublishableError
    from pipelines.kb_candidates.model import CandidateError, CandidateNotFoundError
    from pipelines.publication.local_publisher import storage_warnings

    who = _actor_with_role("kb:maintain")
    if isinstance(who, dict):
        return who
    service, owner = who
    try:
        promoted = service.promote(candidate_id, actor=owner.handle)
        return {**ok_response(promoted, count=1), "warnings": storage_warnings()}
    except CandidateNotFoundError:
        return not_found_response(candidate_id)
    except NotPublishableError as exc:
        return invalid_argument_response("candidate", str(exc))
    except CandidateError as exc:
        return _governance_error(exc)
    except Exception as e:
        return handle_exception_response(e, context_action="promote_kb_candidate")


def publish_kb_candidates() -> dict[str, Any]:
    """Publish the promoted candidates ('kb:maintain'): rebuild the graph, seal a snapshot, write the
    changelog, notify the consumers, mark the candidates ``published``."""
    from pipelines.publication.local_publisher import publish, storage_warnings

    who = _actor_with_role("kb:maintain")
    if isinstance(who, dict):
        return who
    service, owner = who
    try:
        result = publish(service, Path(server_config.kb_dir), Path(server_config.knowledge_db_path),
                         Path("data/snapshots"), owner.handle)
        return {**ok_response(result, count=len(result.get("published") or [])), "warnings": storage_warnings()}
    except Exception as e:
        return handle_exception_response(e, context_action="publish_kb_candidates")


def list_knowledge_publications(entry_type: str | None = None, framework: str | None = None) -> dict[str, Any]:
    """List sealed snapshot publications of the knowledge base with changelog and entry paths (contract 1.27)."""
    try:
        from pipelines.publication.history import get_publications
        res = get_publications(
            Path(server_config.kb_dir),
            snapshots_dir=Path("data/snapshots"),
            entry_type=entry_type,
            framework=framework,
        )
        return res
    except Exception as e:
        return handle_exception_response(e, context_action="list_knowledge_publications")


def get_knowledge_asset_history(asset_id: str) -> dict[str, Any]:
    """Retrieve full successive revision history, entry path, and clause decisions for an asset (contract 1.27)."""
    if not asset_id:
        return invalid_argument_response("asset_id", "An asset identifier is required.")
    try:
        from pipelines.publication.history import get_asset_history
        res = get_asset_history(
            asset_id,
            Path(server_config.kb_dir),
            snapshots_dir=Path("data/snapshots"),
        )
        return res
    except Exception as e:
        return handle_exception_response(e, context_action="get_knowledge_asset_history")


def list_check_clauses(status: str | None = None, framework: str | None = None, asset_type: str | None = None,
                       asset_id: str | None = None) -> dict[str, Any]:
    """Check clauses of the active doctrine with their own status (contract 1.26, requires 'kb:review').

    Each row carries its asset (title, legal text excerpt, framework, severity, domain), the rule (kind, when, expect,
    message), its status (draft | validated | rejected) and the last decision. ``may_decide`` tells whether the acting
    expert can decide on it. ``mandatory_without_clause`` lists the mandatory controls nothing can enforce yet, and
    ``pending_publication`` the decisions waiting for the next publication.
    """
    from mcp_server.core.auth import delegated_actor_email, has_scope
    from pipelines.doctrine.checks import CLAUSE_STATUSES
    from pipelines.kb_candidates.clauses import (
        list_clauses,
        mandatory_without_clause,
        pending_decisions,
    )
    from pipelines.kb_candidates.service import REVIEW_SCOPE

    if not has_scope(REVIEW_SCOPE):
        return {"status": "unauthorized", "reason": f"The '{REVIEW_SCOPE}' token scope is required."}
    if status is not None and status not in CLAUSE_STATUSES:
        return invalid_argument_response("status", f"'status' must be one of {list(CLAUSE_STATUSES)}.")
    try:
        kb = Path(server_config.kb_dir)
        rows = list_clauses(kb, status=status, framework=framework, asset_type=asset_type, asset_id=asset_id)
        email = delegated_actor_email()
        registry = _candidate_service().owners()
        owner = registry.by_email(email) if email else None
        for row in rows:
            row["may_decide"] = bool(owner and registry.can_review(owner.handle, row["domain"]))
        counts = {s: sum(1 for r in rows if r["status"] == s) for s in CLAUSE_STATUSES}
        data = {"clauses": rows, "counts": counts,
                "mandatory_without_clause": [] if asset_id else mandatory_without_clause(kb, framework),
                "pending_publication": len(pending_decisions(kb))}
        return ok_response(data, count=len(rows))
    except Exception as e:
        return handle_exception_response(e, context_action="list_check_clauses")


def decide_check_clause(asset_id: str, check_id: str, decision: str, comment: str | None = None,
                        clause: dict[str, Any] | None = None) -> dict[str, Any]:
    """Decide on one check clause (contract 1.26): 'validate', 'amend' (validate a corrected clause) or 'reject'.

    Requires 'kb:review' and an acting expert owning the asset's domain (or ``kb:maintain``). A comment is required to
    amend or reject. The asset gets a new revision and the decision enters the trail; it takes effect for the judge
    at the next publication (``POST /api/knowledge/publications``).
    """
    from pipelines.kb_candidates.clauses import decide, find_asset
    from pipelines.kb_candidates.model import CandidateError, CandidateNotFoundError

    who = _acting_expert()
    if isinstance(who, dict):
        return who
    service, owner = who
    try:
        kb = Path(server_config.kb_dir)
        asset = find_asset(kb, asset_id)
        domain = asset.frontmatter.get("domain") or []
        if not service.owners().can_review(owner.handle, [str(d) for d in (domain if isinstance(domain, list) else [domain])]):
            return {"status": "unauthorized", "reason": f"{owner.handle} does not own the domain of {asset_id}."}
        row = decide(kb, asset_id, check_id, decision, owner.handle, comment=comment, amended=clause)
        return ok_response(row, count=1)
    except CandidateNotFoundError as exc:
        return not_found_response(str(exc))
    except CandidateError as exc:
        return _candidate_error(exc)
    except Exception as e:
        return handle_exception_response(e, context_action="decide_check_clause")


def _compiled_base_status() -> dict[str, Any] | None:
    """Issue #85: does the compiled graph describe the files? ``None`` if the check itself failed (never an exception)."""
    from pipelines.kb_consistency import check_compiled_base

    try:
        client = _get_db()
        return check_compiled_base(server_config.kb_dir, lambda q, p: client.execute_cypher(q, p))
    except Exception:
        return None


def warn_if_compiled_base_is_not_current() -> dict[str, Any] | None:
    """Log a clear warning at start when the compiled graph does not describe the knowledge base files (issue #85).

    Reports only: the graph is never rebuilt here, a maintainer decides. Returns the report (``None`` if unchecked)."""
    import logging

    report = _compiled_base_status()
    if report is None or report["status"] == "ok":
        return report
    log = logging.getLogger("mcp_server.knowledge")
    if report["status"] == "stale":
        changed = report["changed_since_build"]["count"] + report["not_in_base"]["count"] + report["removed_from_files"]["count"]
        log.warning("STALE KNOWLEDGE GRAPH: %d asset(s) differ from the files (%s). %s", changed,
                    ", ".join((report["changed_since_build"]["ids"] + report["not_in_base"]["ids"]
                               + report["removed_from_files"]["ids"])[:8]), report["reason"])
    else:
        log.warning("UNVERIFIED KNOWLEDGE GRAPH: %s", report["reason"])
    return report


def get_kb_health() -> dict[str, Any]:
    """Health indicators of the knowledge base (requires 'kb:review'): assets by type and domain,
    unvalidated assets, draft clauses, coverage per framework, review queue age per owner, overdue
    candidates, last evaluation, last snapshot and storage mode (``persistent`` is false on the demo)."""
    from mcp_server.core.auth import has_scope
    from pipelines.kb_candidates.service import REVIEW_SCOPE
    from pipelines.publication.health import kb_health

    if not has_scope(REVIEW_SCOPE):
        return {"status": "unauthorized", "reason": f"The '{REVIEW_SCOPE}' token scope is required."}
    try:
        report = kb_health(_candidate_service(), Path(server_config.kb_dir), Path("data/snapshots"),
                           compiled_base=_compiled_base_status())
        return ok_response(report, count=1)
    except Exception as e:
        return handle_exception_response(e, context_action="get_kb_health")


def get_kb_freshness(
    framework: str | None = None,
    owner: str | None = None,
    days: int = 180,
) -> dict[str, Any]:
    """Regulatory and doctrine freshness indicators (requires 'kb:review') (Issue #131).

    Detects overdue reviews, upstream standard version drifts, and controls requiring clause revalidation.
    """
    from mcp_server.core.auth import has_scope
    from pipelines.governance.freshness import check_kb_freshness
    from pipelines.kb_candidates.service import REVIEW_SCOPE

    if not has_scope(REVIEW_SCOPE):
        return {"status": "unauthorized", "reason": f"The '{REVIEW_SCOPE}' token scope is required."}
    try:
        report = check_kb_freshness(Path(server_config.kb_dir), default_review_cycle_days=days)
        if framework:
            fw_lower = framework.lower()
            report["source_drifts"] = [d for d in report["source_drifts"] if str(d.get("framework") or "").lower() == fw_lower]
            report["overdue_reviews"] = [o for o in report["overdue_reviews"] if o.get("type") == "control" and fw_lower in o.get("id", "").lower()]
        if owner:
            owner_clean = owner if owner.startswith("@") else f"@{owner}"
            report["overdue_reviews"] = [o for o in report["overdue_reviews"] if o.get("owner") == owner_clean]
            report["source_drifts"] = [d for d in report["source_drifts"] if d.get("owner") == owner_clean]
            report["doctrine_dependencies"] = [a for a in report["doctrine_dependencies"] if a.get("owner") == owner_clean]
            report["alerts_by_owner"] = {k: v for k, v in report["alerts_by_owner"].items() if k == owner_clean}
        return ok_response(report, count=len(report["source_drifts"]) + len(report["overdue_reviews"]))
    except Exception as e:
        return handle_exception_response(e, context_action="get_kb_freshness")



# ---------------------------------------------------------------------------
# Semantic similarity (contract 1.9) — vectors computed by the client, REST only.
# ---------------------------------------------------------------------------

def _embedding_store():
    from pipelines.governance.store import database_url
    from pipelines.similarity.store import EmbeddingStore

    return EmbeddingStore() if database_url() else None


def get_embeddings_pending(model: str) -> dict[str, Any]:
    """Assets and controls whose vector the client must (re)compute for ``model`` (requires 'kb:review').

    Each item carries the **text to encode** and its SHA-256; a vector deposited for another text is refused.
    ``reason`` is ``missing`` (no vector) or ``stale`` (the asset changed since its vector was computed).
    """
    from mcp_server.core.auth import has_scope
    from pipelines.kb_candidates.service import REVIEW_SCOPE
    from pipelines.similarity.text import embeddable_assets

    if not has_scope(REVIEW_SCOPE):
        return {"status": "unauthorized", "reason": f"The '{REVIEW_SCOPE}' token scope is required."}
    if not isinstance(model, str) or not model.strip():
        return invalid_argument_response("model", "'model' is required (identifier of the embedding model).")
    store = _embedding_store()
    if store is None:
        return _NO_DB
    try:
        stored = store.hashes(model)
        items = []
        for a in embeddable_assets(server_config.kb_dir):
            if a["ref"] not in stored:
                items.append({**a, "reason": "missing"})
            elif stored[a["ref"]] != a["text_sha256"]:
                items.append({**a, "reason": "stale"})
        space = store.model_space(model)
        return ok_response({"model": model, "dim": space[0] if space else None,
                            "model_version": space[1] if space else None,
                            "pending": items, "models": store.models()}, count=len(items))
    except Exception as e:
        return handle_exception_response(e, context_action="get_embeddings_pending")


def put_embeddings(body: dict[str, Any]) -> dict[str, Any]:
    """Deposit vectors computed by the client: ``{model, model_version, items: [{ref, text_sha256, vector, language?}]}``.

    Requires 'kb:review'. With an acting expert the role 'kb:maintain' is needed; without one (system
    synchronisation by the client) the service token suffices. Stale or foreign vectors are refused (400).
    """
    from mcp_server.core.auth import delegated_actor_email, has_scope
    from pipelines.kb_candidates.service import REVIEW_SCOPE
    from pipelines.similarity.store import EmbeddingError
    from pipelines.similarity.text import embeddable_assets

    if not has_scope(REVIEW_SCOPE):
        return {"status": "unauthorized", "reason": f"The '{REVIEW_SCOPE}' token scope is required."}
    store = _embedding_store()
    if store is None:
        return _NO_DB
    try:
        email = delegated_actor_email()
        if email:
            who = _actor_with_role("kb:maintain")
            if isinstance(who, dict):
                return who
            created_by = who[1].handle
        else:
            created_by = "system"
        current = {a["ref"]: a for a in embeddable_assets(server_config.kb_dir)}
        res = store.put(body.get("items"), str(body.get("model") or ""), str(body.get("model_version") or ""),
                        created_by, current)
        return ok_response(res, count=res["stored"])
    except EmbeddingError as exc:
        return invalid_argument_response(exc.argument, exc.reason)
    except Exception as e:
        return handle_exception_response(e, context_action="put_embeddings")


def _lexical_factory():
    """``factory(query_text) -> lexical(ref)``: relevance of the doctrine engine (synonyms EN/FR), index loaded once."""
    from pipelines.doctrine.context import relevance
    from pipelines.doctrine.text import query_concepts

    index = _doctrine_index()
    entries = {e.id: e for e in index.entries}

    def factory(query_text: str):
        concepts = query_concepts(query_text, index.vocabulary)
        return lambda ref: relevance(entries[ref], concepts) if ref in entries else None

    return factory


def _server_side_query(query_text: str, model: str) -> dict[str, Any]:
    """Vector of ``query_text`` by the reference model, with the in-memory vectors of the base, or an error envelope
    (``409 model-mismatch`` for another model, ``503`` when the model is absent or off)."""
    from pipelines.similarity.encoder import reference_encoder
    from pipelines.similarity.semantic import MemoryVectors, calibrate, scorer_for

    encoder, status = reference_encoder()
    if model and model != status["model"]:
        return {**invalid_argument_response(
            "model", f"model-mismatch: the server encodes with its reference model '{status['model']}', not '{model}'. "
            f"Send a 'vector' computed with '{model}', or omit 'model'."),
            "conflict": True, "error": "model-mismatch", "reference_model": status["model"]}
    if encoder is None:
        return {"status": "unavailable", "reason": f"server-side encoding unavailable: the embedding model "
                f"'{status['model']}' is {status['status']} ({status.get('reason')}). Send a 'vector' instead."}
    scorer = scorer_for(encoder)
    spec = encoder.spec
    return {"model": spec.id, "vector": scorer.query(query_text), "store": MemoryVectors(scorer, server_config.kb_dir),
            "score": lambda cos: calibrate(round(cos, 4), spec)}


def similar_knowledge(body: dict[str, Any]) -> dict[str, Any]:
    """Validated knowledge close to a subject: ``{model?, vector?, query_text?, types?, domains?, top_k?}`` ('kb:review').

    Either the client computes ``vector`` with the same model as the stored vectors (as before), or it sends only
    ``query_text`` and the server encodes it with its local reference model (issue #94, lot E4): clients no longer need
    to embed an encoder. Naming another ``model`` than the reference one without a vector is a ``409 model-mismatch``
    (the server can only encode with its own model). The result is **never a decision**: every item has
    ``requires_confirmation: true`` and shows its provenance and its documented assumptions.
    """
    from mcp_server.core.auth import has_scope
    from pipelines.kb_candidates.service import REVIEW_SCOPE
    from pipelines.similarity.search import similar
    from pipelines.similarity.store import EmbeddingError

    if not has_scope(REVIEW_SCOPE):
        return {"status": "unauthorized", "reason": f"The '{REVIEW_SCOPE}' token scope is required."}
    query_text = body.get("query_text")
    has_text = isinstance(query_text, str) and bool(query_text.strip())
    server_side = body.get("vector") is None and has_text
    store: Any = _embedding_store()
    if store is None and not server_side:
        return _NO_DB
    try:
        types = _str_list(body.get("types"), "types")
        if isinstance(types, dict):
            return types
        domains = _str_list(body.get("domains"), "domains")
        if isinstance(domains, dict):
            return domains
        model, vector, vector_score = str(body.get("model") or ""), body.get("vector"), None
        if server_side:
            served = _server_side_query(str(query_text).strip(), model)
            if "status" in served:
                return served
            model, vector, store, vector_score = served["model"], served["vector"], served["store"], served["score"]
        lexical = None
        if has_text:
            lexical = _lexical_factory()(query_text)
        judgements = summary = None
        fingerprint = body.get("subject_fingerprint")
        if isinstance(fingerprint, str) and fingerprint and _embedding_store() is not None:
            from pipelines.kb_candidates.kb import load_assets
            from pipelines.similarity.reuse import ReuseStore

            reuse = ReuseStore()
            judgements = reuse.judgements(fingerprint, {a.id: a for a in load_assets(server_config.kb_dir)})
            summary = reuse.summary()
        res = similar(store, server_config.kb_dir, model, vector,
                      query_text if isinstance(query_text, str) else None, types or None, domains or None,
                      body.get("top_k") or 10, lexical, judgements, summary, vector_score)
        res["encoded_by"] = "server" if server_side else "client"
        return ok_response(res, count=len(res["results"]))
    except EmbeddingError as exc:
        return invalid_argument_response(exc.argument, exc.reason)
    except Exception as e:
        return handle_exception_response(e, context_action="similar_knowledge")


def confirm_reuse(body: dict[str, Any]) -> dict[str, Any]:
    """Record the judgement of a person on a reuse proposal (append-only; requires an acting person).

    Body: ``{subject_fingerprint, subject_label (anonymised), matched_ref, model?, scores?, outcome,
    assumptions: [{text, status: holds|does_not_hold|unknown, note?}], comment?}``. The server refuses
    (400/409) any confirmation that skips the hypotheses: ``reused`` needs every documented assumption judged
    and holding; an asset without documented assumptions cannot be reused; a superseded asset cannot be reused.
    """
    from mcp_server.core.auth import delegated_actor_email
    from pipelines.similarity.reuse import (
        ReuseConflictError,
        ReuseError,
        ReuseStore,
        find_asset,
        validate_confirmation,
    )

    store = _embedding_store()
    if store is None:
        return _NO_DB
    try:
        if not delegated_actor_email():
            return {"status": "unauthorized",
                    "reason": "No acting person: send X-Actor-Email with a token carrying the 'kb:delegate' scope."}
        record = validate_confirmation(body, find_asset(server_config.kb_dir, str(body.get("matched_ref") or "")),
                                       server_config.kb_dir)
        return ok_response(ReuseStore().add(_actor(), record), count=1)
    except ReuseConflictError as exc:
        return {**invalid_argument_response(exc.argument, exc.reason), "conflict": True}
    except ReuseError as exc:
        return invalid_argument_response(exc.argument, exc.reason)
    except Exception as e:
        return handle_exception_response(e, context_action="confirm_reuse")


def list_reuse_confirmations(matched_ref: str | None = None, outcome: str | None = None,
                             subject_fingerprint: str | None = None) -> dict[str, Any]:
    """History of reuse judgements (requires 'kb:review'): calibration base and audit trail."""
    from mcp_server.core.auth import has_scope
    from pipelines.kb_candidates.service import REVIEW_SCOPE
    from pipelines.similarity.reuse import OUTCOMES, ReuseStore

    if not has_scope(REVIEW_SCOPE):
        return {"status": "unauthorized", "reason": f"The '{REVIEW_SCOPE}' token scope is required."}
    if _embedding_store() is None:
        return _NO_DB
    if outcome and outcome not in OUTCOMES:
        return invalid_argument_response("outcome", f"'outcome' must be one of {list(OUTCOMES)}.")
    try:
        items = ReuseStore().history(matched_ref or None, outcome or None, subject_fingerprint or None)
        return ok_response(items, count=len(items))
    except Exception as e:
        return handle_exception_response(e, context_action="list_reuse_confirmations")


def get_similarity_eval(dataset: str) -> dict[str, Any]:
    """Cases of a similarity dataset: text to encode, language, family, expected relations, annotation status ('kb:review')."""
    from mcp_server.core.auth import has_scope
    from pipelines.kb_candidates.service import REVIEW_SCOPE

    if not has_scope(REVIEW_SCOPE):
        return {"status": "unauthorized", "reason": f"The '{REVIEW_SCOPE}' token scope is required."}
    store = _eval_store()
    if store is None:
        return _NO_DB
    try:
        cases = store.cases(dataset)
        return ok_response({"dataset": dataset, "cases": cases,
                            "validated": sum(1 for c in cases if c["annotation_status"] == "validated"),
                            "runs": store.runs(dataset)[:10]}, count=len(cases))
    except Exception as e:
        return _eval_error(e) or handle_exception_response(e, context_action="get_similarity_eval")


def annotate_similarity_case(dataset: str, case_id: str, body: dict[str, Any]) -> dict[str, Any]:
    """Annotate a case: ``{expected: [{ref, relation}], annotation_status}`` (acting expert with 'kb:evaluate')."""
    from pipelines.similarity.evals import annotate

    who = _evaluator()
    if isinstance(who, dict):
        return who
    store = _eval_store()
    if store is None:
        return _NO_DB
    if body.get("expected") is None and body.get("annotation_status") is None:
        return invalid_argument_response("body", "send 'expected' and/or 'annotation_status'.")
    try:
        return ok_response(annotate(store, dataset, case_id, who[1].handle, server_config.kb_dir,
                                    body.get("expected"), body.get("annotation_status")), count=1)
    except Exception as e:
        return _eval_error(e) or handle_exception_response(e, context_action="annotate_similarity_case")


def run_similarity_eval(dataset: str, body: dict[str, Any]) -> dict[str, Any]:
    """Run the similarity search on a dataset with vectors supplied by the client ('kb:evaluate').

    Body: ``{model, vectors: {case_id: vector}, validated_only?}``. Reports recall@3, **wrong strong proposals**,
    per family and language, and a threshold sweep with the lowest threshold that avoids every wrong strong proposal.
    """
    from pipelines.governance.log import get_log
    from pipelines.similarity.evals import check_vectors, evaluate
    from pipelines.similarity.store import EmbeddingStore

    who = _evaluator()
    if isinstance(who, dict):
        return who
    store = _eval_store()
    if store is None:
        return _NO_DB
    try:
        model = str(body.get("model") or "")
        embeddings = EmbeddingStore()
        space = embeddings.model_space(model)
        if space is None:
            return invalid_argument_response("model", f"no vector stored for model '{model}' (known: "
                                             f"{[m['model_id'] for m in embeddings.models()]}).")
        cases = store.cases(dataset)
        if body.get("validated_only"):
            cases = [c for c in cases if c["annotation_status"] == "validated"]
        if not cases:
            return invalid_argument_response("dataset", "no case to evaluate (none validated yet?).")
        vectors = check_vectors(cases, body.get("vectors"), space[0])
        metrics = evaluate(cases, vectors, embeddings, server_config.kb_dir, model, _lexical_factory())
        metrics["validated_only"] = bool(body.get("validated_only"))
        metrics["validated_cases"] = sum(1 for c in cases if c["annotation_status"] == "validated")
        run = store.save_run(dataset, who[1].handle, metrics)
        log = get_log()
        if log is not None:
            log.emit("eval.updated", None, who[1].handle, [], dataset=dataset, run_id=run["id"],
                     false_strong=metrics["false_strong"])
        return ok_response(run, count=1)
    except Exception as e:
        return _eval_error(e) or handle_exception_response(e, context_action="run_similarity_eval")


def get_similarity_eval_run(dataset: str, run_id: int) -> dict[str, Any]:
    """A stored similarity run with its per-case detail ('kb:review')."""
    return get_eval_run(dataset, run_id)


# ---------------------------------------------------------------------------
# Regulatory coverage (contract 1.3).
# ---------------------------------------------------------------------------

def get_framework_coverage(frameworks: list[str]) -> dict[str, Any]:
    """Coverage of regulatory frameworks by the knowledge base.

    For each framework: status ('covered' | 'partial' | 'missing'), version, number of
    expected requirements (from the framework manifest, null when unknown), present and
    validated requirements, missing requirement ids, and who declared the coverage.
    'covered' requires every expected requirement present, active and validated, and an
    expert declaration.

    Args:
        frameworks: Framework codes (e.g. ['NIS2', 'ISO27001']).
    """
    fws = _str_list(frameworks, "frameworks")
    if isinstance(fws, dict):
        return fws
    if not fws:
        return invalid_argument_response("frameworks", "At least one framework is required.")
    try:
        from pipelines.compliance_mapper import compute_framework_coverage

        coverage = compute_framework_coverage(fws, server_config.kb_dir)
        return ok_response(coverage, count=len(coverage))
    except Exception as e:
        return handle_exception_response(e, context_action="get_framework_coverage")


# --- K22: trigger rules and facts vocabulary, for the review in the administration application -------------------------


def _live_vocabulary() -> dict[str, Any]:
    from pipelines.engagement import facts as fact_module

    return fact_module.load(server_config.kb_dir / "vocabulary" / "facts.yaml")


def list_trigger_rules() -> dict[str, Any]:
    """The reference rules by carrying element, the facts vocabulary, and the rule and key candidates in flight (contract 1.25)."""
    from mcp_server.core.auth import has_scope
    from pipelines import triggers
    from pipelines.engagement import facts as fact_module
    from pipelines.kb_candidates.kb import load_assets
    from pipelines.kb_candidates.rules import TRIGGER_TYPES
    from pipelines.kb_candidates.service import REVIEW_SCOPE

    try:
        vocabulary = _live_vocabulary()
        rules = triggers.load_all(server_config.kb_dir, vocabulary)
    except (OSError, fact_module.VocabularyError) as e:
        return handle_exception_response(e, context_action="list_trigger_rules")
    except triggers.TriggerError as e:
        return {"status": "error", "error": "invalid_rules", "reason": str(e), "problems": e.problems}
    titles = {a.id: a.title for a in load_assets(server_config.kb_dir)}
    by_asset: dict[str, list[dict[str, Any]]] = {}
    for r in rules:
        by_asset.setdefault(r["asset"], []).append({k: v for k, v in r.items() if k != "content_sha256"})
    data: dict[str, Any] = {
        "vocabulary": {"version": vocabulary["version"], "keys": fact_module.public_keys(vocabulary)},
        "assets": [{"id": aid, "title": titles.get(aid, aid), "rules": by_asset[aid]} for aid in sorted(by_asset)],
        "candidates": [],
    }
    if has_scope(REVIEW_SCOPE):  # the queue is for reviewers, like the candidates themselves
        data["candidates"] = [
            {"id": c["id"], "asset_type": c["asset_type"], "status": c["status"], "title": c["title"], "kind": c["kind"],
             "target_asset_id": c.get("target_asset_id"), "assigned_owner": c.get("assigned_owner"),
             "production_mode": (c.get("source") or {}).get("production_mode"),
             "checks": [x for x in c.get("checks") or [] if x["name"] == "schema"]}
            for c in _candidate_service().find()
            if c.get("asset_type") in TRIGGER_TYPES and c["status"] not in ("published", "rejected")]
    return ok_response(data, count=len(rules))


def validate_trigger_rule(body: dict[str, Any]) -> dict[str, Any]:
    """Live validation of a rule or a vocabulary key against the facts vocabulary (nothing is stored).

    Body: ``{content: <YAML>, asset_type?: 'trigger'|'fact_key', target_asset_id?}``. Answers ``{valid, problems: [{path, code,
    reason}]}``: the same validator as the ``schema`` check of the candidate cycle and the publication.
    """
    from pipelines.kb_candidates.rules import problems_of

    content = body.get("content")
    if not isinstance(content, str) or not content.strip():
        return invalid_argument_response("content", "'content' is the YAML of the rule or of the key.")
    asset_type = body.get("asset_type", "trigger")
    if asset_type not in ("trigger", "fact_key"):
        return invalid_argument_response("asset_type", "'asset_type' must be 'trigger' or 'fact_key'.")
    target = body.get("target_asset_id")
    problems, _ = problems_of({"asset_type": asset_type, "proposed_content": content, "kind": "amendment" if target else "new_asset",
                               "target_asset_id": target}, server_config.kb_dir)
    return ok_response({"valid": not problems, "problems": problems}, count=len(problems))


def preview_triggers(body: dict[str, Any]) -> dict[str, Any]:
    """"With these facts, these are the questions that would open": the evaluation of the cascade engine (K20), without an engagement.

    Body: ``{facts: {key: value}, rules?: [<rule YAML or mapping>]}``. The reference rules of the knowledge base are evaluated;
    ``rules`` adds drafts (a candidate under review). The facts are checked against the vocabulary (a key or a type it does not
    know is refused with its path). The evaluator is ``pipelines.triggers.evaluate``, the one the engine uses.
    """
    import yaml

    from pipelines import triggers
    from pipelines.engagement import facts as fact_module

    facts = body.get("facts")
    if not isinstance(facts, dict):
        return invalid_argument_response("facts", "'facts' is an object {key: value}.")
    try:
        vocabulary = _live_vocabulary()
        reference = triggers.load_all(server_config.kb_dir, vocabulary)
    except triggers.TriggerError as e:
        return {"status": "error", "error": "invalid_rules", "reason": str(e), "problems": e.problems}
    try:
        fact_module.validate([{"key": k, "value": v, "source_excerpt": "preview"} for k, v in sorted(facts.items())], vocabulary)
    except fact_module.FactError as err:
        return {"status": "invalid_argument", "argument": "facts", "code": err.code, "reason": err.reason, "path": err.path}
    drafts, invalid = [], []
    carrier_index = triggers.carriers(server_config.kb_dir)
    for i, raw in enumerate(body.get("rules") or []):
        doc = yaml.safe_load(raw) if isinstance(raw, str) else raw
        name = str((doc or {}).get("trigger_id")) if isinstance(doc, dict) else f"rules[{i}]"
        problems = triggers.validate_rule(doc, name, vocabulary, carrier_index, local=name.startswith("TRG-local-"))
        if problems:
            invalid.append({"trigger_id": name, "problems": problems})
        else:
            drafts.append({**doc, "scope": "draft"})
    drafted = {d["trigger_id"] for d in drafts}
    rules = [{**r, "scope": "reference"} for r in reference if r["trigger_id"] not in drafted] + drafts
    opened, closed = triggers.evaluate(rules, facts)
    shown = ("trigger_id", "version", "question", "rationale", "initial_level", "suggested_role", "mandatory", "asset", "scope")
    return ok_response({"opens": [{k: r.get(k) for k in shown} for r in opened], "closed": closed, "invalid_drafts": invalid},
                       count=len(opened))


def merge_fact_key_candidate(candidate_id: str, into: str, reviewer: str, reason: str | None = None) -> dict[str, Any]:
    """Merge a proposed vocabulary key into an existing one (requires the 'kb:review' scope).

    Rejects the key candidate (the reason records the merge) and answers the rule candidates that cite the merged key, each with
    the content rewritten on the existing key: the reviewer then amends them (a rule is never changed or accepted as a side
    effect).
    """
    from pipelines.kb_candidates import rules as rule_candidates

    service = _candidate_service()
    try:
        candidate = service.get(candidate_id)
    except Exception:
        return not_found_response(candidate_id)
    if candidate.get("asset_type") != "fact_key":
        return invalid_argument_response("candidate_id", "only a fact_key candidate can be merged.")
    vocabulary = _live_vocabulary()
    if into not in vocabulary["keys"]:
        return invalid_argument_response("into", f"'{into}' is not a key of the facts vocabulary.")
    key = (rule_candidates.parse_content(candidate["proposed_content"]) or {}).get("key")
    if into == key:
        return invalid_argument_response("into", "a key cannot be merged into itself.")
    res = review_kb_candidate(candidate_id, "reject", reviewer, reason=f"merged into {into}" + (f": {reason}" if reason else ""))
    if res.get("status") != "ok":
        return res
    affected = [{"id": c["id"], "status": c["status"], "title": c["title"],
                 "suggested_content": rule_candidates.rewrite_key(c["proposed_content"], key, into)}
                for c in service.find() if c.get("asset_type") == "trigger" and c["status"] in ("checks_failed", "in_review")
                and key in rule_candidates.keys_of(c["proposed_content"])]
    return ok_response({"candidate": res["data"], "merged_into": into, "affected_rules": affected}, count=len(affected))


# ---------------------------------------------------------------------------
# Fine-grained RBAC, delegation, and access audit (issue #7, contract 1.37)
# ---------------------------------------------------------------------------

def list_kb_delegations(
    delegate: str | None = None,
    delegator: str | None = None,
    active_only: bool = True,
) -> dict[str, Any]:
    """List domain ownership and review delegations (requires 'kb:review')."""
    from mcp_server.core.auth import has_scope, resolve_actor
    from pipelines.governance.rbac import get_delegation_store
    from pipelines.kb_candidates.service import REVIEW_SCOPE

    if not has_scope(REVIEW_SCOPE):
        return {"status": "unauthorized", "reason": f"The '{REVIEW_SCOPE}' token scope is required."}

    actor = resolve_actor()
    target_delegate = delegate or (actor.handle if actor and not delegator else None)
    store = get_delegation_store()
    items = store.list_delegations(delegate=target_delegate, delegator=delegator, active_only=active_only)
    return ok_response({"delegations": items}, count=len(items))


def create_kb_delegation(
    delegate: str,
    domains: list[str],
    roles: list[str],
    expires_at: str,
    starts_at: str | None = None,
) -> dict[str, Any]:
    """Delegate review rights and domain ownership temporarily to another expert.

    The delegator is the acting expert (contract 1.37).
    """
    from mcp_server.core.auth import resolve_actor
    from pipelines.governance.rbac import get_delegation_store

    actor = resolve_actor()
    if not actor:
        return {
            "status": "unauthorized",
            "reason": "An acting expert is required: provide X-Actor-Token or X-Actor-Email.",
        }

    if not isinstance(delegate, str) or not delegate.strip().startswith("@"):
        return invalid_argument_response("delegate", "'delegate' must be an owner handle starting with '@'.")
    if not isinstance(domains, list) or not domains:
        return invalid_argument_response("domains", "'domains' must be a non-empty list of domain patterns.")
    if not isinstance(roles, list) or not roles:
        return invalid_argument_response("roles", "'roles' must be a non-empty list of KB roles.")
    if not isinstance(expires_at, str) or not expires_at.strip():
        return invalid_argument_response("expires_at", "'expires_at' ISO timestamp is required.")

    service = _candidate_service()
    registry = service.owners()
    if delegate.strip() not in registry.owners:
        return invalid_argument_response("delegate", f"'{delegate}' is not a registered expert.")

    # Expert can only delegate domains they own or if they have kb:maintain
    if "kb:maintain" not in actor.roles:
        unowned = [d for d in domains if not registry.can_review(actor.handle, [d])]
        if unowned:
            return {"status": "unauthorized", "reason": f"You do not own domain(s): {unowned}"}

    store = get_delegation_store()
    rec = store.create_delegation(
        delegator=actor.handle,
        delegate=delegate,
        domains=domains,
        roles=roles,
        expires_at=expires_at,
        starts_at=starts_at,
        created_by=actor.handle,
    )
    return ok_response(rec, count=1)


def revoke_kb_delegation(delegation_id: str) -> dict[str, Any]:
    """Revoke an active delegation immediately (delegator or kb:maintain)."""
    from mcp_server.core.auth import resolve_actor
    from pipelines.governance.rbac import get_delegation_store

    actor = resolve_actor()
    if not actor:
        return {
            "status": "unauthorized",
            "reason": "An acting expert is required: provide X-Actor-Token or X-Actor-Email.",
        }

    store = get_delegation_store()
    delegations = store.list_delegations(active_only=False)
    target = next((d for d in delegations if d["id"] == delegation_id), None)
    if not target:
        return not_found_response(delegation_id)

    if "kb:maintain" not in actor.roles and target["delegator"] != actor.handle:
        return {"status": "unauthorized", "reason": "Only the delegator or a maintainer can revoke this delegation."}

    success = store.revoke_delegation(delegation_id, revoked_by=actor.handle)
    return ok_response({"revoked": success, "id": delegation_id}, count=1 if success else 0)


def revoke_kb_auth(identifier: str, reason: str = "revoked by admin", is_jti: bool = False) -> dict[str, Any]:
    """Immediately revoke a token JTI or an expert handle/email (requires 'kb:admin' or 'kb:maintain')."""
    from mcp_server.core.assertion import get_revocation_store
    from mcp_server.core.auth import resolve_actor

    actor = resolve_actor()
    if not actor or not ({"kb:admin", "kb:maintain"} & set(actor.roles)):
        return {"status": "unauthorized", "reason": "Requires 'kb:admin' or 'kb:maintain' role."}

    store = get_revocation_store()
    if is_jti:
        store.revoke_jti(identifier.strip(), reason=reason)
    else:
        store.revoke_actor(identifier.strip(), reason=reason)

    return ok_response({"revoked": True, "identifier": identifier, "reason": reason}, count=1)


def get_kb_audit(
    actor: str | None = None,
    action: str | None = None,
    outcome: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Query the governance access audit log (requires 'kb:review')."""
    from mcp_server.core.auth import has_scope
    from pipelines.governance.audit import get_governance_audit
    from pipelines.kb_candidates.service import REVIEW_SCOPE

    if not has_scope(REVIEW_SCOPE):
        return {"status": "unauthorized", "reason": f"The '{REVIEW_SCOPE}' token scope is required."}

    audit = get_governance_audit()
    records = audit.query(actor=actor, action=action, outcome=outcome, limit=limit)
    return ok_response({"events": records}, count=len(records))


def get_jwks() -> dict[str, Any]:
    """Return published JWKS public keys for verifying EdDSA actor assertions."""
    from mcp_server.core.assertion import get_jwks_registry

    jwks = get_jwks_registry().to_jwks()
    return ok_response(jwks, count=len(jwks.get("keys", [])))

def list_ontology_terms(
    concept_class: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """List federated ontology terms and projections (experimental EDP feature, Issue #175).

    Args:
        concept_class: Optional filter by concept class (e.g. 'SecurityZone', 'ComputeSubstrate').
        status: Optional status filter ('draft', 'validated', 'rejected').
    """
    from pipelines.ontology.gateway import is_ontology_experimental_enabled
    from pipelines.ontology.loader import load_ontology_entries

    if not is_ontology_experimental_enabled():
        return not_found_response("experimental_ontology_disabled")

    try:
        ont_dir = Path(server_config.kb_dir) / "ontology"
        entries = load_ontology_entries(ont_dir)
        if concept_class:
            entries = [e for e in entries if e.concept_class == concept_class]
        if status:
            entries = [e for e in entries if e.status == status]
        items = [e.to_dict() for e in entries]
        return ok_response(items, count=len(items), experimental=True)
    except Exception as e:
        return handle_exception_response(e, context_action="list_ontology_terms")


def get_ontology_term(
    urn: str,
    revision: int | None = None,
) -> dict[str, Any]:
    """Retrieve a specific ontology term by its citable URN and optional revision (Issue #175).

    Args:
        urn: Citable ontology URN (e.g. 'urn:llmops:ontology:ComputeSubstrate:bare_metal_k8s').
        revision: Optional revision integer. If specified and not held, raises error without fallback.
    """
    from pipelines.ontology.gateway import is_ontology_experimental_enabled
    from pipelines.ontology.ledger import OntologyResolutionError, resolve_ontology_entry
    from pipelines.ontology.loader import load_ontology_entries

    if not is_ontology_experimental_enabled():
        return not_found_response("experimental_ontology_disabled")

    try:
        ont_dir = Path(server_config.kb_dir) / "ontology"
        entries = load_ontology_entries(ont_dir)
        entry = resolve_ontology_entry(entries, urn, revision=revision)
        return ok_response(entry.to_dict(), count=1, experimental=True)
    except OntologyResolutionError as exc:
        return {
            "status": "not_found",
            "reason": exc.reason,
            "message": str(exc),
            "id": urn,
            "requested_revision": exc.detail.get("requested_revision"),
            "experimental": True,
        }
    except Exception as e:
        return handle_exception_response(e, context_action="get_ontology_term")

