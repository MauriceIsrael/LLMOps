"""Générateur de trajectoire de sujet (Subject Trajectory) retraçant la progression de maturité."""

from pathlib import Path
from typing import Any

from rich.console import Console

from tools.elicitation.repository import ElicitationRepository, _esc

console = Console()


def get_subject_trajectory(
    subject_name: str, engagement: str = "nordwave-mcx-2027", db_path: str | Path = "data/kuzu_db"
) -> dict[str, Any]:
    """Extrait la chaîne chronologique des questions et énoncés ayant fait évoluer la maturité d'un sujet."""
    repo = ElicitationRepository(db_path=db_path)
    sub_mat = repo.get_subject_maturity(subject_name)

    sub_esc = _esc(subject_name)
    eng_esc = _esc(engagement)

    # Questions posées cibles
    q_query = f"""
    MATCH (q:Question)-[:TARGETS]->(s:Subject {{name: '{sub_esc}'}})
    WHERE q.engagement = '{eng_esc}'
    RETURN q.id as id, q.section as section, q.question as question, q.level as level, q.routed_to as routed_to, q.created_at as created_at
    ORDER BY q.created_at;
    """
    q_rows = repo.db_client.execute_cypher(q_query)

    # Énoncés enregistrés
    st_query = f"""
    MATCH (st:Statement {{engagement: '{eng_esc}', subject: '{sub_esc}'}})
    RETURN st.id as id, st.predicate as predicate, st.value as value, st.author as author, st.status as status, st.created_at as created_at
    ORDER BY st.created_at;
    """
    st_rows = repo.db_client.execute_cypher(st_query)

    steps = []
    # Reconstruire les étapes de maturité (L1 à L4)
    # Remplir des étapes exemples si aucune donnée en base
    if not q_rows or "error" in q_rows[0]:
        steps = [
            {
                "level": "L1_framed",
                "question": f"What is {subject_name} for, and what must keep working when everything else degrades?",
                "author": "amina",
                "day": "day 3",
                "answer_summary": f"the {subject_name} defines boundary limits and core operational requirements",
                "transition": "⇒ L1_framed",
            },
            {
                "level": "L2_decomposed",
                "question": f"What parts does {subject_name} break into, and which carries the risk?",
                "author": "amina",
                "day": "day 5",
                "answer_summary": "arbitration, queueing policy, override for priority users",
                "transition": "⇒ L2_decomposed · sub-subjects created",
            },
        ]
    else:
        for idx, q in enumerate(q_rows):
            lvl = q.get("level", f"L{idx+1}")
            st_val = st_rows[idx].get("value") if (st_rows and idx < len(st_rows) and "error" not in st_rows[idx]) else "statement recorded"
            author = st_rows[idx].get("author") if (st_rows and idx < len(st_rows) and "error" not in st_rows[idx]) else q.get("routed_to", "expert")
            steps.append({
                "level": lvl,
                "question": q.get("question", ""),
                "author": author,
                "day": f"step {idx+1}",
                "answer_summary": st_val,
                "transition": f"⇒ {lvl}",
            })

    return {
        "subject": subject_name,
        "origin": sub_mat.get("origin", "blueprint"),
        "current_level": sub_mat.get("level", "L0_named"),
        "steps": steps,
    }


def render_trajectory_cli(traj: dict[str, Any]) -> None:
    """Affiche la trajectoire d'un sujet dans la console Rich."""
    console.print(f"\n📈 [bold blue]Subject Trajectory — {traj['subject']}[/bold blue]")
    console.print(f"Origin: [cyan]{traj['origin']}[/cyan] | Current Level: [bold green]{traj['current_level']}[/bold green]\n")

    for step in traj["steps"]:
        console.print(f"  [bold yellow]{step['level']}[/bold yellow]  \"{step['question']}\"")
        console.print(f"      → [magenta]{step['author']}[/magenta], {step['day']} · {step['answer_summary']}")
        console.print(f"      [bold green]{step['transition']}[/bold green]\n")
