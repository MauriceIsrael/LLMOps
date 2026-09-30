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
    """Analyse le graphe d'engagement pour identifier les récurrences et patterns généralisables.

    Les candidats à la promotion propres à un engagement sont déclarés dans son profil
    (``examples/<engagement>/engagement_profile.yaml``) ; rien n'est codé en dur ici.
    """
    from tools.elicitation.profile import load_profile

    candidates = [dict(c) for c in load_profile(state.get("engagement")).harvest_candidates]
    return {"promotion_candidates": candidates}


def build_harvest_graph() -> Any:
    """Construit le graphe d'exécution du flux D : Harvest."""
    builder = StateGraph(HarvestState)
    builder.add_node("harvest", harvest_candidates_node)
    builder.set_entry_point("harvest")
    builder.add_edge("harvest", END)
    return builder.compile()
