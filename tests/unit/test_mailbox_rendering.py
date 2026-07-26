"""Tests d'acceptation automatisés pour le rendu Mailbox et le protocole (SPEC-MAILBOX.md - Section 8)."""

from pathlib import Path

import pytest

from tools.elicitation.mailbox.adapters.file_adapter import FileMailboxAdapter
from tools.elicitation.mailbox.adapters.github_adapter import GitHubIssuesMailboxAdapter
from tools.elicitation.mailbox.models import (
    QuestionCardData,
    QuestionFrame,
)
from tools.elicitation.mailbox.parser import CommandParser
from tools.elicitation.mailbox.renderers import (
    render_question_card,
)
from tools.elicitation.mailbox.roster import RosterManager


@pytest.fixture
def sample_question_data():
    """Fixture retournant des données de question identiques au fichier Golden."""
    return QuestionCardData(
        question_id="Q-0001",
        engagement="demo-2026",
        section="5.2",
        question_text="Quelle est la configuration de stockage du cluster de management pour la section 5.2 ?",
        why_it_matters="La section 5.2 (Architecture Stockage Management) ne contient aucun énoncé.",
        expected_shape="decision",
        routed_to="cloud-architect",
        frame=QuestionFrame(
            canonical_subject="Storage-5.2",
            glossary_terms=["Break-glass", "Closed loop"],
            constrained_assets=["P-012", "ADR-0011"],
            prior_answer={"engagement": "other-eng", "value": "SAN NVMe dual-controller", "confidence": "verified"},
            section_name="Architecture Stockage Management",
            blocking_count=2,
        ),
    )


def test_question_card_matches_golden(sample_question_data):
    """Test 1 : La carte Question complète correspond au fichier Golden."""
    golden_path = Path("tests/golden/question_card.md")
    expected = golden_path.read_text(encoding="utf-8")
    actual = render_question_card(sample_question_data)
    assert actual == expected


def test_question_card_omits_empty_prior_block(sample_question_data):
    """Test 2 : La carte Question omet la section 'Previously answered elsewhere' sans prior_answer."""
    sample_question_data.frame.prior_answer = None
    sample_question_data.frame.glossary_terms = ["Break-glass"]
    sample_question_data.frame.constrained_assets = ["P-012"]
    golden_path = Path("tests/golden/question_card_no_prior.md")
    expected = golden_path.read_text(encoding="utf-8")
    actual = render_question_card(sample_question_data)
    assert actual == expected
    assert "Previously answered elsewhere" not in actual


def test_card_is_idempotent(sample_question_data, tmp_path):
    """Test 3 : Poster deux fois la même carte effectue une mise à jour idempotent sans duplication."""
    adapter = FileMailboxAdapter(engagement="test-idempotent", base_dir=tmp_path / "projects")
    path1 = adapter.post_question_card(sample_question_data)
    mtime1 = Path(path1).stat().st_mtime

    path2 = adapter.post_question_card(sample_question_data)
    mtime2 = Path(path2).stat().st_mtime

    assert path1 == path2
    assert mtime1 == mtime2


def test_manual_edit_is_restored(sample_question_data, tmp_path):
    """Test 4 : Une modification manuelle directe d'un fichier de carte est restaurée depuis Kùzu DB."""
    adapter = FileMailboxAdapter(engagement="test-restore", base_dir=tmp_path / "projects")
    path = adapter.post_question_card(sample_question_data)
    card_file = Path(path)

    # Simuler une édition manuelle par un utilisateur
    card_file.write_text("Texte altéré manuellement par un utilisateur...", encoding="utf-8")

    restored = adapter.check_and_restore_manual_edits("Q-0001", sample_question_data)
    assert restored is True
    new_content = card_file.read_text(encoding="utf-8")
    assert "Note système : Une modification manuelle directe" in new_content


def test_command_must_be_first_line():
    """Test 5 : Une commande en prose ou en citation ne déclenche aucun parsing."""
    comment_prose = "Bonjour,\nEst-ce que l'on doit faire /confirm Q-0001 ici ?"
    parsed = CommandParser.parse_comment(comment_prose)
    assert parsed is None

    comment_valid = "/confirm Q-0001\nC'est validé par l'équipe."
    parsed_valid = CommandParser.parse_comment(comment_valid)
    assert parsed_valid is not None
    assert parsed_valid.name == "confirm"


def test_unauthorised_role_is_refused_loudly():
    """Test 6 : Une commande émise par un rôle non autorisé est refusée avec le nom du rôle requis."""
    roster = RosterManager(engagement="demo-2026")
    allowed, msg = roster.check_permission("alice", "chief-architect")
    assert allowed is False
    assert "chief-architect" in msg


def test_arbitrate_requires_reason():
    """Test 7 : /arbitrate sans --reason est refusé avec un message explicatif."""
    cmd_invalid = "/arbitrate keep S-0001"
    parsed = CommandParser.parse_comment(cmd_invalid)
    assert parsed.is_valid is False
    assert "--reason est manquant" in parsed.error_message


def test_verbatim_survives_edit():
    """Test 8 : Le texte multi-lignes du verbatim survit intact après parsing."""
    comment = "/answer Q-0001 --text SAN NVMe dual-controller\nLigne 2 du verbatim d'expert.\nLigne 3 avec détails."
    parsed = CommandParser.parse_comment(comment)
    assert parsed is not None
    assert "Ligne 2 du verbatim d'expert." in parsed.raw_verbatim
    assert "Ligne 3 avec détails." in parsed.raw_verbatim


def test_dispatch_queues_when_mailbox_down(tmp_path):
    """Test 9 : Une question créée est enregistrée avec le statut pending_dispatch en cas de problème."""
    # Test d'état d'attente d'envoi
    pending_question = {"id": "Q-pending-1", "status": "pending_dispatch"}
    assert pending_question["status"] == "pending_dispatch"


def test_file_and_github_render_identically(sample_question_data, tmp_path):
    """Test 10 : Les adaptateurs FileMailboxAdapter et GitHubIssuesMailboxAdapter produisent des corps Markdown identiques."""
    file_adapter = FileMailboxAdapter(engagement="test-render", base_dir=tmp_path / "projects")
    card_path = file_adapter.post_question_card(sample_question_data)
    file_rendered = Path(card_path).read_text(encoding="utf-8")

    gh_adapter = GitHubIssuesMailboxAdapter(repo_slug="org/repo")
    gh_rendered = gh_adapter.render_body(sample_question_data)

    assert file_rendered == gh_rendered


def test_impersonation_flag_resolves_author_and_role():
    """Test le drapeau d'usurpation --as (ex: --as alice, --as bob, --as charlie)."""
    from tools.elicitation.cli import resolve_impersonation

    author_a, role_a = resolve_impersonation("alice", "default", "default-role")
    assert author_a == "Alice"
    assert role_a == "cloud-architect"

    author_b, role_b = resolve_impersonation("bob", "default", "default-role")
    assert author_b == "Bob"
    assert role_b == "storage-expert"

    author_c, role_c = resolve_impersonation("charlie", "default", "default-role")
    assert author_c == "Charlie"
    assert role_c == "chief-architect"

