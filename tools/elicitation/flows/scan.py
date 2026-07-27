"""Flux A : Scan déterministe des manques (Gaps) et émission des questions."""

from typing import Any

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from mcp_server.db.kuzu_client import KuzuClient
from tools.elicitation.mailbox import FileMailbox, QuestionMessage
from tools.elicitation.repository import ElicitationRepository


def _esc(val: Any) -> str:
    return str(val or "").replace("'", "\\'")


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
    db_path = state.get("db_path", "data/kuzu_db")
    sections = state.get("sections") or [
        {"id": "4.1", "name": "MCX Services Boundary & Framing", "subject": "mcx-services", "required_level": "L0_named"},
        {"id": "4.2", "name": "Floor Control Latency Budget", "subject": "floor-control", "required_level": "L0_named"},
        {"id": "4.3", "name": "Floor Control Arbitration", "subject": "floor-control", "required_level": "L3_decided"},
        {"id": "4.4", "name": "Media Distribution Topology", "subject": "media-distribution", "required_level": "L0_named"},
        {"id": "4.5", "name": "LMR Interworking Gateway", "subject": "lmr-interworking", "required_level": "L0_named"},
        {"id": "4.6", "name": "Group Management Domain & Affiliation", "subject": "group-management", "required_level": "L0_named"},
        {"id": "5.1", "name": "Mobile Core Framing & Topology", "subject": "mobile-core", "required_level": "L0_named"},
        {"id": "5.3", "name": "Mobile Core QoS & Pre-emption Profile", "subject": "mobile-core", "required_level": "L3_decided"},
        {"id": "5.4", "name": "Transport Topology & Redundancy", "subject": "transport", "required_level": "L0_named"},
    ]
    return {"sections": sections, "engagement": engagement, "db_path": db_path}


def detect_gaps_node(state: ScanState) -> dict[str, Any]:
    """Détecte de manière 100% déterministe les manques basés sur les sujets réellement nés dans le graphe."""
    db_path = state.get("db_path", "data/kuzu_db")
    db_client = KuzuClient(db_path=db_path, read_only=False)
    engagement = state.get("engagement", "demo-2026")
    repo = ElicitationRepository(db_path=db_path)
    gaps: list[dict[str, Any]] = []

    # S'assurer que les sujets racines existent au premier scan
    board_subjects = repo.get_subjects_maturity_board(engagement)
    if not board_subjects:
        repo.save_subject("mcx-services")
        repo.save_subject("mobile-core")
        repo.save_subject("transport")
        board_subjects = repo.get_subjects_maturity_board(engagement)

    active_subjects = {b["subject"] for b in board_subjects}

    # Vérifier l'état de maturité des sujets principaux
    mcx_mat = repo.get_subject_maturity("mcx-services")
    mcx_lvl = mcx_mat.get("level", "L0_named")

    # Si mcx-services est à L1_framed, proposer la décomposition L2
    if mcx_lvl == "L1_framed":
        gaps.append({
            "gap_type": "G1_empty_section",
            "section": "4.1",
            "section_name": "MCX Services Decomposition",
            "subject": "mcx-services",
            "required_level": "L1_framed",
            "target_level": "L2_decomposed",
            "blocking_count": 4,
            "blocking": ["4.2", "4.4", "4.5", "4.6"],
        })

    # Parcourir les sections configurées SEULEMENT pour les sujets qui existent dans la base
    for sec in state.get("sections", []):
        sec_id = sec["id"]
        sec_sub = sec.get("subject", "mcx-services")

        if sec_sub not in active_subjects:
            continue

        subj_mat = repo.get_subject_maturity(sec_sub)
        subj_lvl = subj_mat.get("level", "L0_named")
        req_lvl = sec.get("required_level", "L0_named")

        # Règle : Une section exigeant L2+ n'est scannée que si le sujet est au moins à L1_framed
        if req_lvl in ("L2_decomposed", "L3_decided", "L4_specified") and subj_lvl == "L0_named" and sec_sub not in ("mcx-services", "mobile-core", "transport"):
            continue

        q = f"MATCH (s:Statement {{engagement: '{engagement}', section: '{sec_id}', status: 'active'}}) RETURN count(s) as c;"
        res = db_client.execute_cypher(q)
        count = res[0].get("c", 0) if res and "error" not in res[0] else 0

        if count == 0 and not (sec_id == "4.1" and mcx_lvl != "L0_named"):
            gaps.append({
                "gap_type": "G1_empty_section",
                "section": sec_id,
                "section_name": sec["name"],
                "subject": sec_sub,
                "required_level": req_lvl,
                "blocking_count": 3 if sec_id.startswith("4.") else (2 if "5." in sec_id else 1),
                "blocking": [f"{sec_id}.1", f"{sec_id}.2"],
            })

    # Manques granulaires prématurés : uniquement pour les sujets DÉJÀ NÉS dans le graphe Kùzu DB
    all_premature_specs = [
        ("4.1.1", "mcx-services", "MCX service boundary framing", "L1_framed"),
        ("4.1.2", "mcx-services", "MCX sub-components taxonomy", "L2_decomposed"),
        ("4.1.7", "mcx-services", "MCX inter-service interface contracts", "L2_decomposed"),
        ("4.1.8", "mcx-services", "MCX service deployment boundaries", "L2_decomposed"),
        ("4.1.3", "mcx-services", "MCX local site survival mechanism", "L3_decided"),
        ("4.1.4", "mcx-services", "MCX talkgroup capacity limits", "L4_specified"),
        ("4.1.5", "mcx-services", "MCX dispatcher console protocol", "L3_decided"),
        ("4.1.6", "mcx-services", "MCX encryption key profile", "L4_specified"),

        ("4.2.1", "floor-control", "Floor Control PTT latency SLA", "L2_decomposed"),
        ("4.2.2", "floor-control", "Floor Control packet drop behavior", "L2_decomposed"),
        ("4.3.1", "floor-control", "Floor Control arbitration queue size", "L3_decided"),
        ("4.3.2", "floor-control", "Floor Control pre-emption override policy", "L3_decided"),

        ("4.4.1", "media-distribution", "Multicast stream synchronization", "L2_decomposed"),
        ("4.4.2", "media-distribution", "Unicast fallback trigger threshold", "L2_decomposed"),

        ("4.5.1", "lmr-interworking", "Analog gateway transcoding latency", "L2_decomposed"),
        ("4.5.2", "lmr-interworking", "LMR signaling mapping matrix", "L3_decided"),

        ("4.6.1", "group-management", "Group membership sync protocol", "L2_decomposed"),
        ("4.6.2", "group-management", "Affiliation state caching TTL", "L3_decided"),

        ("5.1.1", "mobile-core", "5G Standalone core topology", "L1_framed"),
        ("5.1.2", "mobile-core", "UPF placement strategy", "L2_decomposed"),
        ("5.3.1", "mobile-core", "5QI allocation for MC voice", "L3_decided"),
        ("5.3.2", "mobile-core", "ARP priority level mapping", "L3_decided"),
        ("5.3.3", "mobile-core", "Pre-emption vulnerability setting", "L4_specified"),
        ("5.3.4", "mobile-core", "Network slicing isolation policy", "L3_decided"),
        ("5.3.5", "mobile-core", "Dual-site active-active core sync", "L3_decided"),

        ("5.4.1", "transport", "Backhaul redundancy framing", "L1_framed"),
        ("5.4.2", "transport", "Physical link separation", "L2_decomposed"),
        ("5.5.1", "transport", "Backhaul failover convergence time", "L2_decomposed"),
        ("5.5.2", "transport", "IPSec tunnel throughput limit", "L3_decided"),
        ("5.5.3", "transport", "Site isolation local breakout route", "L3_decided"),
        ("5.5.4", "transport", "Dark fiber path latency SLA", "L3_decided"),
        ("5.5.5", "transport", "MPLS TE tunnel QoS policy", "L4_specified"),

        ("6.1.1", "telco-interconn", "SGi-LAN firewall throughput", "L2_decomposed"),
        ("6.1.2", "telco-interconn", "eNodeB/gNodeB SCTP multihoming", "L3_decided"),
    ]

    for sec_id, subj, name, req_lvl in all_premature_specs:
        if subj in active_subjects:
            gaps.append({
                "gap_type": "G3_unspecified_parameter",
                "section": sec_id,
                "section_name": name,
                "subject": subj,
                "required_level": req_lvl,
                "blocking_count": 1,
                "blocking": [],
            })

    return {"gaps": gaps}


def enrich_node(state: ScanState) -> dict[str, Any]:
    """Enrichit les manques avec la maturité du sujet, retient les manques prématurés et propose des patterns."""
    db_path = state.get("db_path", "data/kuzu_db")
    repo = ElicitationRepository(db_path=db_path)
    enriched_gaps = []

    from tools.elicitation.config import SUBJECT_LEVELS

    for gap in state.get("gaps", []):
        sub_name = gap["subject"]
        sub_info = repo.get_subject_maturity(sub_name)
        gap["subject_level"] = sub_info["level"]

        required_level = gap.get("required_level", "L0_named")
        req_idx = SUBJECT_LEVELS.index(required_level) if required_level in SUBJECT_LEVELS else 0
        cur_idx = SUBJECT_LEVELS.index(sub_info["level"]) if sub_info["level"] in SUBJECT_LEVELS else 0

        # Level Gating : Si le niveau requis est supérieur au niveau actuel du sujet, retenir
        if req_idx > cur_idx:
            gap["held_premature"] = True
            gap["held_reason"] = f"subject {sub_name} is at {sub_info['level']}, needs {required_level}"
            enriched_gaps.append(gap)
            continue

        # Proposition de patterns pour la décomposition
        if gap.get("target_level") == "L2_decomposed" or sub_info["level"] == "L2_decomposed":
            gap["candidate_patterns"] = [
                {
                    "id": "PAT-006",
                    "name": "PAT-006 Vendor boundary through northbound interface",
                    "when_not_to_use": "Ne pas utiliser si le fournisseur supporte un accès direct modèle.",
                }
            ]

        # Chercher une réponse antérieure sur un autre engagement (défaut à confirmer)
        prior_query = f"""
        MATCH (st:Statement {{status: 'active'}})
        WHERE st.subject = '{_esc(sub_name)}' AND st.engagement <> '{_esc(state.get('engagement', 'demo-2026'))}'
        RETURN st.value as value, st.author as author, st.predicate as predicate, st.confidence as confidence;
        """
        prior_rows = repo.db_client.execute_cypher(prior_query)
        if prior_rows and "error" not in prior_rows[0]:
            gap["prior_answer"] = prior_rows[0]

        # Liens de contexte permanents
        gap["draft_ref"] = f"file:///projects/{state.get('engagement', 'demo-2026')}/draft#section-{gap['section']}"
        gap["subject_ref"] = f"file:///projects/{state.get('engagement', 'demo-2026')}/history#{sub_name}"

        enriched_gaps.append(gap)

    return {"enriched_gaps": enriched_gaps}


def crystallize_node(state: ScanState) -> dict[str, Any]:
    """Formule une question précise pour chaque manque mûr."""
    max_q = state.get("max_questions", 8)
    mur_gaps = [g for g in state.get("enriched_gaps", []) if not g.get("held_premature")]
    gaps = sorted(
        mur_gaps,
        key=lambda x: x.get("blocking_count", 0),
        reverse=True,
    )[:max_q]

    questions = []
    idx = 1
    for gap in gaps:
        q_id = f"Q-{idx:04d}"
        idx += 1
        sec = gap["section"]
        sub = gap["subject"]

        if gap.get("target_level") == "L2_decomposed":
            q_text = f"Comment se décompose l'architecture de {sub} (Section {sec}) ?"
            why = f"Le sujet {sub} a atteint L1_framed et doit être décomposé en sous-domaines."
            routed = "mcx-service-architect"
            shape = "decomposition"
            q_level = "L2_decomposed"
        else:
            q_text = f"Quelle est l'architecture de la section {sec} ({gap['section_name']}) ?"
            why = f"La section {sec} ({gap['section_name']}) ne contient aucun énoncé d'architecture."
            routed = "mcx-service-architect" if "4." in sec else ("mobile-core-architect" if "5." in sec else "cloud-architect")
            shape = "decision"
            q_level = "L1_framing"

        candidate_patterns = gap.get("candidate_patterns")
        if candidate_patterns:
            p_str = ", ".join(p["name"] for p in candidate_patterns)
            w_str = ", ".join(p.get("when_not_to_use", "") for p in candidate_patterns)
            q_text += f"\nPattern proposé : {p_str} (Quand ne pas utiliser : {w_str})"

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
                "level": q_level,
                "blocking": gap.get("blocking", []),
                "candidate_patterns": candidate_patterns,
                "draft_ref": gap.get("draft_ref"),
                "subject_ref": gap.get("subject_ref"),
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
