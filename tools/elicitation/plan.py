"""Commande Elicit Plan — Instruction Planning & Bilans de Cadrage."""

from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from tools.elicitation.models.blueprint_schema import load_blueprint
from tools.elicitation.repository import ElicitationRepository

console = Console()


def generate_instruction_plan(
    engagement: str,
    blueprint_path: str | Path = "data/kb/blueprints/BLU-hla-mcx.yaml",
    db_path: str | Path = "data/kuzu_db",
    roster: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Génère le plan d'instructions complet à 4 blocs selon SPEC-PLANNING-AND-DEMO."""
    roster = roster or {
        "mcx-service-architect": "amina",
        "mobile-core-architect": "rui",
        "chief-architect": "sofia",
    }

    blueprint = load_blueprint(blueprint_path)
    repo = ElicitationRepository(db_path=db_path)

    # 1. Blueprint Coverage
    coverage_rows = []
    for sec in blueprint.sections:
        subj_levels = []
        is_ready = True
        reqs = sec.get_requirements()
        if not reqs:
            is_ready = False
        for req in reqs:
            sub_name = req.subject
            mat = repo.get_subject_maturity(sub_name, engagement=engagement)
            lvl = mat.get("level", "L0_named")
            subj_levels.append(f"{sub_name} ({lvl})")
            if lvl != sec.min_level_final and lvl != "L3_decided" and lvl != "L4_specified":
                is_ready = False

        status = "ready" if is_ready else "provisional"
        coverage_rows.append({
            "section_id": sec.id,
            "title": sec.title,
            "requires": ", ".join(subj_levels),
            "min_level_final": sec.min_level_final,
            "status": status,
            "routes_to": sec.routes_to,
        })

    # 2. Full Gap Inventory
    subjects_board = repo.get_subjects_maturity_board(engagement)
    gap_inventory = []
    for row in subjects_board:
        s_name = row["subject"]
        s_level = row["level"]
        gap_inventory.append({
            "subject": s_name,
            "level": s_level,
            "origin": row.get("origin", "declared"),
            "status": "active" if s_level != "L4_specified" else "complete",
        })

    # 3. Expertise Profiles & Staffing Warning
    role_gaps: dict[str, int] = {}
    for sec in blueprint.sections:
        role_gaps[sec.routes_to] = role_gaps.get(sec.routes_to, 0) + 1

    profiles = []
    warnings = []
    for role, count in role_gaps.items():
        contributor = roster.get(role, "— NOT STAFFED")
        if contributor == "— NOT STAFFED":
            warnings.append(f"[WARNING] Staffing gap: Role '{role}' has {count} required sections but NO assigned contributor in roster!")
        profiles.append({
            "role": role,
            "gaps": count,
            "open": 0,
            "est_answers": count,
            "contributor": contributor,
        })

    # 4. Projected Sequence
    projected_seq = [
        "1. Frame L1 subjects: mcx-services, mobile-core, transport",
        "2. Decompose mcx-services -> group-management, floor-control, media-distribution, lmr-interworking",
        "3. Frame and decide L2/L3 parameters for child MCX services & core QoS profile",
        "4. Specify L4 QoS pre-emption and finalise section readiness",
    ]

    return {
        "blueprint_id": blueprint.id,
        "blueprint_title": blueprint.title,
        "coverage": coverage_rows,
        "gap_inventory": gap_inventory,
        "expertise_profiles": profiles,
        "warnings": warnings,
        "projected_sequence": projected_seq,
    }


def render_plan_cli(plan: dict[str, Any]) -> None:
    """Affiche le plan d'instruction sous forme de tableaux Rich dans la console."""
    console.print(f"\n📋 [bold blue]Instruction Plan — {plan['blueprint_title']} ({plan['blueprint_id']})[/bold blue]\n")

    # Table 1: Coverage
    t1 = Table(title="1. Coverage of the Blueprint")
    t1.add_column("Section", style="cyan")
    t1.add_column("Title")
    t1.add_column("Requires Subjects & Levels")
    t1.add_column("Required Level")
    t1.add_column("Status", style="bold")
    t1.add_column("Routed To", style="magenta")

    for c in plan["coverage"]:
        st_color = "green" if c["status"] == "ready" else "yellow"
        t1.add_row(
            c["section_id"],
            c["title"],
            c["requires"],
            c["min_level_final"],
            f"[{st_color}]{c['status']}[/{st_color}]",
            c["routes_to"],
        )
    console.print(t1)

    # Table 2: Profiles & Warnings
    console.print("\n")
    t2 = Table(title="2. Expertise Profiles & Staffing")
    t2.add_column("Role", style="magenta")
    t2.add_column("Gaps", justify="right")
    t2.add_column("Open", justify="right")
    t2.add_column("Est. Answers", justify="right")
    t2.add_column("Contributor", style="bold")

    for p in plan["expertise_profiles"]:
        c_style = "red" if p["contributor"] == "— NOT STAFFED" else "green"
        t2.add_row(
            p["role"],
            str(p["gaps"]),
            str(p["open"]),
            str(p["est_answers"]),
            f"[{c_style}]{p['contributor']}[/{c_style}]",
        )
    console.print(t2)

    for w in plan["warnings"]:
        console.print(f"[bold red]{w}[/bold red]")

    # Projected Sequence
    console.print("\n[bold]3. Projected Sequence:[/bold]")
    for step in plan["projected_sequence"]:
        console.print(f"  • {step}")
    console.print("\n")
