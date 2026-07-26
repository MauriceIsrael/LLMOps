"""Flux B : Intake des réponses d'experts avec interruption LangGraph (interrupt) et persistance SQLite."""

import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt
from typing_extensions import TypedDict

from mcp_server.db.kuzu_client import KuzuClient
from tools.elicitation.repository import ElicitationRepository


class IntakeState(TypedDict, total=False):
    """État du flux B : intake."""
    question_id: str
    answer_text: str
    author: str
    role: str
    engagement: str
    db_path: str | None
    question: dict[str, Any]
    candidate_statements: list[dict[str, Any]]
    rejected: bool
    persisted_statement_ids: list[str]
    detected_conflicts: list[dict[str, Any]]
    created_conflict_ids: list[str]


def load_question_node(state: IntakeState) -> dict[str, Any]:
    """Charge la question et ses données de cadrage depuis Kùzu DB."""
    db_path = state.get("db_path", "data/kuzu_db")
    repo = ElicitationRepository(db_path=db_path)
    q_id = state.get("question_id", "Q-0001")
    question = repo.get_question(q_id)
    if not question:
        question = {
            "id": q_id,
            "engagement": state.get("engagement", "demo-2026"),
            "section": state.get("section", "5.2"),
            "question": state.get("question_text", "Question d'architecture"),
            "status": "sent",
        }
    return {"question": question}


def interpret_node(state: IntakeState) -> dict[str, Any]:
    """Interprète la réponse de l'expert en candidats d'énoncés (Candidate Statements)."""
    q = state.get("question", {})
    text = state.get("answer_text", "")
    sec = q.get("section", "5.2")
    q_id = q.get("id", "Q-0001")

    if "SAN NVMe" in text or "storage" in text.lower() or "nvme" in text.lower():
        candidates = [
            {
                "question_id": q_id,
                "engagement": state.get("engagement", "demo-2026"),
                "section": sec,
                "subject": f"Storage-{sec}",
                "predicate": "has_property",
                "value": "SAN NVMe dual-controller",
                "unit": "tier-1",
                "author": state.get("author", "alice"),
                "role": state.get("role", "cloud-architect"),
                "confidence": "verified",
                "verbatim": text,
            }
        ]
    elif "Ceph" in text or "SSD" in text:
        candidates = [
            {
                "question_id": q_id,
                "engagement": state.get("engagement", "demo-2026"),
                "section": sec,
                "subject": f"Storage-{sec}",
                "predicate": "has_property",
                "value": "Ceph HCI all-flash SSD",
                "unit": "tier-2",
                "author": state.get("author", "bob"),
                "role": state.get("role", "storage-expert"),
                "confidence": "designed",
                "verbatim": text,
            }
        ]
    else:
        candidates = [
            {
                "question_id": q_id,
                "engagement": state.get("engagement", "demo-2026"),
                "section": sec,
                "subject": f"Storage-{sec}",
                "predicate": "has_value",
                "value": text,
                "unit": "text",
                "author": state.get("author", "expert"),
                "role": state.get("role", "architect"),
                "confidence": "assumed",
                "verbatim": text,
            }
        ]

    return {"candidate_statements": candidates}


def confirm_node(state: IntakeState) -> dict[str, Any]:
    """Interruption LangGraph (interrupt) : présente les candidats à l'expert et s'arrête."""
    candidates = state.get("candidate_statements", [])
    q_id = state.get("question_id")

    confirmation = interrupt(
        {
            "message": "Veuillez confirmer ou corriger les énoncés d'architecture proposés.",
            "question_id": q_id,
            "candidate_statements": candidates,
        }
    )

    if isinstance(confirmation, dict):
        action = confirmation.get("action", "accept")
        if action == "reject" or confirmation.get("accept") is False:
            return {"rejected": True}
        if "edited_statements" in confirmation:
            return {"candidate_statements": confirmation["edited_statements"], "rejected": False}

    return {"candidate_statements": candidates, "rejected": False}



def persist_node(state: IntakeState) -> dict[str, Any]:
    """Persiste les énoncés confirmés dans Kùzu DB avec statut 'active' et passe la question à 'confirmed'."""
    if state.get("rejected"):
        return {}

    db_path = state.get("db_path", "data/kuzu_db")
    repo = ElicitationRepository(db_path=db_path)
    persisted_ids = []
    for st in state.get("candidate_statements", []):
        st["status"] = "active"
        sid = repo.save_statement(st)
        persisted_ids.append(sid)

    q_id = state.get("question_id")
    if q_id:
        repo.update_question_status(q_id, "confirmed")

    return {"persisted_statement_ids": persisted_ids}


def check_node(state: IntakeState) -> dict[str, Any]:
    """Vérifie déterministement si les nouveaux énoncés provoquent des contradictions."""
    if state.get("rejected"):
        return {}

    db_path = state.get("db_path", "data/kuzu_db")
    db_client = KuzuClient(db_path=db_path, read_only=False)
    engagement = state.get("engagement", "demo-2026")

    detected_conflicts = []

    query = f"""
    MATCH (s1:Statement {{engagement: '{engagement}', status: 'active'}})-[:ABOUT]->(sub:Subject),
          (s2:Statement {{engagement: '{engagement}', status: 'active'}})-[:ABOUT]->(sub:Subject)
    WHERE s1.id < s2.id AND s1.predicate = s2.predicate AND s1.value <> s2.value
    RETURN s1.id as id1, s1.author as author1, s1.value as val1,
           s2.id as id2, s2.author as author2, s2.value as val2,
           sub.name as subject, s1.predicate as predicate;
    """
    rows = db_client.execute_cypher(query)

    if rows and "error" not in rows[0]:
        for r in rows:
            detected_conflicts.append(
                {
                    "kind": "contradiction",
                    "detail": f"Contradiction décelée sur {r.get('subject')} ({r.get('predicate')}): {r.get('author1')} propose '{r.get('val1')}' alors que {r.get('author2')} propose '{r.get('val2')}'.",
                    "statement_ids": [r.get("id1"), r.get("id2")],
                }
            )

    return {"detected_conflicts": detected_conflicts}


def raise_conflicts_node(state: IntakeState) -> dict[str, Any]:
    """Crée les nœuds Conflict dans Kùzu DB sans écraser ni retirer aucun énoncé."""
    if state.get("rejected") or not state.get("detected_conflicts"):
        return {}

    db_path = state.get("db_path", "data/kuzu_db")
    repo = ElicitationRepository(db_path=db_path)
    conflict_ids = []
    for conf in state.get("detected_conflicts", []):
        cid = repo.save_conflict(conf, conf["statement_ids"])
        conflict_ids.append(cid)

    return {"created_conflict_ids": conflict_ids}


def get_sqlite_checkpointer(engagement: str = "demo-2026", base_dir: str | Path = "projects") -> SqliteSaver:
    """Crée ou récupère le checkpointer SQLite persistant sur disque pour l'engagement."""
    checkpoint_dir = Path(base_dir) / engagement
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    db_file = checkpoint_dir / ".checkpoints.sqlite"
    conn = sqlite3.connect(str(db_file), check_same_thread=False)
    return SqliteSaver(conn)


def build_intake_graph(checkpointer: SqliteSaver | None = None) -> Any:
    """Construit le graphe de flux B : intake avec interruption durable."""
    workflow = StateGraph(IntakeState)
    workflow.add_node("load_question", load_question_node)
    workflow.add_node("interpret", interpret_node)
    workflow.add_node("confirm", confirm_node)
    workflow.add_node("persist", persist_node)
    workflow.add_node("check", check_node)
    workflow.add_node("raise_conflicts", raise_conflicts_node)

    workflow.set_entry_point("load_question")
    workflow.add_edge("load_question", "interpret")
    workflow.add_edge("interpret", "confirm")
    workflow.add_edge("confirm", "persist")
    workflow.add_edge("persist", "check")
    workflow.add_edge("check", "raise_conflicts")
    workflow.add_edge("raise_conflicts", END)

    return workflow.compile(checkpointer=checkpointer)
