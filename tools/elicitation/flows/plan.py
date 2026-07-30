"""Module graph/flow pour elicit plan."""

from pathlib import Path
from typing import Any, TypedDict

import yaml
from langgraph.graph import END, StateGraph

from tools.elicitation.models.blueprint_schema import load_blueprint
from tools.elicitation.repository import ElicitationRepository


class PlanState(TypedDict, total=False):
    engagement: str
    db_path: str
    blueprint_id: str
    blueprint_path: str
    roster_path: str
    coverage: list[dict[str, Any]]
    expertise_profiles: list[dict[str, Any]]
    warnings: list[str]


def plan_node(state: PlanState) -> dict[str, Any]:
    engagement = state.get("engagement", "nordwave-mcx-2027")
    bp_path = state.get("blueprint_path", "data/kb/blueprints/BLU-hla-mcx.yaml")
    db_path = state.get("db_path", "data/kuzu_db")
    roster_path = state.get("roster_path")

    blueprint = load_blueprint(bp_path)
    repo = ElicitationRepository(db_path=db_path)

    # Charger le roster
    role_to_users: dict[str, list[str]] = {}
    if roster_path and Path(roster_path).exists():
        data = yaml.safe_load(Path(roster_path).read_text(encoding="utf-8")) or []
        for entry in data:
            login = entry.get("login") or entry.get("name", "unknown")
            roles = entry.get("roles") or [entry.get("role")]
            for r in roles:
                if r:
                    role_to_users.setdefault(r, []).append(login)

    # Coverage
    coverage = []
    for sec in blueprint.sections:
        status = "provisional"
        reqs = sec.get_requirements()
        if not reqs:
            status = "empty"
        else:
            all_final = True
            for req in reqs:
                mat = repo.get_subject_maturity(req.subject, engagement=engagement)
                lvl = mat.get("level", "L0_named")
                if lvl not in ("L3_decided", "L4_specified"):
                    all_final = False
            if all_final:
                status = "final"
        
        coverage.append({
            "section_id": sec.id,
            "title": sec.title,
            "status": status,
            "routes_to": sec.routes_to,
        })

    # Expertise profiles
    role_counts: dict[str, int] = {}
    for sec in blueprint.sections:
        r = sec.routes_to
        role_counts[r] = role_counts.get(r, 0) + 1

    profiles = []
    for role, count in role_counts.items():
        users = role_to_users.get(role, [])
        is_staffed = len(users) > 0
        profiles.append({
            "role": role,
            "gap_count": count,
            "staffed": is_staffed,
            "contributors": users,
        })

    return {
        "coverage": coverage,
        "expertise_profiles": profiles,
    }


def build_plan_graph():
    builder = StateGraph(PlanState)
    builder.add_node("plan", plan_node)
    builder.set_entry_point("plan")
    builder.add_edge("plan", END)
    return builder.compile()
