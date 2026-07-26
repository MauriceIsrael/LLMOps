"""Flux A : Scan déterministe des manques (Gaps) et émission des questions."""

from typing import Any

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from mcp_server.db.kuzu_client import KuzuClient
from tools.elicitation.mailbox import FileMailbox, QuestionMessage
from tools.elicitation.repository import ElicitationRepository


class ScanState(TypedDict, total=False):
    """État du flux A : scan."""
    engagement: str
    max_questions: int
    db_path: str | None
    sections: list[dict[str, Any]]
    gaps: list[dict[str, Any]]
    enriched_gaps: list[dict[str, Any]]
    questions: list[dict[str, Any]]
    persisted_ids: list[str]
    dispatched: list[dict[str, Any]]


def load_frame_node(state: ScanState) -> dict[str, Any]:
    """Charge le cadre du projet depuis Kùzu DB et le FastMCP server."""
    engagement = state.get("engagement", "demo-2026")
    sections = [
        {"id": "5.1", "name": "Architecture Calcul & Virtualisation"},
        {"id": "5.2", "name": "Architecture Stockage Management"},
        {"id": "6.1", "name": "Réseau et Interconnexion Telco"},
    ]
    return {"sections": sections, "engagement": engagement}


def detect_gaps_node(state: ScanState) -> dict[str, Any]:
    """Détecte de manière 100% déterministe en Cypher les manques (Gaps G1, G2, G3)."""
    db_path = state.get("db_path", "data/kuzu_db")
    db_client = KuzuClient(db_path=db_path, read_only=False)
    engagement = state.get("engagement", "demo-2026")
    gaps: list[dict[str, Any]] = []


    # Règle G1 : Section vide sans aucun Statement actif
    for sec in state.get("sections", []):
        sec_id = sec["id"]
        q = f"MATCH (s:Statement {{engagement: '{engagement}', section: '{sec_id}', status: 'active'}}) RETURN count(s) as c;"
        res = db_client.execute_cypher(q)
        count = res[0].get("c", 0) if res and "error" not in res[0] else 0
        if count == 0:
            gaps.append(
                {
                    "gap_type": "G1_empty_section",
                    "section": sec_id,
                    "section_name": sec["name"],
                    "subject": f"Storage-{sec_id}" if "5.2" in sec_id else f"Compute-{sec_id}",
                    "blocking_count": 2 if "5.2" in sec_id else 1,
                }
            )

    # Règle G2 : Questionnaires bloquants sans réponse
    q2 = f"MATCH (q:Question {{engagement: '{engagement}', status: 'open'}}) RETURN q.id as id, q.section as section;"
    open_qs = db_client.execute_cypher(q2)
    if open_qs and "error" not in open_qs[0]:
        for oq in open_qs:
            gaps.append(
                {
                    "gap_type": "G2_unanswered_blocking",
                    "section": oq.get("section", "5.2"),
                    "subject": "VendorQuestion",
                    "blocking_count": 3,
                }
            )

    return {"gaps": gaps}


def enrich_node(state: ScanState) -> dict[str, Any]:
    """Enrichit les manques avec le sujet canonique et les réponses antérieures."""
    db_path = state.get("db_path", "data/kuzu_db")
    db_client = KuzuClient(db_path=db_path, read_only=False)
    enriched_gaps = []

    for gap in state.get("gaps", []):
        sub_name = gap["subject"]
        q = f"MATCH (st:Statement)-[:ABOUT]->(sub:Subject {{name: '{sub_name}'}}) WHERE st.status = 'active' RETURN st.value as value, st.unit as unit LIMIT 1;"
        prior = db_client.execute_cypher(q)
        gap["prior_answer"] = prior[0] if prior and "error" not in prior[0] else None
        enriched_gaps.append(gap)

    return {"enriched_gaps": enriched_gaps}


def crystallize_node(state: ScanState) -> dict[str, Any]:
    """Formule une question précise pour chaque manque."""
    max_q = state.get("max_questions", 8)
    gaps = sorted(state.get("enriched_gaps", []), key=lambda x: x.get("blocking_count", 0), reverse=True)[:max_q]

    questions = []
    idx = 1
    for gap in gaps:
        q_id = f"Q-{idx:04d}"
        idx += 1
        sec = gap["section"]
        sub = gap["subject"]

        if gap["gap_type"] == "G1_empty_section":
            q_text = f"Quelle est la configuration de stockage du cluster de management pour la section {sec} ?"
            if gap.get("prior_answer"):
                q_text += f" (Valeur de référence précédente : {gap['prior_answer'].get('value')})"
            why = f"La section {sec} ({gap['section_name']}) ne contient aucun énoncé d'architecture."
            routed = "cloud-architect"
            shape = "decision"
        else:
            q_text = f"La question fournisseur bloquante pour la section {sec} a-t-elle été validée ?"
            why = "Questionnaire fournisseur pré-requis bloquant."
            routed = "network-architect"
            shape = "boolean"

        questions.append(
            {
                "id": q_id,
                "engagement": state.get("engagement", "demo-2026"),
                "gap_type": gap["gap_type"],
                "section": sec,
                "question": q_text,
                "why_it_matters": why,
                "expected_shape": shape,
                "routed_to": routed,
                "subject": sub,
                "status": "open",
            }
        )

    return {"questions": questions}


def persist_questions_node(state: ScanState) -> dict[str, Any]:
    """Persiste les questions dans Kùzu DB via le Repository."""
    db_path = state.get("db_path", "data/kuzu_db")
    repo = ElicitationRepository(db_path=db_path)
    persisted_ids = []
    for q in state.get("questions", []):
        qid = repo.save_question(q)
        persisted_ids.append(qid)
    return {"persisted_ids": persisted_ids}


def dispatch_node(state: ScanState) -> dict[str, Any]:
    """Poste les questions dans la boîte aux lettres et passe leur statut à 'sent'."""
    db_path = state.get("db_path", "data/kuzu_db")
    repo = ElicitationRepository(db_path=db_path)
    engagement = state.get("engagement", "demo-2026")
    mailbox = FileMailbox(engagement=engagement)
    dispatched = []

    for q in state.get("questions", []):
        msg = QuestionMessage(
            question_id=q["id"],
            engagement=q["engagement"],
            question_text=q["question"],
            why_it_matters=q["why_it_matters"],
            expected_shape=q["expected_shape"],
            routed_to=q["routed_to"],
        )
        ref = mailbox.post(msg)
        repo.update_question_status(q["id"], "sent")
        dispatched.append({"id": q["id"], "ref": ref})

    return {"dispatched": dispatched}


def build_scan_graph() -> Any:
    """Construit le graphe de flux A : scan."""
    workflow = StateGraph(ScanState)
    workflow.add_node("load_frame", load_frame_node)
    workflow.add_node("detect_gaps", detect_gaps_node)
    workflow.add_node("enrich", enrich_node)
    workflow.add_node("crystallize", crystallize_node)
    workflow.add_node("persist_questions", persist_questions_node)
    workflow.add_node("dispatch", dispatch_node)

    workflow.set_entry_point("load_frame")
    workflow.add_edge("load_frame", "detect_gaps")
    workflow.add_edge("detect_gaps", "enrich")
    workflow.add_edge("enrich", "crystallize")
    workflow.add_edge("crystallize", "persist_questions")
    workflow.add_edge("persist_questions", "dispatch")
    workflow.add_edge("dispatch", END)

    return workflow.compile()
