"""Témoin du canal « conformité » du Hub (#151, #148, #150) : l'émetteur le **reconstruit**, il ne se contente pas de le lire.

Même idiome que le registre de canaux de la suite (``witness.rebuiltByEmitterTest``) : un émetteur qui change sans régénérer
fait tomber sa propre suite. Le témoin est construit sur une donnée d'engagement figée (``engagement_data``) dérivée de la
section ``compliance`` (majeure 4.0, ``RequirementRef`` complète sur chaque exigence, jamais ``EXPLICIT_KB_ALIGNMENTS``). Le
Document Engine le relit avec ``make verify-suite``.

Régénérer : ``CONFORMITY_WRITE_GOLDEN=1 pytest tests/contract/test_conformity_golden.py``
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from pipelines import canonical
from pipelines.compliance_mapper import to_conformity_snapshot

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests" / "fixtures" / "suite" / "conformity-snapshot.golden.json"
FIXED_NOW = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)

GOLDEN_ENGAGEMENT_DATA = {
    "requirements": [
        {
            "id": "REQ-NIS2-01",
            "text": "Network segmentation and access control shall isolate critical control plane traffic.",
            "category": "network",
            "ref": {"sourceId": "tuleap:golden", "requirementKey": "GOLD-NET-001", "version": 2},
        },
        {
            "id": "REQ-NIS2-02",
            "text": "Governance policy shall assign cybersecurity accountability.",
            "category": "governance",
            "ref": {"sourceId": "knowledge-hub:golden-engagement", "requirementKey": "REQ-NIS2-02", "version": 1},
        },
    ],
    "compliance": {
        "items": [
            {
                "requirement_id": "REQ-NIS2-01",
                "control_id": "NIS2-ART21-2A",
                "framework": "NIS2",
                "severity": "mandatory",
                "status": "allocated",
                "decisions": ["D-0001"],
                "assets": ["PAT-006"],
            },
            {
                "requirement_id": "REQ-NIS2-02",
                "control_id": "NIS2-ART20-1",
                "framework": "NIS2",
                "severity": "mandatory",
                "status": "proposed",
                "decisions": ["D-0002"],
                "assets": [],
            },
        ],
    },
}


def _rebuild() -> str:
    envelope = to_conformity_snapshot(
        engagement="golden-engagement",
        framework="NIS2",
        now=FIXED_NOW,
        engagement_data=GOLDEN_ENGAGEMENT_DATA,
    )
    return json.dumps(envelope, indent=2, ensure_ascii=False) + "\n"


def test_the_golden_is_what_the_emitter_rebuilds():
    rebuilt = _rebuild()
    if os.environ.get("CONFORMITY_WRITE_GOLDEN") == "1":
        GOLDEN.write_text(rebuilt, encoding="utf-8", newline="\n")
    assert GOLDEN.read_text(encoding="utf-8").replace("\r\n", "\n") == rebuilt, (
        "le témoin est périmé par rapport à l'émetteur : CONFORMITY_WRITE_GOLDEN=1 pytest "
        "tests/contract/test_conformity_golden.py, puis recopier le témoin chez ses lecteurs"
    )


def test_the_golden_seal_is_the_canonical_checksum_of_its_data():
    envelope = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert envelope["schemaVersion"] == "4.0"
    assert envelope["checksum"] == canonical.sha256(envelope["data"])
    assert envelope["snapshotId"].endswith(envelope["checksum"][len("sha256:"):][:12])
    assert envelope["sourceSystem"] == "knowledge-hub"
    assert {r["status"] for r in envelope["data"]["requirements"]} == {"allocated", "identified"}
    for req in envelope["data"]["requirements"]:
        assert set(req["ref"].keys()) == {"sourceId", "requirementKey", "version"}
        assert isinstance(req["ref"]["version"], int) and req["ref"]["version"] >= 1
