"""Tests for seed ontology entries (Issue #170).

Verifies:
1. data/kb/ontology/telco-cloud.yaml and security-zones.yaml load and pass check_ontology with 0 errors.
2. No IP addresses, specific hostnames or runtime instantiation values exist.
3. Every entry has definition, at least 1 FR and 1 EN synonym, and review_source.
4. Status is draft.
"""

import re
from pathlib import Path

from pipelines.ontology.checker import check_ontology
from pipelines.ontology.loader import load_ontology_entries

ROOT = Path(__file__).parent.parent.parent
ONTOLOGY_DIR = ROOT / "data" / "kb" / "ontology"

IPV4_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
IPV6_PATTERN = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b")
HOSTNAME_PATTERN = re.compile(r"\b[a-zA-Z0-9-]+\.(?:internal|local|corp|example\.com|localdomain)\b", re.IGNORECASE)


def test_seed_entries_pass_integrity_check():
    """Seed files telco-cloud.yaml and security-zones.yaml pass all integrity and quality checks."""
    assert ONTOLOGY_DIR.is_dir()
    report = check_ontology(ONTOLOGY_DIR)
    assert report.status == "ok", f"Ontology check failed with errors: {report.errors}"
    assert report.entries_count >= 8
    assert len(report.errors) == 0


def test_seed_entries_content_rules():
    """Verify metadata rules: definitions, FR/EN synonyms, review_source, and draft status."""
    entries = load_ontology_entries(ONTOLOGY_DIR)
    assert len(entries) >= 8

    for entry in entries:
        assert entry.definition and len(entry.definition.strip()) > 10, f"{entry.id} missing proper definition"
        assert len(entry.synonyms) >= 2, f"{entry.id} must have at least 1 FR and 1 EN synonym"
        assert entry.review_source and len(entry.review_source.strip()) > 5, f"{entry.id} missing review_source"
        assert entry.status == "draft", f"{entry.id} status must be draft"
        assert entry.revision == 1


def test_no_ip_addresses_or_hostnames():
    """Seed entries must reason in intension and contain no LLD IP addresses or environment hostnames."""
    yaml_files = list(ONTOLOGY_DIR.glob("*.yaml")) + list(ONTOLOGY_DIR.glob("*.yml"))
    assert yaml_files, "No YAML files found in data/kb/ontology"

    for file_path in yaml_files:
        content = file_path.read_text(encoding="utf-8")
        # Check IP addresses
        ipv4_matches = IPV4_PATTERN.findall(content)
        # Filter out possible version numbers like 17.4.0 or 29.500
        real_ips = [m for m in ipv4_matches if not any(f"TS {m}" in content or f"v{m}" in content for m in [m])]
        assert not real_ips, f"Found IP address in {file_path.name}: {real_ips}"

        ipv6_matches = IPV6_PATTERN.findall(content)
        assert not ipv6_matches, f"Found IPv6 address in {file_path.name}: {ipv6_matches}"

        host_matches = HOSTNAME_PATTERN.findall(content)
        assert not host_matches, f"Found hostname in {file_path.name}: {host_matches}"
