"""Script to index 3GPP MCPTT specification clauses for the evaluation corpus.

Per Rule 0.3 #4: Stores stable references, versions, release tags, and clause IDs only.
Does NOT store raw full specification text in the repository.
"""

import json
import os
from pathlib import Path
from typing import Any

# Primary Functional Perimeter: MCPTT Floor Control
PERIMETER_TOPIC = "floor_control"

# Target Specifications Index
TARGET_SPECS = [
    {
        "doc_id": "TS 22.179",
        "stage": 1,
        "title": "Mission Critical Push To Talk (MCPTT) over LTE; Service requirements",
        "releases": ["Rel-13", "Rel-14", "Rel-15", "Rel-16", "Rel-17"],
        "primary_clauses": ["5.3", "5.4", "6.2", "6.3", "7.2", "7.3"],
    },
    {
        "doc_id": "TS 23.179",
        "stage": 2,
        "title": "Functional architecture and information flows to support MCPTT; Stage 2 (Rel-13)",
        "releases": ["Rel-13"],
        "primary_clauses": ["7.2", "7.3", "7.4", "10.9", "10.10"],
    },
    {
        "doc_id": "TS 23.280",
        "stage": 2,
        "title": "Common functional architecture for mission critical services; Stage 2 (Rel-14+)",
        "releases": ["Rel-14", "Rel-15", "Rel-16", "Rel-17"],
        "primary_clauses": ["6.2", "7.2", "7.3", "9.2"],
    },
    {
        "doc_id": "TS 23.379",
        "stage": 2,
        "title": "Mission Critical Push To Talk (MCPTT) media plane control; Stage 2 (Rel-14+)",
        "releases": ["Rel-14", "Rel-15", "Rel-16", "Rel-17"],
        "primary_clauses": ["6.3", "7.3", "7.4", "10.1", "10.2", "10.3"],
    },
]


def build_corpus_index() -> dict[str, Any]:
    """Generates the clause reference table for the evaluation benchmark."""
    stage1_clauses = []
    stage2_clauses = []

    # Stage 1 Requirements Indexing (TS 22.179)
    s1_items = [
        {
            "clause_id": "TS 22.179 # 6.2.1",
            "spec": "TS 22.179",
            "stage": 1,
            "release": "Rel-13",
            "title": "Floor Control Requests & Queuing",
            "topic": "floor_control",
            "requirement_summary": "The MCPTT system shall support floor request, floor grant, floor override, and floor release under active call state.",
        },
        {
            "clause_id": "TS 22.179 # 6.2.2",
            "spec": "TS 22.179",
            "stage": 1,
            "release": "Rel-13",
            "title": "Floor Override & Preemption",
            "topic": "floor_control",
            "requirement_summary": "The MCPTT system shall support pre-emptive floor control based on user priority level and emergency state.",
        },
        {
            "clause_id": "TS 22.179 # 6.2.3",
            "spec": "TS 22.179",
            "stage": 1,
            "release": "Rel-13",
            "title": "Floor Control Audio Cut-in & Warning",
            "topic": "floor_control",
            "requirement_summary": "The system shall notify the current floor holder when floor is revoked or overridden.",
        },
        {
            "clause_id": "TS 22.179 # 6.3.1",
            "spec": "TS 22.179",
            "stage": 1,
            "release": "Rel-13",
            "title": "Off-Network Floor Control",
            "topic": "floor_control",
            "requirement_summary": "The MCPTT system shall support floor control mechanisms when operating in off-network (ProSe) mode.",
        },
        {
            "clause_id": "TS 22.179 # 7.2.1",
            "spec": "TS 22.179",
            "stage": 1,
            "release": "Rel-14",
            "title": "Dual-Floor / Multi-Talker Control",
            "topic": "floor_control",
            "requirement_summary": "The MCPTT system shall support multi-speaker audio mixing or dual-floor allocation for supervisor override.",
        },
    ]
    stage1_clauses.extend(s1_items)

    # Stage 2 Architectural Decisions Indexing (TS 23.179 / TS 23.280 / TS 23.379)
    s2_items = [
        {
            "clause_id": "TS 23.179 # 7.3.1",
            "spec": "TS 23.179",
            "stage": 2,
            "release": "Rel-13",
            "title": "Floor Control Server Centralized Topology",
            "topic": "floor_control",
            "decision_summary": "Floor control arbitration is centralized at the MCPTT Floor Control Server (Floor Control Host).",
        },
        {
            "clause_id": "TS 23.179 # 10.9.2",
            "spec": "TS 23.179",
            "stage": 2,
            "release": "Rel-13",
            "title": "Floor Request Procedure over Unicast Signaling",
            "topic": "floor_control",
            "decision_summary": "Floor requests use SIP/RTP/RTCP control messages over unicast bearer between UE and Floor Control Server.",
        },
        {
            "clause_id": "TS 23.379 # 7.4.1",
            "spec": "TS 23.379",
            "stage": 2,
            "release": "Rel-14",
            "title": "Split Architecture: Floor Control Server vs Media Distribution Function",
            "topic": "floor_control",
            "decision_summary": "Decouple control plane floor arbitration (Floor Control Server) from user plane media distribution (MDF).",
        },
        {
            "clause_id": "TS 23.379 # 10.2.1",
            "spec": "TS 23.379",
            "stage": 2,
            "release": "Rel-14",
            "title": "Off-Network Floor Control Distributed Token Protocol",
            "topic": "floor_control",
            "decision_summary": "Off-network ProSe floor control utilizes distributed peer-to-peer token passing with timer-based collision recovery.",
        },
        {
            "clause_id": "TS 23.379 # 10.3.2",
            "spec": "TS 23.379",
            "stage": 2,
            "release": "Rel-15",
            "title": "Floor Override Audio Preemption Protocol",
            "topic": "floor_control",
            "decision_summary": "Floor revoking sends Floor Granted to pre-emptor while sending Floor Revoked with reason code to incumbent speaker.",
        },
    ]
    stage2_clauses.extend(s2_items)

    return {
        "perimeter": PERIMETER_TOPIC,
        "specifications": TARGET_SPECS,
        "stage1_count": len(stage1_clauses),
        "stage2_count": len(stage2_clauses),
        "stage1_clauses": stage1_clauses,
        "stage2_clauses": stage2_clauses,
    }


def main() -> None:
    output_dir = Path(__file__).parent.parent.parent / "fixtures" / "eval"
    output_dir.mkdir(parents=True, exist_ok=True)

    index_data = build_corpus_index()
    target_file = output_dir / "corpus_clauses.json"
    target_file.write_text(json.dumps(index_data, indent=2) + "\n", encoding="utf-8")
    print(f"✅ Generated 3GPP evaluation corpus index at: {target_file}")
    print(f"   Stage 1 Clauses: {index_data['stage1_count']}")
    print(f"   Stage 2 Decision Points: {index_data['stage2_count']}")


if __name__ == "__main__":
    main()
    os._exit(0)
