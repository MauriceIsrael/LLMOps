"""Tests for ontology documentation and PR template checklist (Issue #174)."""

from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


def test_ontology_readme_guide_and_checklist():
    readme = ROOT / "data" / "kb" / "ontology" / "README.md"
    assert readme.is_file(), "data/kb/ontology/README.md missing"
    text = readme.read_text(encoding="utf-8")

    # Guide sections
    assert "Quand créer une entrée d'ontologie vs utiliser le glossaire" in text
    assert "Conventions de nommage" in text
    assert "Projections taxonomiques" in text

    # Checklist items
    assert "Checklist de relecture" in text
    assert "Définition intensionnelle" in text
    assert "Intégrité référentielle" in text
    assert "Symétrie de l'isolation" in text
    assert "Synonymes bilingues" in text
    assert "reviewed_by" in text
    assert "kb check --experimental-ontology" in text


def test_contributing_references_ontology_guide():
    contrib = ROOT / "data" / "kb" / "CONTRIBUTING.md"
    assert contrib.is_file()
    text = contrib.read_text(encoding="utf-8")
    assert "ontology/README.md" in text


def test_pr_template_includes_ontology_checklist():
    pr_template = ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
    if not pr_template.is_file():
        pr_template = ROOT / ".github" / "pull_request_template.md"
    assert pr_template.is_file()
    text = pr_template.read_text(encoding="utf-8")
    assert "data/kb/ontology/" in text
    assert "kb check --experimental-ontology" in text
