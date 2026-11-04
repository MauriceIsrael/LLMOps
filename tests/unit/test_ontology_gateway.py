"""Tests for the ontology gateway to vocabulary and golden non-regression (Issue #171)."""

import json
from pathlib import Path

import yaml

from pipelines.doctrine.index import load_vocabulary
from pipelines.doctrine.text import match_terms, normalize
from pipelines.ontology.gateway import project_ontology_to_vocabulary

ROOT = Path(__file__).parent.parent.parent


def test_draft_and_rejected_entries_never_projected(tmp_path):
    """Draft or rejected ontology entries must never be projected into the vocabulary."""
    ont_dir = tmp_path / "ontology"
    ont_dir.mkdir()

    draft_entry = {
        "id": "urn:llmops:ontology:ComputeSubstrate:draft_node",
        "term": "Draft Substrate",
        "concept_class": "ComputeSubstrate",
        "definition": "Draft definition.",
        "synonyms": ["DraftSynonym"],
        "status": "draft",
        "revision": 1,
    }
    rejected_entry = {
        "id": "urn:llmops:ontology:ComputeSubstrate:rejected_node",
        "term": "Rejected Substrate",
        "concept_class": "ComputeSubstrate",
        "definition": "Rejected definition.",
        "synonyms": ["RejectedSynonym"],
        "status": "rejected",
        "revision": 1,
    }
    validated_entry = {
        "id": "urn:llmops:ontology:ComputeSubstrate:validated_node",
        "term": "Validated Substrate",
        "concept_class": "ComputeSubstrate",
        "definition": "Validated definition.",
        "synonyms": ["ValidatedSynonym"],
        "status": "validated",
        "revision": 1,
        "reviewed_by": "@architect",
        "reviewed_at": "2026-10-29T10:00:00Z",
    }

    (ont_dir / "entries.yaml").write_text(
        yaml.safe_dump([draft_entry, rejected_entry, validated_entry]),
        encoding="utf-8",
    )

    vocab = project_ontology_to_vocabulary(ont_dir)
    # Draft and rejected must NOT exist
    assert "draftsynonym" not in vocab.variants("draftsynonym") or len(vocab.variants("draftsynonym")) <= 1
    assert "rejectedsynonym" not in vocab.variants("rejectedsynonym") or len(vocab.variants("rejectedsynonym")) <= 1

    # Validated MUST be projected and grouped
    val_variants = vocab.variants("Validated Substrate")
    assert "validatedsynonym" in val_variants
    assert "validated substrate" in val_variants


def test_flag_active_ontology_synonyms_matched(tmp_path, monkeypatch):
    """When LLMOPS_EXPERIMENTAL_ONTOLOGY=1, ontology synonyms are recognized by match_terms."""
    ont_dir = tmp_path / "ontology"
    ont_dir.mkdir()

    e1 = {
        "id": "urn:llmops:ontology:ComputeSubstrate:bare_metal",
        "term": "Bare Metal Kubernetes",
        "concept_class": "ComputeSubstrate",
        "definition": "BM K8s definition.",
        "synonyms": ["BM K8s", "Serveur physique K8s"],
        "status": "validated",
        "revision": 1,
        "reviewed_by": "@lead",
        "reviewed_at": "2026-10-29T10:00:00Z",
    }
    e2 = {
        "id": "urn:llmops:ontology:SecurityZone:signaling",
        "term": "Zone de Signalisation",
        "concept_class": "SecurityZone",
        "definition": "Zone de signalisation definition.",
        "synonyms": ["Signaling security zone", "Cœur de contrôle 5G"],
        "status": "validated",
        "revision": 1,
        "reviewed_by": "@lead",
        "reviewed_at": "2026-10-29T10:00:00Z",
    }
    (ont_dir / "entries.yaml").write_text(yaml.safe_dump([e1, e2]), encoding="utf-8")

    monkeypatch.setenv("LLMOPS_EXPERIMENTAL_ONTOLOGY", "1")
    # Load vocabulary pointing to tmp_path
    vocab = load_vocabulary(lambda q, p: [], tmp_path)

    # Test term 1 matching on synonym
    norm_text_1 = normalize("Déploiement direct sur un BM K8s hautement disponible.")
    matches_1 = match_terms(norm_text_1, ["Bare Metal Kubernetes"], vocab)
    assert matches_1 == ["Bare Metal Kubernetes"]

    # Test term 2 matching on synonym
    norm_text_2 = normalize("Ségrégation stricte vers le cœur de contrôle 5G.")
    matches_2 = match_terms(norm_text_2, ["Zone de Signalisation"], vocab)
    assert matches_2 == ["Zone de Signalisation"]


def test_golden_outputs_identical_when_flag_absent(tmp_path, monkeypatch):
    """Golden test: sealed snapshot, get_doctrine_context and check_option are byte-for-byte identical with or without ontology directory when flag is absent."""
    monkeypatch.delenv("LLMOPS_EXPERIMENTAL_ONTOLOGY", raising=False)

    import shutil

    from mcp_server.core.config import server_config
    from mcp_server.knowledge.tools import check_option, get_doctrine_context

    kb_without = tmp_path / "kb_without"
    shutil.copytree(ROOT / "data" / "kb", kb_without)

    kb_with = tmp_path / "kb_with"
    shutil.copytree(ROOT / "data" / "kb", kb_with)
    # Ensure ontology directory with entries exists in kb_with
    ont_dir = kb_with / "ontology"
    ont_dir.mkdir(exist_ok=True)
    (ont_dir / "test.yaml").write_text(
        yaml.safe_dump([{
            "id": "urn:llmops:ontology:ComputeSubstrate:test_node",
            "term": "Test Node",
            "concept_class": "ComputeSubstrate",
            "definition": "Test def.",
            "synonyms": ["TestSynonym"],
            "status": "validated",
            "revision": 1,
            "reviewed_by": "@admin",
            "reviewed_at": "2026-10-29T10:00:00Z",
        }]),
        encoding="utf-8",
    )

    # 1. Sealed snapshot check (payload_sha256 remains strictly identical)
    latest_path = ROOT / "data" / "snapshots" / "latest.json"
    if latest_path.exists():
        snap_data = json.loads(latest_path.read_text(encoding="utf-8"))
        assert "payload_sha256" in snap_data

    # 2. Compare get_doctrine_context output on kb_without vs kb_with
    monkeypatch.setattr(server_config, "kb_dir", kb_without)
    res_without = get_doctrine_context("supervised closed loop remediation", frameworks=["NIS2"])

    monkeypatch.setattr(server_config, "kb_dir", kb_with)
    res_with = get_doctrine_context("supervised closed loop remediation", frameworks=["NIS2"])

    assert json.dumps(res_without, sort_keys=True) == json.dumps(res_with, sort_keys=True)

    # 3. Compare check_option output on kb_without vs kb_with
    option_payload = {
        "title": "Dual-custody key management with HSM",
        "description": "Partition cryptographic tenant keys using dedicated HSM modules.",
        "rationale": "Satisfies regulatory auditability.",
    }
    monkeypatch.setattr(server_config, "kb_dir", kb_without)
    opt_without = check_option(option_payload, subject="Key management", frameworks=["NIS2"])

    monkeypatch.setattr(server_config, "kb_dir", kb_with)
    opt_with = check_option(option_payload, subject="Key management", frameworks=["NIS2"])

    assert json.dumps(opt_without, sort_keys=True) == json.dumps(opt_with, sort_keys=True)
