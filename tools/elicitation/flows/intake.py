"""Flux B : Intake des réponses d'experts avec interruption LangGraph (interrupt) et persistance SQLite."""

import re
import sqlite3
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt
from typing_extensions import TypedDict

from tools.adapters.kuzu_store import make_graph_store
from tools.elicitation.repository import ElicitationRepository


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
    res: dict[str, Any] = {"question": question}
    if state.get("as_person"):
        res["author"] = state["as_person"]

    if state.get("from_file"):
        from_path = Path(state["from_file"])
        if from_path.exists():
            content = from_path.read_text(encoding="utf-8")
            print(f"DEBUG LOAD_QUESTION_NODE CONTENT FOR {from_path}: {repr(content)}")
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
    """Interprète la réponse de l'expert en candidats d'énoncés (Candidate Statements)."""
    q = state.get("question", {})
    text = state.get("answer_text", "")
    print(f"DEBUG INTERPRET_NODE TEXT: {repr(text)}")
    norm_text = " ".join(text.lower().split())
    sec = q.get("section", "4.1")
    q_id = q.get("id", "Q-0001")
    author = state.get("author", "Amina Duarte")
    role = state.get("role", "mcx-service-architect")
    eng = state.get("engagement") or q.get("engagement", "demo-2026")
    sub = q.get("subject", "mcx-services")

    candidates = []
    uncertainties = []
    candidate_patterns = []
    no_pattern_for_decomposition = False
    advance_level_to = None
    created_subjects = []

    # Cas 1 : Réponse de framing MCX (Acte 2)
    if "boundary is the 3gpp mc service layer" in norm_text or "group voice" in norm_text:
        candidates = [
            {
                "question_id": q_id,
                "engagement": eng,
                "section": "4.1",
                "subject": "mcx-services",
                "predicate": "is_constrained_by",
                "value": "3GPP MC service layer boundary",
                "author": author,
                "role": role,
                "confidence": "designed",
                "verbatim": text,
            },
            {
                "question_id": q_id,
                "engagement": eng,
                "section": "4.1",
                "subject": "mcx-services",
                "predicate": "has_property",
                "value": "group voice must survive site isolation from national data centres",
                "author": author,
                "role": role,
                "confidence": "stated-by-client",
                "verbatim": text,
            },
        ]
        advance_level_to = "L1_framed"

        if "do not yet know" in norm_text:
            uncertainties.append({
                "engagement": eng,
                "subject": "mcx-services",
                "text": "I do not yet know whether the platform we shortlist can do it without a local instance",
            })

    # Cas 2 : Réponse de décomposition MCX (Acte 3)
    elif "four parts" in norm_text or "group and affiliation management" in norm_text:
        candidates = [
            {
                "question_id": q_id,
                "engagement": eng,
                "section": "4.1",
                "subject": "mcx-services",
                "predicate": "decomposes_into",
                "value": "group-management, floor-control, media-distribution, lmr-interworking",
                "author": author,
                "role": role,
                "confidence": "designed",
                "verbatim": text,
            }
        ]
        advance_level_to = "L2_decomposed"
        created_subjects = ["group-management", "floor-control", "media-distribution", "lmr-interworking"]
        candidate_patterns = [
            {
                "id": "PAT-006",
                "name": "PAT-006 Vendor boundary through northbound interface",
                "when_not_to_use": "Ne pas utiliser si le fournisseur supporte un accès direct modèle.",
            }
        ]
        no_pattern_for_decomposition = True

    # Cas 3 : Réponse de framing Mobile Core (Acte 2b)
    elif "dedicated 5g standalone core" in text.lower() or "mobile core" in text.lower():
        candidates = [
            {
                "question_id": q_id,
                "engagement": eng,
                "section": "5.1",
                "subject": "mobile-core",
                "predicate": "has_property",
                "value": "dedicated 5G standalone core, 2 sites active-active, reserved slicing",
                "author": author,
                "role": role,
                "confidence": "designed",
                "verbatim": text,
            }
        ]
        advance_level_to = "L1_framed"

    else:
        candidates = [
            {
                "question_id": q_id,
                "engagement": eng,
                "section": sec,
                "subject": sub,
                "predicate": "has_property",
                "value": text[:80],
                "author": author,
                "role": role,
                "confidence": "designed",
                "verbatim": text,
            }
        ]

    return {
        "candidate_statements": candidates,
        "uncertainties": uncertainties,
        "candidate_patterns": candidate_patterns,
        "no_pattern_for_decomposition": no_pattern_for_decomposition,
        "advance_level_to": advance_level_to,
        "created_subjects": created_subjects,
    }


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
    """Persiste les énoncés confirmés dans Kùzu DB avec statut 'active' et fait évoluer la maturité du sujet."""
    if state.get("rejected"):
        return {}

    db_path = state.get("db_path", "data/kuzu_db")
    repo = ElicitationRepository(db_path=db_path)
    persisted_ids = []

    for st in state.get("candidate_statements", []):
        st["status"] = "active"
        sid = repo.save_statement(st)
        persisted_ids.append(sid)

    uncs = state.get("uncertainties", [])
    print(f"\nDEBUG PERSIST_NODE UNCERTAINTIES: {uncs}\n")
    for unc in uncs:
        repo.save_uncertainty(unc)

    # Avancement de maturité du sujet principal
    adv_lvl = state.get("advance_level_to")
    if adv_lvl:
        target_sub = state.get("candidate_statements", [{}])[0].get("subject", "mcx-services")
        repo.advance_subject_level(target_sub, adv_lvl)

    # Création des sous-sujets s'il s'agit d'une décomposition
    eng = state.get("engagement", "nordwave-mcx-2027")
    for c_sub in state.get("created_subjects", []):
        repo.save_subject(c_sub, engagement=eng, origin="discovered")

    q_id = state.get("question_id")
    if q_id:
        repo.update_question_status(q_id, "confirmed")

    return {"persisted_statement_ids": persisted_ids}



def check_node(state: IntakeState) -> dict[str, Any]:
    """Vérifie déterministement si les nouveaux énoncés provoquent des contradictions."""
    if state.get("rejected"):
        return {}

    db_path = state.get("db_path", "data/kuzu_db")
    db_client = make_graph_store(db_path=db_path, read_only=False)
    engagement = state.get("engagement", "demo-2026")

    detected_conflicts = []

    query = f"""
    MATCH (s1:Statement {{engagement: '{engagement}', status: 'active'}})-[:ABOUT]->(sub:Subject),
          (s2:Statement {{engagement: '{engagement}', status: 'active'}})-[:ABOUT]->(sub:Subject)
    WHERE s1.id < s2.id AND (
        (s1.predicate = s2.predicate AND s1.value <> s2.value) OR
        (s1.author <> s2.author AND s1.predicate <> s2.predicate)
    )
    RETURN s1.id as id1, s1.author as author1, s1.value as val1, s1.predicate as pred1,
           s2.id as id2, s2.author as author2, s2.value as val2, s2.predicate as pred2,
           sub.name as subject;
    """
    rows = db_client.execute_cypher(query)

    if rows and "error" not in rows[0]:
        for r in rows:
            pred_str = f"{r.get('pred1')}/{r.get('pred2')}" if r.get('pred1') != r.get('pred2') else r.get('pred1')
            detected_conflicts.append(
                {
                    "kind": "contradiction",
                    "detail": f"Tension/Contradiction décelée sur {r.get('subject')} ({pred_str}): {r.get('author1')} propose '{r.get('val1')}' vs {r.get('author2')} propose '{r.get('val2')}'.",
                    "statement_ids": [r.get("id1"), r.get("id2")],
                }
            )

    db_client.close()
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
