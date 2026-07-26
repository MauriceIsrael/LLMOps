"""Test d'intégration automatisé du scénario d'élicitation collaboratif avec 3 acteurs fictifs (Alice, Bob, Charlie)."""

import pytest
from pathlib import Path

from tools.elicitation.repository import ElicitationRepository
from tools.elicitation.flows.scan import build_scan_graph
from tools.elicitation.flows.intake import build_intake_graph, get_sqlite_checkpointer
from tools.elicitation.flows.assemble import build_assemble_graph
from langgraph.types import Command


def test_end_to_end_3_architects_scenario(tmp_path):
    """Déroule le scénario complet entre Alice (cloud-architect), Bob (storage-expert) et Charlie (chief-architect)."""
    db_path = tmp_path / "kuzu_db"
    engagement = "test-3-arch"
    repo = ElicitationRepository(db_path=db_path)

    # 1. SCAN : Détection des manques
    scan_graph = build_scan_graph()
    scan_res = scan_graph.invoke({"engagement": engagement, "db_path": str(db_path)})
    questions = scan_res.get("questions", [])
    assert len(questions) > 0
    q_id = questions[0]["id"]

    # 2. INTAKE ALICE : Alice propose SAN NVMe
    checkpointer = get_sqlite_checkpointer(engagement=engagement)
    intake_graph = build_intake_graph(checkpointer=checkpointer)
    thread_config = {"configurable": {"thread_id": q_id}}

    intake_graph.invoke(
        {
            "question_id": q_id,
            "answer_text": "SAN NVMe dual-controller",
            "author": "Alice",
            "role": "cloud-architect",
            "engagement": engagement,
            "db_path": str(db_path),
        },
        config=thread_config,
    )

    # 3. CONFIRM ALICE : Reprise d'interruption dans un nouveau processus
    confirm_res = intake_graph.invoke(Command(resume={"action": "accept", "accept": True}), config=thread_config)
    s_alice_ids = confirm_res.get("persisted_statement_ids", [])
    assert len(s_alice_ids) > 0
    s_alice_id = s_alice_ids[0]

    # 4. INTAKE BOB : Bob propose Ceph HCI (contradiction)
    q_id_bob = f"{q_id}-bob"
    thread_config_bob = {"configurable": {"thread_id": q_id_bob}}
    intake_graph.invoke(
        {
            "question_id": q_id,
            "answer_text": "Ceph HCI all-flash SSD",
            "author": "Bob",
            "role": "storage-expert",
            "engagement": engagement,
            "db_path": str(db_path),
        },
        config=thread_config_bob,
    )

    # 5. CONFIRM BOB : Détection du conflit C-0001
    confirm_bob_res = intake_graph.invoke(Command(resume={"action": "accept", "accept": True}), config=thread_config_bob)
    conflicts = confirm_bob_res.get("created_conflict_ids", [])
    assert len(conflicts) > 0
    conflict_id = conflicts[0]

    # 6. ASSEMBLE 1 : Le document est PROVISIONAL car un conflit est ouvert
    assemble_graph = build_assemble_graph()
    ass_res_1 = assemble_graph.invoke({"engagement": engagement, "db_path": str(db_path)})
    assert ass_res_1["is_provisional"] is True

    # 7. ARBITRATE CHARLIE : Charlie conserve l'énoncé d'Alice
    repo.arbitrate_conflict(
        conflict_id=conflict_id,
        keep_statement_id=s_alice_id,
        reason="Homogénéité du stockage SAN",
        arbitrated_by="Charlie",
    )

    # Avancer la maturité du sujet à L3 pour débloquer la section readiness
    repo.advance_subject_level("Storage-5.2", "L3_decided")
    repo.close()
    del repo
    import gc
    gc.collect()

    # 8. ASSEMBLE 2 : Le document passe en statut COMPLETE !

    ass_res_2 = assemble_graph.invoke({"engagement": engagement, "db_path": str(db_path)})
    assert ass_res_2["is_provisional"] is False
    assert ass_res_2["status"] == "COMPLETE"
