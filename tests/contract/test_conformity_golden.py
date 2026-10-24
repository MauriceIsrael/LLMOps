"""Témoin du canal « conformité » du Hub (#151) : l'émetteur le **reconstruit**, il ne se contente pas de le lire.

Même idiome que le registre de canaux de la suite (``witness.rebuiltByEmitterTest``) : un émetteur qui change sans régénérer
fait tomber sa propre suite. Le témoin est construit sur deux contrôles figés (``tests/fixtures/suite/controls``), pas sur la
base vivante : il ne bouge que si le code d'émission bouge. Le Document Engine le relit avec ``make verify-suite``.

Régénérer : ``CONFORMITY_WRITE_GOLDEN=1 poetry run pytest tests/contract/test_conformity_golden.py``
"""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from pipelines import canonical
from pipelines.compliance_mapper import to_conformity_snapshot

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests" / "fixtures" / "suite" / "conformity-snapshot.golden.json"
CONTROLS = ROOT / "tests" / "fixtures" / "suite" / "controls"
FIXED_NOW = datetime(2026, 10, 1, 12, 0, 0, tzinfo=UTC)


def _rebuild() -> str:
    envelope = to_conformity_snapshot(engagement="golden-engagement", framework="NIS2", controls_dir=CONTROLS, now=FIXED_NOW)
    return json.dumps(envelope, indent=2, ensure_ascii=False) + "\n"


def test_the_golden_is_what_the_emitter_rebuilds():
    rebuilt = _rebuild()
    if os.environ.get("CONFORMITY_WRITE_GOLDEN") == "1":
        GOLDEN.write_text(rebuilt, encoding="utf-8", newline="\n")
    assert GOLDEN.read_text(encoding="utf-8").replace("\r\n", "\n") == rebuilt, (
        "le témoin est périmé par rapport à l'émetteur : CONFORMITY_WRITE_GOLDEN=1 poetry run pytest "
        "tests/contract/test_conformity_golden.py, puis recopier le témoin chez ses lecteurs"
    )


def test_the_golden_seal_is_the_canonical_checksum_of_its_data():
    envelope = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert envelope["checksum"] == canonical.sha256(envelope["data"])
    assert envelope["snapshotId"].endswith(envelope["checksum"][len("sha256:"):][:12])
    assert envelope["sourceSystem"] == "knowledge-hub"
    assert {r["status"] for r in envelope["data"]["requirements"]} == {"allocated", "identified"}
