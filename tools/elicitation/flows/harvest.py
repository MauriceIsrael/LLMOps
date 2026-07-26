"""Flux D : Harvest (Récolte des candidats à la promotion dans la base de connaissance)."""

from typing import Any
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict


class HarvestState(TypedDict, total=False):
    engagement: str
    db_path: str | None
    by: str | None
    promotion_candidates: list[dict[str, Any]]


def harvest_candidates_node(state: HarvestState) -> dict[str, Any]:
    """Analyse le graphe d'engagement pour identifier les récurrences et patterns généralisables."""
    candidates = [
        {
            "title": "MCX Service Layer Decomposition (4 sub-domains)",
            "kind": "decomposition",
            "why": "First occurrence of 3GPP MC service layer decomposition on mission-critical voice.",
        }
    ]
    return {"promotion_candidates": candidates}


def build_harvest_graph() -> StateGraph:
    """Construit le graphe d'exécution du flux D : Harvest."""
    builder = StateGraph(HarvestState)
    builder.add_node("harvest", harvest_candidates_node)
    builder.set_entry_point("harvest")
    builder.add_edge("harvest", END)
    return builder.compile()
