"""Flux B : Intake des réponses d'experts avec interruption LangGraph (interrupt) et persistance SQLite."""

import re
import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt
from typing_extensions import TypedDict

from tools.elicitation.repository import ElicitationRepository
from tools.elicitation.resolve import database_path, engagement_of, is_managed


class IntakeState(TypedDict, total=False):
    """État du flux B : intake."""
    question_id: str
    from_file: str
    as_person: str
    answer_text: str
    author: str
    role: str
    engagement: str
    db_path: str | None
    question: dict[str, Any]
    candidate_statements: list[dict[str, Any]]
    uncertainties: list[dict[str, Any]]
    candidate_patterns: list[dict[str, Any]]
    no_pattern_for_decomposition: bool
    advance_level_to: str | None
    created_subjects: list[str]
    rejected: bool
    persisted_statement_ids: list[str]
    detected_conflicts: list[dict[str, Any]]
    managed: bool
    created_conflict_ids: list[str]


def load_question_node(state: IntakeState) -> dict[str, Any]:
    """Charge la question et ses données de cadrage depuis Kùzu DB."""
    db_path = database_path(state.get("db_path"), state.get("engagement"))
    repo = ElicitationRepository(db_path=db_path)
    q_id = state.get("question_id", "Q-0001")
    question = repo.get_question(q_id)
    if not question:
        question = {
            "id": q_id,
            "engagement": engagement_of(state.get("engagement")),
            "section": state.get("section", "5.2"),
            "question": state.get("question_text", "Question d'architecture"),
            "status": "sent",
        }
    res: dict[str, Any] = {"question": question}
    if state.get("as_person"):
        res["author"] = state["as_person"]

    if state.get("from_file"):
        from_path = Path(state["from_file"])
        if from_path.exists():
            content = from_path.read_text(encoding="utf-8")
            if "## Your answer" in content:
                ans_text = content.split("## Your answer", 1)[1]
                if "## How to submit" in ans_text:
                    ans_text = ans_text.split("## How to submit", 1)[0]
                ans_text = re.sub(r"<!--.*?-->", "", ans_text, flags=re.DOTALL).strip()
                res["answer_text"] = ans_text
            else:
                res["answer_text"] = content.strip()

    return res


def interpret_node(state: IntakeState) -> dict[str, Any]:
    """Interprète la réponse de l'expert en candidats d'énoncés (Candidate Statements).

    Aucune règle propre à un engagement n'est codée ici : l'interprète est choisi par
    ``get_interpreter`` (scénario scripté de l'engagement s'il existe, sinon passthrough
    qui conserve la réponse verbatim en incertitude sans inventer d'énoncé).
    """
    from tools.elicitation.interpreters import get_interpreter

    q = state.get("question", {})
    eng = engagement_of(state.get("engagement") or q.get("engagement"))
    return get_interpreter(eng).interpret(dict(state))


def confirm_node(state: IntakeState) -> dict[str, Any]:
    """Interruption LangGraph (interrupt) : présente les candidats à l'expert et s'arrête."""
    candidates = state.get("candidate_statements", [])
    q_id = state.get("question_id")

    confirmation = interrupt(
        {
            "message": "Veuillez confirmer ou corriger les énoncés d'architecture proposés.",
            "question_id": q_id,
            "candidate_statements": candidates,
            "candidate_patterns": state.get("candidate_patterns", []),
            "no_pattern_for_decomposition": state.get("no_pattern_for_decomposition", False),
        }
    )

    if isinstance(confirmation, dict):
        action = confirmation.get("action", "accept")
        if action == "reject" or confirmation.get("accept") is False:
            return {"rejected": True}
        if "edited_statements" in confirmation:
            return {"candidate_statements": confirmation["edited_statements"], "rejected": False}

    return {
        "candidate_statements": candidates,
        "uncertainties": state.get("uncertainties", []),
        "rejected": False,
    }


def persist_node(state: IntakeState) -> dict[str, Any]:
    """Persiste les énoncés confirmés dans Kùzu DB et fait évoluer la maturité du sujet.

    Engagement non géré : statut 'active' (démo, scénarios). Engagement **géré** (K14) : statut 'proposed', maturité
    inchangée ; l'affirmation passe par l'API, avec un décideur distinct de l'auteur (issue #78).
    """
    if state.get("rejected"):
        return {}
    managed = is_managed(state.get("engagement"))

    db_path = database_path(state.get("db_path"), state.get("engagement"))
    repo = ElicitationRepository(db_path=db_path)
    persisted_ids = []

    for st in state.get("candidate_statements", []):
        st["status"] = "proposed" if managed else "active"
        sid = repo.save_statement(st)
        persisted_ids.append(sid)

    uncs = state.get("uncertainties", [])
    for unc in uncs:
        repo.save_uncertainty(unc)

    # Avancement de maturité du sujet principal
    adv_lvl = None if managed else state.get("advance_level_to")
    candidates = state.get("candidate_statements") or []
    if adv_lvl and candidates:
        target_sub = candidates[0].get("subject") or (state.get("question") or {}).get("subject", "")
        repo.advance_subject_level(target_sub, adv_lvl)

    # Création des sous-sujets s'il s'agit d'une décomposition
    from mcp_server.core.config import resolve_engagement

    eng = state.get("engagement") or resolve_engagement() or "default"
    for c_sub in state.get("created_subjects", []):
        repo.save_subject(c_sub, engagement=eng, origin="discovered")

    q_id = state.get("question_id")
    if q_id:
        repo.update_question_status(q_id, "confirmed")

    return {"persisted_statement_ids": persisted_ids, "managed": managed}



def check_node(state: IntakeState) -> dict[str, Any]:
    """Détecte les contradictions des nouveaux énoncés avec la **seule** définition du dépôt (``run_checks``, issue #79).

    ``run_checks`` est celle de l'API d'écriture (K15) : le même état du graphe donne les mêmes conflits par les deux
    chemins. Elle enregistre elle-même les nœuds Conflict, sans écraser ni retirer aucun énoncé. Un engagement géré
    n'affirme rien ici (les énoncés sont proposés) : rien à détecter.
    """
    engagement = engagement_of(state.get("engagement"))  # validated before any query (issue #81)
    if state.get("rejected") or state.get("managed"):
        return {}

    repo = ElicitationRepository(db_path=database_path(state.get("db_path"), engagement))
    found = repo.run_checks(engagement, state.get("persisted_statement_ids") or None)
    return {"detected_conflicts": found, "created_conflict_ids": [c["id"] for c in found]}


def get_sqlite_checkpointer(engagement: str, base_dir: str | Path = "projects") -> SqliteSaver:
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

    workflow.set_entry_point("load_question")
    workflow.add_edge("load_question", "interpret")
    workflow.add_edge("interpret", "confirm")
    workflow.add_edge("confirm", "persist")
    workflow.add_edge("persist", "check")
    workflow.add_edge("check", END)

    return workflow.compile(checkpointer=checkpointer)
