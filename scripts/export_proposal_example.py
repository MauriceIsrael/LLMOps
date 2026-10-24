"""Rebuild ``schemas/examples/proposal_snapshot.example.json`` (a sealed snapshot of proposals, K7); the freshness test rebuilds it.

    poetry run python scripts/export_proposal_example.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipelines.kb_candidates.proposals import seal  # noqa: E402

EXAMPLE = ROOT / "schemas" / "examples" / "proposal_snapshot.example.json"
CONTENT = """---
id: PAT-NEW
title: Canary before general deployment
type: pattern
phase: [BUILD]
domain: [network-automation]
---

# Canary before general deployment

## Problem
A routing change that is wrong everywhere at once cannot be rolled back in time.

## Solution
Inject the change on one canary node, observe, then widen.

## Trade-offs
Slower roll-out.

## When not to use this
Changes that are atomic by nature.
"""


def build_example() -> dict[str, Any]:
    candidate = {
        "id": "cand-REQ-0007", "suggestedDestination": "knowledge-hub-reference", "candidateKind": "technical-requirement",
        # The suite's `ExtractedCandidate` requires both texts (Requirements Intake, packages/contracts); without them its own
        # schema refuses what an emitter of the suite would send (#157). The Hub reads them as optional.
        "originalText": "Routing changes went out to every node at once.",
        "normalizedText": "Routing changes are rolled out progressively, one node first, never to every node at once.",
        "sourceFragment": {"id": "frag-REQ-0007", "documentId": "lessons-learned-2026", "documentVersion": "1.0",
                           "sectionPath": ["3.2"], "originalText": "Routing changes went out to every node at once.",
                           "hash": "sha256:" + "0" * 64},
        "proposal": {"kind": "new_asset", "asset_type": "pattern", "title": "Canary before general deployment",
                     "rationale": "A routing change went to every node at once and could not be rolled back in time.",
                     "proposed_content": CONTENT, "domain": ["network-automation"], "production_mode": "llm-derived"},
    }
    return seal([candidate], "document-studio", "document-studio-proposals-0001", "2026-10-15T09:00:00Z")


def main() -> None:
    EXAMPLE.parent.mkdir(parents=True, exist_ok=True)
    EXAMPLE.write_text(json.dumps(build_example(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {EXAMPLE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
