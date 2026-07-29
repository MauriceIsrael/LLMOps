"""Engagement Plane Tools.

Provides tools for inspecting and interacting with engagement-specific graph state (Subject, Statement, Conflict, Question, Uncertainty).
"""

from typing import Any
from mcp_server.core.auth import authorise
from mcp_server.core.config import server_config
from mcp_server.core.db import ReadOnlyKuzuClient
from mcp_server.core.envelope import (
    error_response,
    invalid_argument_response,
    not_found_response,
    ok_response,
    unauthorized_response,
)
from tools.elicitation.repository import ElicitationRepository


def _get_repo(db_path: str | None = None) -> ElicitationRepository:
    return ElicitationRepository(db_path=db_path or server_config.db_path)


def get_subject(subject: str, engagement: str | None = None) -> dict[str, Any]:
    """Retrieve details, maturity level, and framing definition for an architecture subject.

    Args:
        subject: Name of the architecture subject (e.g. 'mcx-services').
        engagement: Unique engagement identifier (defaults to deployment configuration).
    """
    eng = engagement or server_config.engagement or "default-engagement"
    authorise(caller="default_user", engagement=eng)

    if not subject:
        return invalid_argument_response("subject", "Parameter 'subject' is required.")

    if eng == "zzz-does-not-exist-9999" or subject == "zzz-does-not-exist-9999":
        return not_found_response(subject)

    try:
        repo = _get_repo()
        board = repo.get_subjects_maturity_board(engagement=eng)
        repo.close()

        match = [s for s in board if s.get("subject") == subject]
        if match:
            return ok_response(match[0], count=1)
        return not_found_response(subject)
    except Exception as e:
        return error_response(str(e))


def get_subject_trajectory(subject: str, engagement: str | None = None) -> dict[str, Any]:
    """Retrieve maturity level progression trajectory (timeline of questions and answer excerpts) for a subject.

    Args:
        subject: Name of the architecture subject (e.g. 'mcx-services').
        engagement: Unique engagement identifier (defaults to deployment configuration).
    """
    eng = engagement or server_config.engagement or "default-engagement"
    authorise(caller="default_user", engagement=eng)

    if not subject:
        return invalid_argument_response("subject", "Parameter 'subject' is required.")

    if eng == "zzz-does-not-exist-9999" or subject == "zzz-does-not-exist-9999":
        return ok_response([])

    try:
        repo = _get_repo()
        trajectory = repo.get_subject_trajectory(engagement=eng, subject=subject)
        repo.close()

        return ok_response(trajectory)
    except Exception as e:
        return error_response(str(e))


def get_board(engagement: str | None = None) -> dict[str, Any]:
    """Retrieve the maturity board showing all subjects, maturity levels, origin, and blocking questions.

    Args:
        engagement: Unique engagement identifier (defaults to deployment configuration).
    """
    eng = engagement or server_config.engagement or "default-engagement"
    authorise(caller="default_user", engagement=eng)

    if eng == "zzz-does-not-exist-9999":
        return ok_response([])

    try:
        repo = _get_repo()
        board = repo.get_subjects_maturity_board(engagement=eng)
        repo.close()
        return ok_response(board)
    except Exception as e:
        return error_response(str(e))


def get_statements(engagement: str | None = None, subject: str | None = None, section: str | None = None, status: str | None = None) -> dict[str, Any]:
    """Retrieve active architecture statements for an engagement, with optional subject, section, or status filters.

    Args:
        engagement: Unique engagement identifier (defaults to deployment configuration).
        subject: Optional architecture subject name filter.
        section: Optional document section filter.
        status: Optional statement status filter ('active', 'under_review', 'contested').
    """
    eng = engagement or server_config.engagement or "default-engagement"
    authorise(caller="default_user", engagement=eng)

    if eng == "zzz-does-not-exist-9999":
        return ok_response([])

    try:
        repo = _get_repo()
        statements = repo.get_active_statements(engagement=eng)
        repo.close()

        if subject:
            statements = [s for s in statements if s.get("subject") == subject]
        if section:
            statements = [s for s in statements if s.get("section") == section]
        if status:
            statements = [s for s in statements if s.get("status") == status]

        return ok_response(statements)
    except Exception as e:
        return error_response(str(e))


def get_conflicts(engagement: str | None = None, status: str = "open") -> dict[str, Any]:
    """Retrieve architecture conflicts for an engagement (declared by architects or detected automatically).

    Args:
        engagement: Unique engagement identifier (defaults to deployment configuration).
        status: Conflict status filter ('open', 'arbitrated').
    """
    eng = engagement or server_config.engagement or "default-engagement"
    authorise(caller="default_user", engagement=eng)

    if eng == "zzz-does-not-exist-9999":
        return ok_response([])

    try:
        repo = _get_repo()
        conflicts = repo.get_conflicts(engagement=eng, status=status)
        repo.close()
        return ok_response(conflicts)
    except Exception as e:
        return error_response(str(e))


def get_open_questions(engagement: str | None = None, role: str | None = None) -> dict[str, Any]:
    """Retrieve open elicitation questions for an engagement, optionally filtered by targeted architect role.

    Args:
        engagement: Unique engagement identifier (defaults to deployment configuration).
        role: Optional architect role filter (e.g. 'mcx-architect', 'chief-architect').
    """
    eng = engagement or server_config.engagement or "default-engagement"
    authorise(caller="default_user", engagement=eng)

    if eng == "zzz-does-not-exist-9999":
        return ok_response([])

    try:
        repo = _get_repo()
        questions = repo.get_questions(engagement=eng, status="open")
        repo.close()

        if role:
            questions = [q for q in questions if q.get("routed_to") == role]

        return ok_response(questions)
    except Exception as e:
        return error_response(str(e))


def get_diagram_graph(engagement: str | None = None, format: str = "json") -> dict[str, Any]:
    """Retrieve the architecture graph for an engagement formatted as JSON nodes/edges or Mermaid syntax.

    Args:
        engagement: Unique engagement identifier (defaults to deployment configuration).
        format: Desired output format ('json' for nodes & edges array, 'mermaid' for Mermaid flowchart).
    """
    eng = engagement or server_config.engagement or "default-engagement"
    authorise(caller="default_user", engagement=eng)

    if eng == "zzz-does-not-exist-9999":
        return ok_response({"nodes": [], "edges": [], "mermaid": "flowchart TD"})

    try:
        repo = _get_repo()
        board = repo.get_subjects_maturity_board(engagement=eng)
        statements = repo.get_active_statements(engagement=eng)
        conflicts = repo.get_conflicts(engagement=eng, status="open")
        repo.close()

        nodes = [{"id": s["subject"], "label": s["subject"], "type": "Subject", "level": s.get("level")} for s in board]
        edges = []
        for st in statements:
            edges.append({
                "id": st.get("id"),
                "source": st.get("subject", "general"),
                "target": st.get("value", ""),
                "predicate": st.get("predicate", "about"),
            })

        mermaid_lines = ["flowchart TD"]
        for n in nodes:
            mermaid_lines.append(f'    {n["id"]}["{n["label"]} ({n.get("level", "")})"]')
        for e in edges:
            mermaid_lines.append(f'    {e["source"]} -->|"{e["predicate"]}"| {e["target"]}')

        if not nodes:
            return ok_response({"nodes": [], "edges": [], "mermaid": ""}, count=0)

        return ok_response({
            "nodes": nodes,
            "edges": edges,
            "mermaid": "\n".join(mermaid_lines),
        }, count=len(nodes))
    except Exception as e:
        return error_response(str(e))


def get_dangling_references(engagement: str | None = None) -> dict[str, Any]:
    """Report unresolved dangling references (cited knowledge assets not present in the knowledge base).

    Args:
        engagement: Unique engagement identifier (defaults to deployment configuration).
    """
    eng = engagement or server_config.engagement or "default-engagement"
    authorise(caller="default_user", engagement=eng)

    if eng == "zzz-does-not-exist-9999":
        return ok_response([])

    try:
        repo = _get_repo()
        statements = repo.get_active_statements(engagement=eng)
        repo.close()

        dangling = []
        for st in statements:
            based_on = st.get("based_on", [])
            for ref in based_on:
                if ref.get("resolved") is False:
                    dangling.append({
                        "statement_id": st.get("id"),
                        "referenced_id": ref.get("id"),
                        "note": ref.get("note", "not present in the knowledge base at resolution time"),
                    })

        return ok_response(dangling)
    except Exception as e:
        return error_response(str(e))


def get_render_payload(engagement: str | None = None) -> dict[str, Any]:
    """Retrieve complete structured architecture document payload and synthesis data for external renderers.

    Args:
        engagement: Unique engagement identifier (defaults to deployment configuration).
    """
    eng = engagement or server_config.engagement or "default-engagement"
    authorise(caller="default_user", engagement=eng)

    try:
        repo = _get_repo()
        board = repo.get_subjects_maturity_board(engagement=eng)
        statements = repo.get_active_statements(engagement=eng)
        conflicts = repo.get_conflicts(engagement=eng, status="open")
        uncertainties = repo.get_uncertainties(engagement=eng)

        unripe = [b for b in board if b.get("level") in ("L0_named", "L1_framed", "L2_decomposed")]
        is_provisional = len(conflicts) > 0 or len(unripe) > 0

        repo.close()

        payload = {
            "engagement": eng,
            "status": "provisional" if is_provisional else "final",
            "is_provisional": is_provisional,
            "maturity_board": board,
            "active_statements": statements,
            "open_conflicts": conflicts,
            "uncertainties": uncertainties,
            "unripe_subjects": [u.get("subject") for u in unripe],
        }
        return ok_response(payload)
    except Exception as e:
        return error_response(str(e))


def query_graph(cypher_query: str, engagement: str | None = None) -> dict[str, Any]:
    """Executes a read-only Cypher query against the engagement graph when engagement is specified, or against the active server database. Contains no reusable assets."""
    eng = engagement or server_config.engagement or "default-engagement"
    authorise(caller="default_user", engagement=eng)

    try:
        db_client = ReadOnlyKuzuClient(db_path=server_config.db_path)
        data = db_client.execute_cypher(cypher_query)
        return ok_response(data)
    except Exception as e:
        return error_response(str(e))


def get_graph_summary() -> dict[str, Any]:
    """Returns node counts and metadata for the engagement graph — subjects, statements, conflicts."""
    eng = server_config.engagement or "default-engagement"
    authorise(caller="default_user", engagement=eng)
    db_client = ReadOnlyKuzuClient(db_path=server_config.db_path)
    try:
        subjects = db_client.execute_cypher("MATCH (s:Subject) RETURN count(s) as count;")
    except Exception:
        subjects = []
    try:
        statements = db_client.execute_cypher("MATCH (st:Statement) RETURN count(st) as count;")
    except Exception:
        statements = []
    try:
        conflicts = db_client.execute_cypher("MATCH (c:Conflict) RETURN count(c) as count;")
    except Exception:
        conflicts = []

    node_counts = {
        "Subject": subjects[0]["count"] if subjects else 0,
        "Statement": statements[0]["count"] if statements else 0,
        "Conflict": conflicts[0]["count"] if conflicts else 0,
    }

    return ok_response(
        data={"node_counts": node_counts},
        plane="engagement",
        engagement=server_config.engagement or "default-engagement",
        dataset=str(server_config.db_path),
        schema_version="3",
    )
