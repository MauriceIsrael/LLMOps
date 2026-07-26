"""Flux C : Assemblage du document d'architecture, vérification globale et rapport de statut."""

from pathlib import Path
from typing import Any

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from tools.elicitation.repository import ElicitationRepository


class AssembleState(TypedDict, total=False):
    """État du flux C : assemble."""
    engagement: str
    db_path: str | None
    statements_by_section: dict[str, list[dict[str, Any]]]
    all_statements: list[dict[str, Any]]
    rendered_sections: dict[str, str]
    open_conflicts: int
    open_conflicts_list: list[dict[str, Any]]
    unripe_subjects: list[Any]
    is_provisional: bool
    section_status: dict[str, str]
    document_path: str
    document: str
    status: str



def gather_node(state: AssembleState) -> dict[str, Any]:
    """Rassemble tous les énoncés actifs de l'engagement regroupés par section."""
    db_path = state.get("db_path", "data/kuzu_db")
    repo = ElicitationRepository(db_path=db_path)
    engagement = state.get("engagement", "demo-2026")
    statements = repo.get_active_statements(engagement)

    by_section: dict[str, list[dict[str, Any]]] = {}
    for st in statements:
        sec = st.get("section", "general")
        by_section.setdefault(sec, []).append(st)

    return {"statements_by_section": by_section, "all_statements": statements}


def render_node(state: AssembleState) -> dict[str, Any]:
    """Génère la prose de chaque section exclusivement à partir des énoncés actifs (TPL-authoring)."""
    rendered_sections = {}
    by_section = state.get("statements_by_section", {})

    for sec, st_list in by_section.items():
        prose_lines = [f"### Section {sec}\n"]
        for st in st_list:
            author = st.get("author", "expert")
            conf = st.get("confidence", "verified")
            val = st.get("value", "")
            pred = st.get("predicate", "has_property")

            if conf == "assumed":
                prose_lines.append(f"- *[Sous réserve de confirmation]* Énoncé proposé par {author} : `{pred}` = `{val}`.")
            else:
                prose_lines.append(f"- Énoncé validé (`{conf}`) par {author} : `{pred}` = `{val}`.")

            prose_lines.append(f"  > *Verbatim :* \"{st.get('verbatim', '')}\"")

        rendered_sections[sec] = "\n".join(prose_lines)

    return {"rendered_sections": rendered_sections}


def global_check_node(state: AssembleState) -> dict[str, Any]:
    """Vérifie la cohérence globale : conflits ouverts et maturité des sujets (Section Readiness : L3+)."""
    db_path = state.get("db_path", "data/kuzu_db")
    repo = ElicitationRepository(db_path=db_path)
    engagement = state.get("engagement", "demo-2026")
    open_conflicts_list = repo.get_conflicts(engagement, status="open")

    board = repo.get_subjects_maturity_board(engagement)
    from tools.elicitation.config import SUBJECT_LEVELS
    unripe_subjects = [
        {"subject": b["subject"], "level": b.get("level", "L0_named")}
        for b in board
        if SUBJECT_LEVELS.index(b.get("level", "L0_named")) < SUBJECT_LEVELS.index("L3_decided")
    ]

    is_prov = (len(open_conflicts_list) > 0) or (len(unripe_subjects) > 0)
    section_status = {
        "4.1": "PROVISIONAL" if is_prov else "COMPLETE",
        "4.2": "INCOMPLETE",
        "4.3": "PROVISIONAL",
        "4.4": "INCOMPLETE",
        "5.1": "PROVISIONAL",
    }

    return {
        "open_conflicts": len(open_conflicts_list),
        "open_conflicts_list": open_conflicts_list,
        "unripe_subjects": unripe_subjects,
        "is_provisional": is_prov,
        "section_status": section_status,
    }


def report_node(state: AssembleState) -> dict[str, Any]:
    """Écrit le document final sous projects/<engagement>/document.md et affiche le rapport."""
    engagement = state.get("engagement", "demo-2026")
    out_dir = Path("projects") / engagement
    out_dir.mkdir(parents=True, exist_ok=True)
    doc_path = out_dir / "document.md"

    is_prov = state.get("is_provisional", False)
    status_str = "PROVISIONAL" if is_prov else "COMPLETE"
    open_conflicts_count = state.get("open_conflicts", 0)
    open_conflicts_list = state.get("open_conflicts_list", [])

    content = [
        f"# Document d'Architecture System — Engagement {engagement}",
        f"**Statut du Document :** `{status_str}`",
        f"**Conflits Ouverts :** {open_conflicts_count}\n",
        "---",
        "## Sections Rédigées\n",
    ]

    for sec, text in state.get("rendered_sections", {}).items():
        content.append(text)
        content.append("")

    if is_prov and open_conflicts_list:
        content.append("---")
        content.append("## ⚠️ Registre des Conflits Ouverts\n")
        for c in open_conflicts_list:
            content.append(f"- **Conflit `{c['id']}`** ({c['kind']}) : {c['detail']}")

    full_doc = "\n".join(content)
    doc_path.write_text(full_doc, encoding="utf-8")
    return {"document_path": str(doc_path), "document": full_doc, "status": status_str}


def build_assemble_graph() -> Any:
    """Construit le graphe de flux C : assemble."""
    workflow = StateGraph(AssembleState)
    workflow.add_node("gather", gather_node)
    workflow.add_node("render", render_node)
    workflow.add_node("global_check", global_check_node)
    workflow.add_node("report", report_node)

    workflow.set_entry_point("gather")
    workflow.add_edge("gather", "render")
    workflow.add_edge("render", "global_check")
    workflow.add_edge("global_check", "report")
    workflow.add_edge("report", END)

    return workflow.compile()
