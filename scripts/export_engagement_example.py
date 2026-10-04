"""Rebuild ``schemas/examples/engagement_snapshot.example.json`` from a fixed scenario (the emitter's own test rebuilds it).

    poetry run python scripts/export_engagement_example.py          # write
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipelines import canonical  # noqa: E402
from pipelines.engagement.snapshot import build_data, seal  # noqa: E402
from pipelines.knowledge_ref import content_sha256, knowledge_ref  # noqa: E402

EXAMPLE = ROOT / "schemas" / "examples" / "engagement_snapshot.example.json"
CREATED_AT = "2026-10-03T12:00:00Z"


def scenario() -> tuple[dict[str, Any], dict[str, Any]]:
    """Raw rows of an illustrative engagement and the knowledge snapshot it is pinned to (a stub: one asset)."""
    adr = "---\nid: ADR-0001\ntitle: Git as the source of truth\n---\n\n# ADR-0001\n"
    vocabulary = {"version": 1, "knowledge_ref": knowledge_ref("vocabulary:facts", 1), "content_sha256": "sha256:" + "0" * 64, "keys": [
        {"key": "topology.dc_count", "type": "int", "min": 1, "unit": "datacentres", "label": {"fr": "Nombre de centres de données", "en": "Number of data centres"}},
        {"key": "topology.mode", "type": "enum", "values": ["single-site", "active-passive", "active-active"],
         "label": {"fr": "Mode multi-site", "en": "Multi-site mode"}}]}
    kb = {
        "fact_vocabulary": vocabulary, "snapshot_id": "snapshot-2026-10-03-0000000", "payload_sha256": "sha256:" + "0" * 64,
        "assets": [{"id": "ADR-0001", "typed_id": "decision:ADR-0001", "revision": 1, "confidence": "verified",
                    "knowledge_ref": knowledge_ref("decision:ADR-0001", 1), "content": adr, "content_sha256": content_sha256(adr),
                    "title": "Git as the source of truth", "type": "decision", "status": "active"}],
    }
    raw = {
        "requirements": [
            {"id": "REQ-001", "text": "The gateway shall survive the loss of one site.", "section": "3.2", "category": "resilience",
             "criticality": "mandatory", "status": "gap"},
            {"id": "REQ-002", "text": "Data at rest shall be encrypted.", "section": "4.1", "category": "security",
             "criticality": "mandatory", "status": "gap"},
        ],
        "subjects": [{"name": "core-network", "definition": "", "level": "L1_framed"},
                     {"name": "mcx-services", "definition": "Mission-critical services", "level": "L3_decided"}],
        "statements": [
            {"id": "S-0001", "subject": "mcx-services", "section": "resilience", "predicate": "has_property",
             "value": "The gateway is active-active across two sites.", "confidence": "designed", "status": "active", "origin": "human",
             "author": "@carl", "validated_by": "@ada", "validated_at": "2026-10-02T09:30:00", "based_on": '[{"id": "ADR-0001", "resolved": null}]'},
            {"id": "S-0002", "subject": "mcx-services", "section": "resilience", "predicate": "has_property",
             "value": "The gateway is active-passive.", "confidence": "assumed", "status": "superseded", "origin": "llm-derived",
             "author": "@carl", "validated_by": "@ada", "validated_at": "2026-10-02T09:31:00", "based_on": "[]"},
            {"id": "S-0003", "subject": "core-network", "section": "general", "predicate": "has_property",
             "value": "A second core site is under study.", "confidence": "stated-by-client", "status": "proposed", "origin": "human",
             "author": "@dan", "validated_by": "", "validated_at": "", "based_on": '[{"id": "UNKNOWN-REF-1", "resolved": null}]',
             "imported_from": "archinex-batch-1"},
        ],
        "decisions": [
            {"id": "D-0001", "subject": "mcx-services", "decision": "Active-active gateway across two sites",
             "rationale": "Meets REQ-001 within the latency budget.", "rejected": [
                 {"option": "Active-passive gateway", "reason": "Failover time above the budget."}],
             "reversibility": "costly", "consequences": ["Two sites to operate."], "accepted_violations": [],
             "based_on": [{"id": "ADR-0001", "resolved": None}], "status": "active", "origin": "human",
             "author": "@carl", "validated_by": "@ada", "validated_at": "2026-10-02T10:00:00", "supersedes": "",
             "facts": [{"key": "topology.dc_count", "value": 2, "source_excerpt": "across two sites"},
                       {"key": "topology.mode", "value": "active-active", "source_excerpt": "Active-active gateway"}]},
            {"id": "D-0002", "subject": "core-network", "decision": "Keep a single core site for the pilot",
             "rationale": "Budget.", "rejected": [], "reversibility": "reversible", "consequences": [],
             "accepted_violations": [{"typed_id": "principle:P-009", "justification": "Pilot only."}],
             "based_on": [], "status": "proposed", "origin": "llm-derived", "author": "@dan", "validated_by": "",
             "validated_at": "", "supersedes": "",
             "facts": [{"key": "topology.dc_count", "value": 1, "source_excerpt": "a single core site"}]},
        ],
        "conflicts": [{"id": "C-0001", "kind": "contradiction", "detail": "Contradiction between S-0001 and S-0002.",
                       "status": "arbitrated", "resolution": "Latency budget", "arbitrated_by": "@ada"}],
        "involves": [{"conflict": "C-0001", "statement": "S-0001"}, {"conflict": "C-0001", "statement": "S-0002"}],
        "questions": [{"id": "Q-0001", "gap_type": "G2_unanswered_blocking", "question": "Which redundancy model for the core?",
                       "status": "open", "subject": "core-network"}],
    }
    return raw, kb


def build_example() -> dict[str, Any]:
    raw, kb = scenario()
    return seal(build_data(raw, "example-eng", "confidential", kb), "example-eng", CREATED_AT, "example")


def main() -> None:
    EXAMPLE.parent.mkdir(parents=True, exist_ok=True)
    EXAMPLE.write_text(json.dumps(build_example(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {EXAMPLE.relative_to(ROOT)} ({canonical.sha256(build_example()['data'])})")


if __name__ == "__main__":
    main()
