"""Module graph/flow pour les contributions spontanées externes."""

from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from tools.elicitation.contribution_repository import ContributionRepository


class ContributionState(TypedDict, total=False):
    engagement: str
    db_path: str
    action: str  # submit | triage | crystallise | confirm | accept
    as_person: str
    title: str
    material_path: str
    material_text: str
    relates_to: str
    contribution_id: str
    decision: str
    to_subject: str
    accept: bool
    section: str
    rejected: bool
    proposed_statements: list[dict[str, Any]]
    unmapped_terms: list[str]
    persisted_statement_ids: list[str]


def contribution_node(state: ContributionState) -> dict[str, Any]:
    engagement = state.get("engagement", "nordwave-mcx-2027")
    db_path = state.get("db_path", "data/kuzu_db")
    action = state.get("action", "submit")
    as_person = state.get("as_person", "external:contributor")
    ct_id = state.get("contribution_id")

    # Base dir pour artifacts
    base_dir = Path("artifacts")
    crepo = ContributionRepository(engagement=engagement, base_dir=base_dir)

    if action == "submit":
        title = state.get("title", "External Contribution")
        mat_path = state.get("material_path")
        mat_text = state.get("material_text", "")
        if mat_path and Path(mat_path).exists():
            mat_text = Path(mat_path).read_text(encoding="utf-8")
        relates_to = state.get("relates_to", "general")
        c = crepo.submit(contributor=as_person, title=title, material_text=mat_text, relates_to=relates_to)
        return {"contribution_id": c.id}

    elif action == "triage":
        if not ct_id:
            raise ValueError("contribution_id requis pour triage")
        decision = state.get("decision", "accept")
        to_subject = state.get("to_subject")
        c = crepo.triage(ct_id=ct_id, lead_author=as_person, decision=decision, to_subject=to_subject)
        return {"status": c.status}

    elif action == "crystallise":
        if not ct_id:
            raise ValueError("contribution_id requis pour crystallise")
        c = crepo.crystallise(ct_id=ct_id, db_path=db_path)
        return {
            "proposed_statements": c.proposed_statements,
            "unmapped_terms": c.unmapped_terms,
        }

    elif action == "confirm":
        if not ct_id:
            raise ValueError("contribution_id requis pour confirm")
        accept = state.get("accept", True)
        c = crepo.confirm_by_author(ct_id=ct_id, author=as_person, accept=accept)
        return {"status": c.status}

    elif action == "accept":
        if not ct_id:
            raise ValueError("contribution_id requis pour accept")
        c_obj = crepo.get(ct_id)
        if not c_obj or c_obj.status != "confirmed_by_author":
            return {"rejected": True, "persisted_statement_ids": []}
        
        section_id = state.get("section", "4.5")
        c, ids = crepo.accept_by_lead(ct_id=ct_id, lead_author=as_person, section_id=section_id, db_path=db_path)
        return {"persisted_statement_ids": ids}

    return {}


def build_contribution_graph():
    builder = StateGraph(ContributionState)
    builder.add_node("contribution", contribution_node)
    builder.set_entry_point("contribution")
    builder.add_edge("contribution", END)
    return builder.compile()
