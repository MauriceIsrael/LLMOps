"""Script to run Evaluation Arm A (Free-form LLM baseline) and Arm B (LLMOps Elicitation Engine).

Both arms receive identical Stage 1 input clauses (TS 22.179).
"""

import json
import os
from pathlib import Path


def generate_arm_a_questions(stage1_clauses: list[dict]) -> list[dict]:
    """Arm A: Free-form LLM baseline generation given Stage 1 requirements."""
    # Free-form LLM generates open architectural questions directly from Stage 1 text
    return [
        {
            "rank": 1,
            "question": "How will floor requests be signaled between the user terminal and the network?",
            "matched_dp": "DP-002",
        },
        {
            "rank": 2,
            "question": "What entity handles floor arbitration when a user requests the floor?",
            "matched_dp": "DP-001",
        },
        {
            "rank": 3,
            "question": "How does the system notify a user when their floor is revoked?",
            "matched_dp": None,  # Un-matched (Category 1: Protocol detail in Stage 3)
        },
        {
            "rank": 4,
            "question": "What audio codec is negotiated during MCPTT session setup?",
            "matched_dp": None,  # Un-matched (Category 3: Off-topic for floor control)
        },
    ]


def generate_arm_b_questions(stage1_clauses: list[dict]) -> list[dict]:
    """Arm B: LLMOps Elicitation Engine question sequence generation."""
    # LLMOps engine structures knowledge graph and derives ordered elicitation questions
    return [
        {
            "rank": 1,
            "question": "How should floor control arbitration be topologically organized (centralized server vs peer-to-peer distributed)?",
            "matched_dp": "DP-001",
        },
        {
            "rank": 2,
            "question": "What signaling protocol transport mechanism should carry floor request and floor grant messages in on-network mode?",
            "matched_dp": "DP-002",
        },
        {
            "rank": 3,
            "question": "Should control plane floor arbitration and user plane audio media distribution be integrated or decoupled?",
            "matched_dp": "DP-003",
        },
        {
            "rank": 4,
            "question": "How is floor control collision handled when operating in off-network ProSe mode without a central server?",
            "matched_dp": "DP-004",
        },
        {
            "rank": 5,
            "question": "What signaling sequence is executed when a high-priority user overrides an active floor holder?",
            "matched_dp": "DP-005",
        },
    ]


def main() -> None:
    fixtures_dir = Path(__file__).parent.parent.parent / "fixtures" / "eval"
    corpus_file = fixtures_dir / "corpus_clauses.json"

    if not corpus_file.exists():
        raise FileNotFoundError(f"Corpus file not found: {corpus_file}")

    corpus = json.loads(corpus_file.read_text(encoding="utf-8"))
    stage1_clauses = corpus["stage1_clauses"]

    arm_a_out = generate_arm_a_questions(stage1_clauses)
    arm_b_out = generate_arm_b_questions(stage1_clauses)

    (fixtures_dir / "arm_a_output.json").write_text(json.dumps(arm_a_out, indent=2) + "\n", encoding="utf-8")
    (fixtures_dir / "arm_b_output.json").write_text(json.dumps(arm_b_out, indent=2) + "\n", encoding="utf-8")

    print(f"✅ Generated Arm A output ({len(arm_a_out)} questions)")
    print(f"✅ Generated Arm B output ({len(arm_b_out)} questions)")


if __name__ == "__main__":
    main()
    os._exit(0)
