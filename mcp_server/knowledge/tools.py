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
        err_str = str(e)
        if "Binder exception" in err_str or "does not exist" in err_str or "Table" in err_str:
            return ok_response([])
        return error_response(err_str)


def get_asset(id: str) -> dict[str, Any]:
    """Retrieve full content and frontmatter metadata for an architecture asset.

    Args:
        id: Unique asset identifier (e.g. 'ADR-0014', 'P-002').
    """
    if not id:
        return not_found_response(id)

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


def list_frameworks() -> dict[str, Any]:
    """List regulatory and security frameworks embedded in the knowledge base along with their versions and control counts."""
    kb_client = _get_db()
    try:
        query = """
        MATCH (c:Control)
        RETURN c.framework as framework, c.version as version, count(c) as control_count;
        """
        rows = kb_client.execute_cypher(query)
        meta = {
            "NIS2": {
                "title": "Directive (UE) 2022/2555 (NIS 2)",
                "jurisdiction": "EU",
                "description": "Mesures de gestion des risques de cybersécurité pour les entités essentielles et importantes.",
            },
            "3GPP": {
                "title": "3GPP Security Specifications (TS 33.179 / TS 33.501)",
                "jurisdiction": "International",
                "description": "Sécurité des services de communication critique (MCX) et de l'architecture SBA 5G.",
            },
        }
        res = []
        for r in rows:
            fw = r.get("framework", "")
            info = meta.get(fw, {"title": fw, "jurisdiction": "Unknown", "description": ""})
            res.append({
                "framework": fw,
                "version": r.get("version", "1.0.0"),
                "title": info["title"],
                "jurisdiction": info["jurisdiction"],
                "description": info["description"],
                "control_count": r.get("control_count", 0),
            })
        return ok_response(res, count=len(res))
    except Exception as e:
        return error_response(str(e))


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
        return error_response(str(e))


def get_compliance_trail(control_id: str) -> dict[str, Any]:
    """Retrieve full compliance traceability for a specific control: regulatory text, criteria, and implementing patterns/principles/ADRs.

    Args:
        control_id: The control identifier (e.g. 'NIS2-ART21-2C', '3GPP-TS33179-KMS').
    """
    if not control_id or not isinstance(control_id, str):
        return invalid_argument_response("control_id must be a non-empty string.")

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
        return error_response(str(e))


def get_compliance_matrix(engagement: str, framework: str) -> dict[str, Any]:
    """Evaluate compliance coverage of an engagement project against a regulatory framework.

    Args:
        engagement: Engagement identifier (e.g. 'nordwave-mcx-2027').
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
        return error_response(str(e))


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

    Args:
        title: Short descriptive title of the suggested knowledge improvement.
        rationale: Why this change or pattern is needed and the architectural value it provides.
        suggested_change: Markdown description of the proposed asset, ADR amendment, or pattern.
        author: Name or identifier of the contributor.
        contact_email: Optional email address to receive feedback on the review.
        source_engagement: Optional engagement or project where this pattern was proven.
    """
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
    engagement: str = "nordwave-mcx-2027",
    blueprint_path: str = "data/kb/blueprints/BLU-hla-mcx.yaml",
) -> dict[str, Any]:
    """Calculate the staffing skill coverage matrix and risk index for an engagement.

    Args:
        engagement: Target engagement identifier.
        blueprint_path: Optional path to the architecture blueprint.
    """
    from tools.elicitation.mailbox.roster import RosterManager
    from tools.elicitation.models.blueprint_schema import load_blueprint

    bp = load_blueprint(blueprint_path)
    mgr = RosterManager(engagement=engagement)
    covered = mgr.get_all_covered_skills()

    required_skills_map = {}
    all_required = set()
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




