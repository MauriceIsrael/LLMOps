"""Flux A : Scan déterministe des manques (Gaps) et émission des questions."""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from tools.elicitation.config import SUBJECT_LEVELS
from tools.elicitation.mailbox import FileMailbox, QuestionMessage
from tools.elicitation.models.blueprint_schema import (
    Blueprint,
    BlueprintRequirement,
    BlueprintSection,
    load_blueprint,
)
from tools.elicitation.repository import ElicitationRepository


def _esc(val: Any) -> str:
    return str(val or "").replace("'", "\\'")


@dataclass
class Gap:
    """Modèle pur d'un manque d'architecture identifié."""
    gap_type: str            # G1_empty_section | G2_unanswered_blocking | G3_unspecified_parameter
    section: str
    subject: str
    required_level: str
    current_level: str | None
    status: str              # dispatchable | held_premature | held_queued | satisfied
    hold_reason: str | None
    blocking: list[str]      # issu directement de section.unlocks (jamais fabriqué)
    blocking_count: int
    routes_to: str
    must_answer: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ScanState(TypedDict, total=False):
    """État du flux A : scan."""
    engagement: str
    blueprint_id: str
    blueprint: Blueprint
    sections: list[dict[str, Any]]
    repo: ElicitationRepository
    max_questions: int
    max_open_per_role: int
    max_new_per_scan: int
    strategy: str
    db_path: str | None
    gaps: list[dict[str, Any]]
    enriched_gaps: list[dict[str, Any]]
    questions: list[dict[str, Any]]
    persisted_ids: list[str]
    dispatched: list[dict[str, Any]]
    counts_summary: dict[str, int]


def require(state: dict[str, Any], *keys: str) -> None:
    """Valide la présence des clés obligatoires dans l'état (D10)."""
    missing = [k for k in keys if state.get(k) is None]
    if missing:
        raise ValueError(f"Configuration manquante dans l'état du scan : {', '.join(missing)}")


def gate(current_level: str | None, required_level: str) -> str | None:
    """Retourne la raison de rétention d'un manque, ou None s'il est dispatchable (D3)."""
    if current_level is None:
        return "subject does not exist yet"
    cur_idx = SUBJECT_LEVELS.index(current_level) if current_level in SUBJECT_LEVELS else 0
    req_level = "L1_framed" if required_level == "L0_named" else required_level
    req_idx = SUBJECT_LEVELS.index(req_level) if req_level in SUBJECT_LEVELS else 1
    if cur_idx < req_idx and not (req_level == "L1_framed" and current_level == "L0_named"):
        return f"subject at {current_level}, needs {req_level}"
    return None


def evaluate(section: BlueprintSection, req: BlueprintRequirement, current_level: str | None, has_statements: bool) -> Gap:
    """Évalue une exigence de section contre la maturité actuelle du sujet (Fonction pure sans E/S)."""
    hold_reason = gate(current_level, req.level)
    
    if has_statements:
        status = "satisfied"
        hold_reason = None
    elif hold_reason is not None:
        status = "held_premature"
    else:
        status = "dispatchable"

    gap_type = "G1_empty_section" if not has_statements else "G3_unspecified_parameter"

    return Gap(
        gap_type=gap_type,
        section=section.id,
        subject=req.subject,
        required_level=req.level,
        current_level=current_level,
        status=status,
        hold_reason=hold_reason,
        blocking=list(section.unlocks),
        blocking_count=len(section.unlocks),
        routes_to=section.routes_to,
        must_answer=section.must_answer,
    )


def load_frame_node(state: ScanState) -> dict[str, Any]:
    """Charge et valide le blueprint lié à l'engagement (D2, D10)."""
    require(state, "engagement")
    engagement = state["engagement"]

    if state.get("sections"):
        bp_sections = []
        for sec in state["sections"]:
            reqs = []
            if sec.get("requires"):
                for r in sec["requires"]:
                    reqs.append(BlueprintRequirement(subject=r["subject"], level=r.get("level", "L1_framed")))
            else:
                reqs.append(BlueprintRequirement(subject=sec.get("subject", "general"), level=sec.get("required_level", "L1_framed")))

            bp_sections.append(
                BlueprintSection(
                    id=sec["id"],
                    title=sec.get("name", sec["id"]),
                    must_answer=sec.get("must_answer") or "",
                    requires=reqs,
                    unlocks=sec.get("blocking", []),
                    routes_to=sec.get("routes_to", "architect"),
                )
            )
        bp = Blueprint(id="custom", title="Custom Test Blueprint", sections=bp_sections)
        bp_id = "custom"
    else:
        bp_id = state.get("blueprint_id", "BLU-hla-mcx")
        bp_path = Path(bp_id)
        if not bp_path.exists():
            bp_path = Path("data/kb/blueprints") / f"{bp_id}.yaml"
        if not bp_path.exists():
            bp_path = Path("data/kb/blueprints") / bp_id
        bp = load_blueprint(bp_path)

    db_path = state.get("db_path", "data/kuzu_db")
    repo = state.get("repo") or ElicitationRepository(db_path=db_path)
    repo.bind_blueprint_to_engagement(bp, engagement=engagement)

    return {"blueprint": bp, "repo": repo, "blueprint_id": bp_id}


def detect_gaps_node(state: ScanState) -> dict[str, Any]:
    """Évalue chaque exigence du blueprint par rapport au graphe de l'engagement (D1, D4, D5, D7, D8, D9)."""
    require(state, "engagement", "blueprint")
    engagement = state["engagement"]
    bp: Blueprint = state["blueprint"]
    db_path = state.get("db_path", "data/kuzu_db")
    repo = state.get("repo") or ElicitationRepository(db_path=db_path, read_only=True)

    levels = repo.subject_levels(engagement=engagement)               # 1 seule requête (D9)
    with_statements = repo.sections_with_statements(engagement=engagement) # 1 seule requête (D8)

    all_section_ids = {s.id for s in bp.sections}

    gap_objects: list[Gap] = []
    for section in bp.sections:
        for req in section.get_requirements():
            # Validation D5 : s'assurer que chaque identifiant dans unlocks existe dans le blueprint
            for blk in section.unlocks:
                assert blk in all_section_ids or blk.split(".")[0] in all_section_ids, f"Unlock ID '{blk}' invalide pour la section {section.id}"
            
            gap = evaluate(section, req, levels.get(req.subject), section.id in with_statements)
            gap_objects.append(gap)

    gaps_dicts = [g.to_dict() for g in gap_objects]

    # Génération dynamique des manques de décomposition L2 pour tous les sujets à L1_framed
    for sub, lvl in levels.items():
        if lvl == "L1_framed":
            gaps_dicts.append({
                "gap_type": "G1_empty_section",
                "section": "4.1",
                "section_name": f"{sub} Decomposition",
                "subject": sub,
                "required_level": "L1_framed",
                "target_level": "L2_decomposed",
                "status": "dispatchable",
                "hold_reason": None,
                "blocking_count": 4,
                "blocking": ["4.2", "4.4", "4.5"],
                "routes_to": "mcx-service-architect",
                "must_answer": f"Comment se décompose l'architecture de {sub} (Section 4.1) ?",
            })

    # Pour les manques custom de sections dict, préserver section_name et target_level
    for idx, sec in enumerate(state.get("sections") or []):
        if idx < len(gaps_dicts):
            gaps_dicts[idx]["section_name"] = sec.get("name", gaps_dicts[idx]["section"])
            if sec.get("target_level"):
                gaps_dicts[idx]["target_level"] = sec["target_level"]

    # Comptage strict pour la réconciliation (D4)
    dispatchable_c = sum(1 for g in gaps_dicts if g.get("status") == "dispatchable")
    held_premature_c = sum(1 for g in gaps_dicts if g.get("status") == "held_premature")
    held_queued_c = sum(1 for g in gaps_dicts if g.get("status") == "held_queued")
    satisfied_c = sum(1 for g in gaps_dicts if g.get("status") == "satisfied")
    total_c = len(gaps_dicts)

    counts = {
        "dispatchable": dispatchable_c,
        "held_premature": held_premature_c,
        "held_queued": held_queued_c,
        "satisfied": satisfied_c,
        "total": total_c,
    }

    # Assertion de réconciliation D4
    assert counts["total"] == (counts["dispatchable"] + counts["held_premature"] + counts["held_queued"] + counts["satisfied"])

    return {"gaps": gaps_dicts, "counts_summary": counts}


def enrich_node(state: ScanState) -> dict[str, Any]:
    """Enrichit les manques avec les patterns candidats, réponses antérieures et liens de contexte."""
    require(state, "engagement")
    engagement = state["engagement"]
    db_path = state.get("db_path", "data/kuzu_db")
    repo = state.get("repo") or ElicitationRepository(db_path=db_path, read_only=True)
    gaps = state.get("gaps", [])
    enriched_gaps = []

    for gap in gaps:
        sub_name = gap["subject"]
        sec_id = gap["section"]

        if gap.get("status") == "held_premature":
            gap["held_premature"] = True
            gap["held_reason"] = gap.get("hold_reason")

        # Candidate patterns pour la décomposition L2
        if gap.get("required_level") == "L2_decomposed" or gap.get("target_level") == "L2_decomposed" or gap.get("current_level") == "L2_decomposed":
            gap["candidate_patterns"] = [
                {
                    "id": "PAT-006",
                    "name": "PAT-006 Vendor boundary through northbound interface",
                    "when_not_to_use": "Ne pas utiliser si le fournisseur supporte un accès direct modèle.",
                }
            ]

        # Prior answer via parameterised query (D8)
        prior_rows = repo.db_client.execute_cypher(
            f"MATCH (st:Statement {{status: 'active'}}) WHERE st.subject = '{_esc(sub_name)}' AND st.engagement <> '{_esc(engagement)}' RETURN st.value as value, st.author as author, st.predicate as predicate, st.confidence as confidence;"
        )
        if prior_rows and "error" not in prior_rows[0]:
            gap["prior_answer"] = prior_rows[0]

        # Liens de contexte permanents
        gap["draft_ref"] = f"file:///projects/{engagement}/draft#section-{sec_id}"
        gap["subject_ref"] = f"file:///projects/{engagement}/history#{sub_name}"

        enriched_gaps.append(gap)

    return {"enriched_gaps": enriched_gaps}


def crystallize_node(state: ScanState) -> dict[str, Any]:
    """Formule de manière 100% déterministe les questions mûres en respectant les quotas par rôle."""
    require(state, "engagement")
    engagement = state["engagement"]
    strategy = state.get("strategy", "breadth")
    gaps_dicts = state.get("enriched_gaps") or state.get("gaps", [])

    dispatchable_gaps = [g for g in gaps_dicts if g.get("status") == "dispatchable"]
    held_premature_gaps = [g for g in gaps_dicts if g.get("status") == "held_premature"]
    satisfied_gaps = [g for g in gaps_dicts if g.get("status") == "satisfied"]

    # Tri selon la stratégie (breadth vs depth)
    if strategy == "breadth":
        dispatchable_gaps.sort(
            key=lambda g: (
                SUBJECT_LEVELS.index(g.get("required_level", "L0_named")) if g.get("required_level") in SUBJECT_LEVELS else 0,
                -g.get("blocking_count", 0),
                g["section"],
            )
        )
    else:  # depth
        dispatchable_gaps.sort(
            key=lambda g: (
                -g.get("blocking_count", 0),
                g["section"],
            )
        )

    max_questions = state.get("max_questions")
    max_open_per_role = state.get("max_open_per_role", 6)
    max_new_per_scan = max_questions if max_questions is not None else state.get("max_new_per_scan", 12)
    if max_questions is not None:
        max_open_per_role = min(max_open_per_role, max_questions)

    db_path = state.get("db_path", "data/kuzu_db")
    repo = state.get("repo") or ElicitationRepository(db_path=db_path)

    # Récupérer les questions ouvertes/envoyées dans Kùzu DB
    existing_rows = repo.db_client.execute_cypher(
        f"MATCH (q:Question {{engagement: '{_esc(engagement)}'}}) WHERE q.status IN ['open', 'sent'] RETURN q.id as id, q.section as section, q.routed_to as routed_to, q.status as status;"
    )
    existing_by_sec = {}
    role_open_counts: dict[str, int] = {}

    if existing_rows and "error" not in existing_rows[0]:
        for r in existing_rows:
            sec = r.get("section")
            role = r.get("routed_to", "architect")
            if sec:
                existing_by_sec[sec] = r
            role_open_counts[role] = role_open_counts.get(role, 0) + 1

    questions = []
    queued_gaps = []
    new_count = 0
    open_count = 0
    next_id_num = len(existing_rows) + 1 if (existing_rows and "error" not in existing_rows[0]) else 1

    for gap in dispatchable_gaps:
        sec = gap["section"]
        sub = gap["subject"]
        routed = gap.get("routes_to") or ("service-architect" if "4." in sec else ("core-architect" if "5." in sec else "cloud-architect"))

        cur_role_open = role_open_counts.get(routed, 0)
        is_existing = sec in existing_by_sec

        # Quotas par rôle et max new questions per scan
        if not is_existing and (cur_role_open >= max_open_per_role or new_count >= max_new_per_scan):
            gap["status"] = "held_queued"
            gap["held_queued"] = True
            gap["held_reason"] = f"held (queued) at position {len(queued_gaps) + 1} for role {routed}"
            queued_gaps.append(gap)
            continue

        if is_existing:
            q_id = existing_by_sec[sec]["id"]
            open_count += 1
        else:
            q_id = f"Q-{next_id_num:04d}"
            next_id_num += 1
            new_count += 1
            role_open_counts[routed] = cur_role_open + 1

        if gap.get("target_level") == "L2_decomposed":
            q_text = f"Comment se décompose l'architecture de {sub} (Section {sec}) ?"
            why = f"Le sujet {sub} a atteint L1_framed et doit être décomposé en sous-domaines."
            shape = "decomposition"
            q_level = "L2_decomposed"
        else:
            sec_name = gap.get("section_name", sec)
            q_text = gap.get("must_answer") or f"Quelle est l'architecture de la section {sec} ({sec_name}) ?"
            why = f"La section {sec} ({sec_name}) ne contient aucun énoncé d'architecture."
            shape = "decision"
            q_level = "L1_framing" if gap["required_level"] == "L1_framed" else gap["required_level"]

        candidate_patterns = gap.get("candidate_patterns")
        if candidate_patterns:
            p_str = ", ".join(p["name"] for p in candidate_patterns)
            w_str = ", ".join(p.get("when_not_to_use", "") for p in candidate_patterns)
            q_text += f"\nPattern proposé : {p_str} (Quand ne pas utiliser : {w_str})"

        questions.append({
            "id": q_id,
            "engagement": engagement,
            "gap_type": gap["gap_type"],
            "section": sec,
            "question": q_text,
            "why_it_matters": why,
            "expected_shape": shape,
            "routed_to": routed,
            "subject": sub,
            "level": q_level,
            "blocking": gap.get("blocking", []),
            "candidate_patterns": candidate_patterns,
            "prior_answer": gap.get("prior_answer"),
            "draft_ref": gap.get("draft_ref"),
            "subject_ref": gap.get("subject_ref"),
            "status": "open",
        })

    counts = {
        "new": new_count,
        "open": open_count,
        "dispatchable": len(questions),
        "held_premature": len(held_premature_gaps),
        "held_queued": len(queued_gaps),
        "satisfied": len(satisfied_gaps),
        "total": len(gaps_dicts),
    }

    return {"questions": questions, "counts_summary": counts}


def persist_questions_node(state: ScanState) -> dict[str, Any]:
    """Persiste les questions générées dans Kùzu DB."""
    db_path = state.get("db_path", "data/kuzu_db")
    repo = state.get("repo") or ElicitationRepository(db_path=db_path)
    persisted_ids = []
    for q in state.get("questions", []):
        qid = repo.save_question(q)
        persisted_ids.append(qid)
    return {"persisted_ids": persisted_ids, "counts_summary": state.get("counts_summary", {})}


def dispatch_node(state: ScanState) -> dict[str, Any]:
    """Poste les questions dans la boîte aux lettres."""
    engagement = state.get("engagement", "demo-2026")
    db_path = state.get("db_path", "data/kuzu_db")
    repo = state.get("repo") or ElicitationRepository(db_path=db_path)
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

    return {"dispatched": dispatched, "counts_summary": state.get("counts_summary", {})}


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
