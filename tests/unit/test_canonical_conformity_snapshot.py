"""Tests unitaires pour le calcul canonique et la provenance du ConformitySnapshot."""

import hashlib
import json
from pathlib import Path

from pipelines.compliance_mapper import to_conformity_snapshot


def test_canonical_json_test_vector_hash_matches():
    """Valide que la sérialisation canonique et le checksum SHA-256 correspondent au vecteur de test partagé."""
    vector_path = Path("tests/fixtures/canonical_conformity_vector.json")
    with open(vector_path, encoding="utf-8") as f:
        vector = json.load(f)

    data = vector["data"]
    expected_canonical = vector["canonicalJson"]
    expected_checksum = vector["expectedChecksum"]

    # Profil strict canonical-json (v1): clés triées, séparateurs compacts sans espace, UTF-8
    canonical_str = json.dumps(data, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    assert canonical_str == expected_canonical

    computed_checksum = f"sha256:{hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()}"
    assert computed_checksum == expected_checksum


def test_to_conformity_snapshot_defaults_to_knowledge_hub():
    """Vérifie que la provenance par défaut est 'knowledge-hub' avec identifiant 'kh-'."""
    snapshot = to_conformity_snapshot(engagement="nordwave-mcx-2027", framework="ISO27001")

    assert snapshot["sourceSystem"] == "knowledge-hub"
    assert snapshot["snapshotId"].startswith("kh-nordwave-mcx-2027-iso27001-")
    assert snapshot["schemaVersion"] == "2.0"
    assert snapshot["checksum"].startswith("sha256:")

    # Vérification que le checksum scelle fidèlement le bloc data
    canonical_str = json.dumps(snapshot["data"], separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    expected_hash = f"sha256:{hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()}"
    assert snapshot["checksum"] == expected_hash


def test_to_conformity_snapshot_backward_compat_tuleap():
    """Vérifie que le Hub peut émettre 'tuleap' si expressément demandé pour rétrocompatibilité."""
    snapshot = to_conformity_snapshot(engagement="nordwave-mcx-2027", framework="ISO27001", source_system="tuleap")

    assert snapshot["sourceSystem"] == "tuleap"
    assert snapshot["snapshotId"].startswith("tuleap-kh-nordwave-mcx-2027-iso27001-")

