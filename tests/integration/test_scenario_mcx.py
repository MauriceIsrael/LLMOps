"""Test d'intégration complet pour le scénario Nordwave MCX (SCENARIO-MCX.md).

Sollicite l'ENSEMBLE des renderers du système à chaque étape du scénario :
- Jinja2 Mailbox Card Renderers (Question, Proposal, Conflict, Arbitration, Maturity Board)
- Assemble Graph Renderer (Document d'Architecture .md aux étapes 2, 5, 6 et 7)

Produit le fichier d'avancement complet `projects/nordwave-mcx-2027/renderer_progression.md`
et les snapshots individuels sous `projects/nordwave-mcx-2027/snapshots/`.
"""

import gc
from pathlib import Path
import pytest
from tools.elicitation.repository import ElicitationRepository
from tools.elicitation.flows.scan import build_scan_graph
from tools.elicitation.flows.intake import build_intake_graph, get_sqlite_checkpointer
from tools.elicitation.flows.assemble import build_assemble_graph
from langgraph.types import Command

# Import direct des renderers et modèles de données du système Mailbox
from tools.elicitation.mailbox.renderers import (
    render_question_card,
    render_proposal_card,
    render_conflict_card,
    render_arbitration_card,
    render_maturity_board,
)
from tools.elicitation.mailbox.models import (
    QuestionCardData,
    QuestionFrame,
    ProposalCardData,
    ConflictCardData,
    ArbitrationCardData,
    StatementData,
)


def test_mcx_scenario_end_to_end(tmp_path):
    db_path = tmp_path / "kuzu_db"
    engagement = "nordwave-mcx-2027"
    repo = ElicitationRepository(db_path=db_path)

    snapshots_dir = Path("projects/nordwave-mcx-2027/snapshots")
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    report_sections = [
        "# 📑 Avancement Découplé du Document d'Architecture & Fiches Mailbox — Nordwave MCX\n",
        "Ce document rassemble les sorties **réellement générées par les renderers Jinja2 et le graphe d'assemblage** du système au fil des réponses de l'équipe d'architectes.\n",
    ]

    # --------------------------------------------------------------------------
    # ACTE 1 : Premier scan sur graphe vierge & Question Card Renderer
    # --------------------------------------------------------------------------
    scan_graph = build_scan_graph()
    scan_res_1 = scan_graph.invoke({"engagement": engagement, "db_path": str(db_path)})

    questions_1 = scan_res_1.get("questions", [])
    assert len(questions_1) > 0
    q_1 = questions_1[0]
    q_1_id = q_1["id"]

    # Sollicitation du Jinja2 Question Card Renderer
    q_card_data = QuestionCardData(
        question_id=q_1_id,
        engagement=engagement,
        section=q_1.get("section", "4.1"),
        question_text=q_1["question"],
        why_it_matters=q_1.get("why_it_matters", "Périmètre et contraintes à définir."),
        expected_shape="Explicitation du périmètre et du mode dégradé",
        routed_to="mcx-service-architect",
        frame=QuestionFrame(
            canonical_subject="mcx-services",
            glossary_terms=["mcx-services", "degraded-mode"],
            section_name="MCX Services Domain",
            blocking_count=3
        ),
    )
    rendered_q_card = render_question_card(q_card_data)
    (snapshots_dir / "acte1_question_card.md").write_text(rendered_q_card, encoding="utf-8")

    report_sections.append(f"""
## 🟢 Acte 1 — Premier Scan (Graphe Vierge)

### 📨 Fiche Question générée par le Question Renderer (`question.md.j2`) :
```markdown
{rendered_q_card}
```
""")

    # --------------------------------------------------------------------------
    # ACTE 2 : Cadrage (Amina Duarte) & Proposal Card + Document Renderer
    # --------------------------------------------------------------------------
    checkpointer = get_sqlite_checkpointer(engagement=engagement)
    intake_graph = build_intake_graph(checkpointer=checkpointer)
    thread_config_1 = {"configurable": {"thread_id": q_1_id}}

    intake_graph.invoke(
        {
            "question_id": q_1_id,
            "answer_text": "The MCX layer delivers group voice. Boundary is 3GPP MC service layer.",
            "author": "Amina Duarte",
            "role": "mcx-service-architect",
            "engagement": engagement,
            "db_path": str(db_path),
        },
        config=thread_config_1,
    )

    confirm_1 = intake_graph.invoke(Command(resume={"action": "accept", "accept": True}), config=thread_config_1)
    s_ids_1 = confirm_1.get("persisted_statement_ids", [])

    s1 = StatementData(
        id="S-0001",
        subject="mcx-services",
        predicate="is_constrained_by",
        value="3GPP MC service layer boundary",
        author="Amina Duarte",
        role="mcx-service-architect",
        confidence="designed",
        verbatim="Boundary is 3GPP MC service layer."
    )
    s2 = StatementData(
        id="S-0002",
        subject="mcx-services",
        predicate="has_property",
        value="group voice must survive site isolation from national data centres",
        author="Amina Duarte",
        role="mcx-service-architect",
        confidence="stated-by-client",
        verbatim="Group voice must survive site isolation."
    )

    repo.save_statement({
        "engagement": engagement,
        "section": "4.1",
        "subject": s1.subject,
        "predicate": s1.predicate,
        "value": s1.value,
        "author": s1.author,
        "role": s1.role,
        "confidence": s1.confidence,
        "status": "active"
    })
    repo.save_statement({
        "engagement": engagement,
        "section": "4.1",
        "subject": s2.subject,
        "predicate": s2.predicate,
        "value": s2.value,
        "author": s2.author,
        "role": s2.role,
        "confidence": s2.confidence,
        "status": "active"
    })

    repo.advance_subject_level("mcx-services", "L1_framed")
    repo.close()
    del repo
    gc.collect()

    repo = ElicitationRepository(db_path=db_path)

    # Sollicitation du Proposal Card Renderer
    prop_card_data = ProposalCardData(
        question_id=q_1_id,
        engagement=engagement,
        section="4.1",
        statements=[s1, s2],
        verbatim="The MCX layer delivers group voice. Boundary is 3GPP MC service layer."
    )
    rendered_prop_card = render_proposal_card(prop_card_data)
    (snapshots_dir / "acte2_proposal_card.md").write_text(rendered_prop_card, encoding="utf-8")

    # Sollicitation du Document Assembly Renderer (Acte 2)
    assemble_graph = build_assemble_graph()
    ass_res_2 = assemble_graph.invoke({"engagement": engagement, "db_path": str(db_path)})
    doc_text_2 = Path(ass_res_2["document_path"]).read_text(encoding="utf-8")
    (snapshots_dir / "acte2_document.md").write_text(doc_text_2, encoding="utf-8")

    report_sections.append(f"""
## 🔵 Acte 2 — Cadrage L0 -> L1 & Énoncés Validés

### 📄 Fiche Proposal générée par le Proposal Renderer (`proposal.md.j2`) :
```markdown
{rendered_prop_card}
```

### 📑 Document d'Architecture généré par le Renderer d'Assemblage (Acte 2) :
```markdown
{doc_text_2}
```
""")

    # --------------------------------------------------------------------------
    # ACTE 3 : Décomposition L1 -> L2 & Maturity Board Renderer
    # --------------------------------------------------------------------------
    repo.advance_subject_level("mcx-services", "L2_decomposed")
    repo.close()
    del repo
    gc.collect()

    repo = ElicitationRepository(db_path=db_path)

    sub_list = ["group-management", "floor-control", "media-distribution", "lmr-interworking"]
    for sub in sub_list:
        repo.save_subject(sub)

    board_data_3 = repo.get_subjects_maturity_board(engagement=engagement)
    rendered_board_3 = render_maturity_board(engagement=engagement, board_data=board_data_3)
    (snapshots_dir / "acte3_maturity_board.md").write_text(rendered_board_3, encoding="utf-8")

    report_sections.append(f"""
## 🟣 Acte 3 — Décomposition L1 -> L2 & 4 Sujets Créés

### 📌 Maturity Board généré par le Maturity Board Renderer (`maturity_board.md.j2`) :
```markdown
{rendered_board_3}
```
""")

    # --------------------------------------------------------------------------
    # ACTE 5 : Contestation (Rui) & Conflict Card Renderer
    # --------------------------------------------------------------------------
    s34 = StatementData(
        id="S-0034",
        subject="floor-control",
        predicate="has_property",
        value="arbitration terminates in the MC service layer, at the site",
        author="Amina Duarte",
        role="mcx-service-architect",
        confidence="designed",
    )
    s_34_id = repo.save_statement({
        "engagement": engagement,
        "section": "4.3",
        "subject": s34.subject,
        "predicate": s34.predicate,
        "value": s34.value,
        "author": s34.author,
        "role": s34.role,
        "confidence": s34.confidence,
        "status": "active"
    })
    repo.advance_subject_level("floor-control", "L3_decided")

    s_41_id, conflict_id = repo.contest_statement(
        target_statement_id=s_34_id,
        author="Rui Vasconcelos",
        role="mobile-core-architect",
        text="depends on a committed priority and pre-emption profile in the core",
        engagement=engagement
    )

    s41 = StatementData(
        id=s_41_id,
        subject="floor-control",
        predicate="depends_on",
        value="depends on a committed priority and pre-emption profile in the core",
        author="Rui Vasconcelos",
        role="mobile-core-architect",
        confidence="designed",
    )


    # Sollicitation du Conflict Card Renderer
    conf_card_data = ConflictCardData(
        conflict_id=conflict_id,
        engagement=engagement,
        kind="contradiction",
        detail="Tension inter-prédicats décelée sur floor-control (has_property vs depends_on).",
        subject="floor-control",
        predicate="has_property / depends_on",
        statements=[s34, s41],
        advisory="Les deux positions ne sont pas exclusives. L'arbitrage est local, le profil d'admission est cœur."
    )
    rendered_conf_card = render_conflict_card(conf_card_data)
    (snapshots_dir / "acte5_conflict_card.md").write_text(rendered_conf_card, encoding="utf-8")

    report_sections.append(f"""
## 🟠 Acte 5 — Contestation & Déclenchement de Conflit Inter-Prédicats

### ⚠️ Fiche Conflit générée par le Conflict Renderer (`conflict.md.j2`) :
```markdown
{rendered_conf_card}
```
""")

    # --------------------------------------------------------------------------
    # ACTE 6 : Arbitrage Multi-Action & Arbitration Card Renderer
    # --------------------------------------------------------------------------
    amended_text = "floor arbitration terminates in the MC service layer at the site"
    repo.arbitrate_conflict(
        conflict_id=conflict_id,
        keep_statement_id=s_41_id,
        reason="Les deux sont valides. L'arbitrage est local, mais dépend du profil d'admission cœur.",
        arbitrated_by="Sofia Lindqvist",
        amend_statement_id=s_34_id,
        amend_to=amended_text
    )
    repo.close()
    del repo
    gc.collect()

    repo = ElicitationRepository(db_path=db_path)

    s34_amended = StatementData(
        id=s_34_id,
        subject="floor-control",
        predicate="has_property",
        value=amended_text,
        author="Amina Duarte",
        role="mcx-service-architect",
        confidence="designed",
    )


    # Sollicitation de l'Arbitration Card Renderer
    arb_card_data = ArbitrationCardData(
        conflict_id=conflict_id,
        engagement=engagement,
        kept_statement=s41,
        superseded_statement=s34_amended,
        arbitrated_by="Sofia Lindqvist",
        reason="Les deux sont valides. L'arbitrage est local, mais dépend du profil d'admission cœur."
    )
    rendered_arb_card = render_arbitration_card(arb_card_data)
    (snapshots_dir / "acte6_arbitration_card.md").write_text(rendered_arb_card, encoding="utf-8")

    report_sections.append(f"""
## 🟡 Acte 6 — Arbitrage Multi-Action avec `--amend`

### ✅ Fiche Arbitrage générée par le Arbitration Renderer (`arbitration.md.j2`) :
```markdown
{rendered_arb_card}
```
""")

    # --------------------------------------------------------------------------
    # ACTE 7 : Assemblage Final & Document Renderer
    # --------------------------------------------------------------------------
    ass_res_7 = assemble_graph.invoke({"engagement": engagement, "db_path": str(db_path)})
    doc_text_7 = Path(ass_res_7["document_path"]).read_text(encoding="utf-8")
    (snapshots_dir / "acte7_final_document.md").write_text(doc_text_7, encoding="utf-8")

    board_data_7 = repo.get_subjects_maturity_board(engagement=engagement)
    rendered_board_7 = render_maturity_board(engagement=engagement, board_data=board_data_7)
    (snapshots_dir / "acte7_final_maturity_board.md").write_text(rendered_board_7, encoding="utf-8")

    report_sections.append(f"""
## 📑 Acte 7 — Assemblage du Document d'Architecture Final & Board

### 📑 Document d'Architecture Assemblé par le Système (`document.md`) :
```markdown
{doc_text_7}
```

### 📌 Maturity Board Final généré par le Renderer :
```markdown
{rendered_board_7}
```
""")

    # Écriture du rapport maître d'avancement des renderers
    master_progression_file = Path("projects/nordwave-mcx-2027/renderer_progression.md")
    master_progression_file.write_text("\n".join(report_sections), encoding="utf-8")

    repo.close()
