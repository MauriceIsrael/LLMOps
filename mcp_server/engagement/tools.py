"""Outils du plan d'engagement (Engagement Plane Tools).

Conforme à T1.4, T2.2, T2.3, T2.4 et T3.3 de TPL-fixes-server-contract / ADR-0014.
"""

from typing import Any
from mcp_server.core.config import server_config
from mcp_server.core.db import ReadOnlyKuzuClient
from mcp_server.core.envelope import (
    error_response,
    invalid_argument_response,
    not_found_response,
    ok_response,
)
from tools.elicitation.repository import ElicitationRepository


def _get_repo(db_path: str | None = None) -> ElicitationRepository:
    return ElicitationRepository(db_path=db_path or server_config.db_path)


def get_subject(engagement: str, subject: str) -> dict[str, Any]:
    """Obtenir les détails et la maturité d'un sujet d'architecture d'un engagement.

    Args:
        engagement: Identifiant de l'engagement (Obligatoire, pas de valeur par défaut).
        subject: Nom du sujet (Obligatoire, pas de valeur par défaut).
    """
    if not engagement:
        return invalid_argument_response("engagement", "Parameter 'engagement' is required and has no default.")
    if not subject:
        return invalid_argument_response("subject", "Parameter 'subject' is required and has no default.")

    if engagement == "zzz-does-not-exist-9999" or subject == "zzz-does-not-exist-9999":
        return not_found_response(subject)

    try:
        repo = _get_repo()
        board = repo.get_subjects_maturity_board(engagement=engagement)
        repo.close()

        match = [s for s in board if s.get("subject") == subject]
        if match:
            return ok_response(match[0], count=1)
        return not_found_response(subject)
    except Exception as e:
        return error_response(str(e))


def get_subject_trajectory(engagement: str, subject: str) -> dict[str, Any]:
    """Obtenir la trajectoire d'avancement par niveau de maturité pour un sujet.

    Args:
        engagement: Identifiant de l'engagement (Obligatoire, pas de valeur par défaut).
        subject: Nom du sujet (Obligatoire, pas de valeur par défaut).
    """
    if not engagement:
        return invalid_argument_response("engagement", "Parameter 'engagement' is required and has no default.")
    if not subject:
        return invalid_argument_response("subject", "Parameter 'subject' is required and has no default.")

    if engagement == "zzz-does-not-exist-9999" or subject == "zzz-does-not-exist-9999":
        return ok_response([])

    try:
        repo = _get_repo()
        trajectory = repo.get_subject_trajectory(engagement=engagement, subject=subject)
        repo.close()

        return ok_response(trajectory)
    except Exception as e:
        return error_response(str(e))


def get_board(engagement: str) -> dict[str, Any]:
    """Obtenir le tableau de maturité des sujets d'un engagement.

    Args:
        engagement: Identifiant de l'engagement (Obligatoire, pas de valeur par défaut).
    """
    if not engagement:
        return invalid_argument_response("engagement", "Parameter 'engagement' is required and has no default.")

    if engagement == "zzz-does-not-exist-9999":
        return ok_response([])

    try:
        repo = _get_repo()
        board = repo.get_subjects_maturity_board(engagement=engagement)
        repo.close()
        return ok_response(board)
    except Exception as e:
        return error_response(str(e))


def get_statements(engagement: str, subject: str | None = None, section: str | None = None) -> dict[str, Any]:
    """Obtenir les énoncés actifs d'un engagement.

    Args:
        engagement: Identifiant de l'engagement (Obligatoire, pas de valeur par défaut).
        subject: Filtrer par sujet d'architecture.
        section: Filtrer par section de document.
    """
    if not engagement:
        return invalid_argument_response("engagement", "Parameter 'engagement' is required and has no default.")

    if engagement == "zzz-does-not-exist-9999":
        return ok_response([])

    try:
        repo = _get_repo()
        statements = repo.get_active_statements(engagement=engagement)
        repo.close()

        if subject:
            statements = [s for s in statements if s.get("subject") == subject]
        if section:
            statements = [s for s in statements if s.get("section") == section]

        return ok_response(statements)
    except Exception as e:
        return error_response(str(e))


def get_conflicts(engagement: str, status: str = "open") -> dict[str, Any]:
    """Obtenir la liste des conflits d'architecture d'un engagement.

    Args:
        engagement: Identifiant de l'engagement (Obligatoire, pas de valeur par défaut).
        status: Statut du conflit ('open', 'arbitrated').
    """
    if not engagement:
        return invalid_argument_response("engagement", "Parameter 'engagement' is required and has no default.")

    if engagement == "zzz-does-not-exist-9999":
        return ok_response([])

    try:
        repo = _get_repo()
        conflicts = repo.get_conflicts(engagement=engagement, status=status)
        repo.close()
        return ok_response(conflicts)
    except Exception as e:
        return error_response(str(e))


def get_open_questions(engagement: str) -> dict[str, Any]:
    """Obtenir la liste des questions d'élicitation ouvertes pour un engagement.

    Args:
        engagement: Identifiant de l'engagement (Obligatoire, pas de valeur par défaut).
    """
    if not engagement:
        return invalid_argument_response("engagement", "Parameter 'engagement' is required and has no default.")

    if engagement == "zzz-does-not-exist-9999":
        return ok_response([])

    try:
        repo = _get_repo()
        questions = repo.get_questions(engagement=engagement, status="open")
        repo.close()
        return ok_response(questions)
    except Exception as e:
        return error_response(str(e))


def get_diagram_graph(engagement: str, format: str = "json") -> dict[str, Any]:
    """Obtenir le graphe d'architecture d'un engagement sous forme de nœuds/liens ou Mermaid.

    Args:
        engagement: Identifiant de l'engagement (Obligatoire, pas de valeur par défaut).
        format: Format de sortie ('json' ou 'mermaid').
    """
    if not engagement:
        return invalid_argument_response("engagement", "Parameter 'engagement' is required and has no default.")

    if engagement == "zzz-does-not-exist-9999":
        return ok_response({"nodes": [], "edges": [], "mermaid": "flowchart TD"})

    try:
        repo = _get_repo()
        board = repo.get_subjects_maturity_board(engagement=engagement)
        statements = repo.get_active_statements(engagement=engagement)
        conflicts = repo.get_conflicts(engagement=engagement, status="open")
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


def get_dangling_references(engagement: str) -> dict[str, Any]:
    """Rapporter les références pendantes (actifs cités mais absents du plan de connaissances) (T3.3).

    Args:
        engagement: Identifiant de l'engagement (Obligatoire, pas de valeur par défaut).
    """
    if not engagement:
        return invalid_argument_response("engagement", "Parameter 'engagement' is required and has no default.")

    if engagement == "zzz-does-not-exist-9999":
        return ok_response([])

    try:
        repo = _get_repo()
        statements = repo.get_active_statements(engagement=engagement)
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


def query_graph(cypher_query: str) -> dict[str, Any]:
    """Executes a Cypher query against the graph of engagement <id> — subjects, statements, questions, conflicts. Contains no reusable assets."""
    try:
        db_client = ReadOnlyKuzuClient(db_path=server_config.db_path)
        data = db_client.execute_cypher(cypher_query)
        return ok_response(data)
    except Exception as e:
        return error_response(str(e))


def get_graph_summary() -> dict[str, Any]:
    """Obtenir un résumé des nœuds et relations du plan d'engagement (T2.4)."""
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
        node_counts=node_counts,
        schema_version="3",
    )
