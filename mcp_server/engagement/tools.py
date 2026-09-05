"""Engagement Plane Tools.

Provides tools for inspecting and interacting with engagement-specific graph state (Subject, Statement, Conflict, Question, Uncertainty).
"""

from pathlib import Path
from typing import Any

from mcp_server.core.auth import authorise
from mcp_server.core.config import server_config
from mcp_server.core.db import (
    get_engagement_path,
    open_connection,
)
from mcp_server.core.envelope import (
    error_response,
    invalid_argument_response,
    not_found_response,
    ok_response,
)
from tools.elicitation.repository import ElicitationRepository


def _mermaid_label(text: str, max_len: int = 48) -> str:
    if not text:
        return '""'
    clean = text.replace('"', "'").replace("\n", " ").strip()
    if len(clean) > max_len:
        clean = clean[: max_len - 1] + "…"
    return f'"{clean}"'


def _get_repo(engagement: str | None = None, db_path: str | Path | None = None) -> ElicitationRepository:
    if db_path:
        p = Path(db_path)
    else:
        eng_id = engagement or server_config.engagement or "nordwave-mcx-2027"
        p = get_engagement_path(eng_id)
    return ElicitationRepository(db_path=p)


def get_subject(subject: str, engagement: str | None = None, db_path: str | Path | None = None) -> dict[str, Any]:
    """Retrieve details, maturity level, and framing definition for an architecture subject.

    Args:
        subject: Name of the architecture subject (e.g. 'mcx-services').
        engagement: Unique engagement identifier (defaults to deployment configuration).
        db_path: Optional explicit database path override.
    """
    eng = engagement or server_config.engagement or "nordwave-mcx-2027"
    authorise(engagement=eng)

    if not subject:
        return invalid_argument_response("subject", "Parameter 'subject' is required.")

    try:
        repo = _get_repo(engagement=eng, db_path=db_path)
        board = repo.get_subjects_maturity_board(engagement=eng)
        repo.close()

        match = [s for s in board if s.get("subject") == subject]
        if match:
            return ok_response(match[0], count=1)
        return not_found_response(subject)
    except FileNotFoundError:
        return not_found_response(subject)
    except Exception as e:
        return error_response(str(e))


def get_subject_trajectory(subject: str, engagement: str | None = None, db_path: str | Path | None = None) -> dict[str, Any]:
    """Retrieve maturity level progression trajectory (timeline of questions and answer excerpts) for a subject.

    Args:
        subject: Name of the architecture subject (e.g. 'mcx-services').
        engagement: Unique engagement identifier (defaults to deployment configuration).
        db_path: Optional explicit database path override.
    """
    eng = engagement or server_config.engagement or "nordwave-mcx-2027"
    authorise(engagement=eng)

    if not subject:
        return invalid_argument_response("subject", "Parameter 'subject' is required.")

    try:
        repo = _get_repo(engagement=eng, db_path=db_path)
        trajectory = repo.get_subject_trajectory(engagement=eng, subject=subject)
        repo.close()

        return ok_response(trajectory)
    except FileNotFoundError:
        return ok_response([])
    except Exception as e:
        return error_response(str(e))


def get_board(engagement: str | None = None) -> dict[str, Any]:
    """Retrieve the maturity board showing all subjects, maturity levels, origin, and blocking questions.

    Args:
        engagement: Unique engagement identifier (defaults to deployment configuration).
    """
    eng = engagement or server_config.engagement or "nordwave-mcx-2027"
    authorise(engagement=eng)

    try:
        repo = _get_repo(engagement=eng)
        board = repo.get_subjects_maturity_board(engagement=eng)
        repo.close()
        return ok_response(board)
    except FileNotFoundError:
        return ok_response([])
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
    eng = engagement or server_config.engagement or "nordwave-mcx-2027"
    authorise(engagement=eng)

    try:
        repo = _get_repo(engagement=eng)
        statements = repo.get_active_statements(engagement=eng)
        repo.close()

        if subject:
            statements = [s for s in statements if s.get("subject") == subject]
        if section:
            statements = [s for s in statements if s.get("section") == section]
        if status:
            statements = [s for s in statements if s.get("status") == status]

        return ok_response(statements)
    except FileNotFoundError:
        return ok_response([])
    except Exception as e:
        return error_response(str(e))


def get_conflicts(engagement: str | None = None, status: str = "open") -> dict[str, Any]:
    """Retrieve architecture conflicts for an engagement (declared by architects or detected automatically).

    Args:
        engagement: Unique engagement identifier (defaults to deployment configuration).
        status: Conflict status filter ('open', 'arbitrated').
    """
    eng = engagement or server_config.engagement or "nordwave-mcx-2027"
    authorise(engagement=eng)

    try:
        repo = _get_repo(engagement=eng)
        conflicts = repo.get_conflicts(engagement=eng, status=status)
        repo.close()
        return ok_response(conflicts)
    except FileNotFoundError:
        return ok_response([])
    except Exception as e:
        return error_response(str(e))


def get_open_questions(engagement: str | None = None, role: str | None = None) -> dict[str, Any]:
    """Retrieve open elicitation questions for an engagement, optionally filtered by targeted architect role.

    Args:
        engagement: Unique engagement identifier (defaults to deployment configuration).
        role: Optional architect role filter (e.g. 'mcx-architect', 'chief-architect').
    """
    eng = engagement or server_config.engagement or "nordwave-mcx-2027"
    authorise(engagement=eng)

    try:
        repo = _get_repo(engagement=eng)
        questions = repo.get_open_questions(engagement=eng)
        repo.close()

        if role:
            questions = [q for q in questions if q.get("routed_to") == role]

        return ok_response(questions)
    except FileNotFoundError:
        return ok_response([])
    except Exception as e:
        return error_response(str(e))


def get_diagram_graph(
    engagement: str | None = None, format: str = "json", db_path: str | Path | None = None
) -> dict[str, Any]:
    """Retrieve the architecture graph for an engagement formatted as JSON nodes/edges or Mermaid syntax.

    Args:
        engagement: Unique engagement identifier (defaults to deployment configuration).
        format: Desired output format ('json' for nodes & edges array, 'mermaid' for Mermaid flowchart).
        db_path: Optional explicit database path override.
    """
    eng = engagement or server_config.engagement or "nordwave-mcx-2027"
    authorise(engagement=eng)

    try:
        repo = _get_repo(engagement=eng, db_path=db_path)
        board = repo.get_subjects_maturity_board(engagement=eng)
        statements = repo.get_active_statements(engagement=eng)
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
            lbl = _mermaid_label(f"{n['label']} ({n.get('level', '')})")
            mermaid_lines.append(f'    {n["id"]}[{lbl}]')
        for idx, e in enumerate(edges):
            pred_lbl = _mermaid_label(e["predicate"])
            target_text = e["target"]
            target_id = f"node_t_{idx}"
            target_lbl = _mermaid_label(target_text)
            mermaid_lines.append(f'    {target_id}[{target_lbl}]')
            mermaid_lines.append(f'    {e["source"]} -->|{pred_lbl}| {target_id}')

        if not nodes:
            return ok_response({"engagement": eng, "format": format, "nodes": [], "edges": [], "mermaid": "flowchart TD"}, count=0)

        return ok_response({
            "engagement": eng,
            "format": format,
            "nodes": nodes,
            "edges": edges,
            "mermaid": "\n".join(mermaid_lines),
        }, count=len(nodes))
    except FileNotFoundError:
        return ok_response({"engagement": eng, "format": format, "nodes": [], "edges": [], "mermaid": "flowchart TD"}, count=0)
    except Exception as e:
        return error_response(str(e))


def get_dangling_references(engagement: str | None = None) -> dict[str, Any]:
    """Report unresolved dangling references (cited knowledge assets not present in the knowledge base).

    Args:
        engagement: Unique engagement identifier (defaults to deployment configuration).
    """
    eng = engagement or server_config.engagement or "nordwave-mcx-2027"
    authorise(engagement=eng)

    try:
        repo = _get_repo(engagement=eng)
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
    except FileNotFoundError:
        return ok_response([])
    except Exception as e:
        return error_response(str(e))


def get_render_payload(engagement: str | None = None, db_path: str | Path | None = None) -> dict[str, Any]:
    """Retrieve complete structured architecture document payload and synthesis data for external renderers.

    Args:
        engagement: Unique engagement identifier (defaults to deployment configuration).
        db_path: Optional explicit database path override.
    """
    eng = engagement or server_config.engagement or "nordwave-mcx-2027"
    authorise(engagement=eng)

    try:
        repo = _get_repo(engagement=eng, db_path=db_path)
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
    except FileNotFoundError:
        return ok_response({
            "engagement": eng,
            "status": "provisional",
            "is_provisional": True,
            "maturity_board": [],
            "active_statements": [],
            "open_conflicts": [],
            "uncertainties": [],
            "unripe_subjects": [],
        })
    except Exception as e:
        return error_response(str(e))


def get_engagement_export(engagement: str | None = None) -> dict[str, Any]:
    """Retrieve complete bulk export (board, render payload, diagram graph) for an engagement in a single call (E4).

    Args:
        engagement: Unique engagement identifier (defaults to deployment configuration).
    """
    eng = engagement or server_config.engagement or "nordwave-mcx-2027"
    authorise(engagement=eng)

    board_res = get_board(engagement=eng)
    payload_res = get_render_payload(engagement=eng)
    diagram_res = get_diagram_graph(engagement=eng, format="mermaid")

    export_data = {
        "engagement": eng,
        "board": board_res.get("data", []),
        "render_payload": payload_res.get("data", {}),
        "diagram_graph": diagram_res.get("data", {}),
    }

    return ok_response(export_data)


def query_graph(cypher_query: str, engagement: str | None = None) -> dict[str, Any]:
    """Executes a read-only Cypher query against the engagement graph when engagement is specified, or against the active server database. Contains no reusable assets."""
    eng = engagement or server_config.engagement or "nordwave-mcx-2027"
    authorise(engagement=eng)

    try:
        db_client = open_connection(scope=eng)
        data = db_client.execute_cypher(cypher_query)
        return ok_response(data)
    except FileNotFoundError as e:
        return not_found_response(id_val=eng, data=str(e))
    except Exception as e:
        return error_response(str(e))


def get_graph_summary() -> dict[str, Any]:
    """Discovers available databases and returns node counts for knowledge assets and active engagements.

    This server is read-only by design. Project data is written only through the elicitation engine's human-confirmation flow; see TPL-elicitation-proto for how to produce an engagement graph (E5).
    """
    authorise(engagement="nordwave-mcx-2027")
    from mcp_server.knowledge.tools import get_graph_summary as kb_summary
    return kb_summary()
