"""Adaptateur FileMailboxAdapter pour l'exécution hors-ligne et les tests de rendu."""

from pathlib import Path

from tools.elicitation.mailbox.models import QuestionCardData
from tools.elicitation.mailbox.parser import CommandParser, ParsedCommand
from tools.elicitation.mailbox.renderers import render_question_card


class FileMailboxAdapter:
    """Adaptateur de boîte aux lettres sur système de fichiers local sous projects/<engagement>/mailbox/."""

    def __init__(self, engagement: str = "demo-2026", base_dir: str | Path = "projects") -> None:
        self.engagement = engagement
        self.mailbox_dir = Path(base_dir) / engagement / "mailbox"
        self.questions_dir = self.mailbox_dir / "questions"
        self.questions_dir.mkdir(parents=True, exist_ok=True)

    def post_question_card(self, data: QuestionCardData) -> str:
        """Poste ou met à jour la fiche Question de manière idempotente sous questions/<q_id>/card.md."""
        q_dir = self.questions_dir / data.question_id
        q_dir.mkdir(parents=True, exist_ok=True)
        card_path = q_dir / "card.md"

        new_rendered = render_question_card(data)

        if card_path.exists():
            current_text = card_path.read_text(encoding="utf-8")
            # Extraire le hash s'il existe
            if new_rendered.splitlines()[0] == current_text.splitlines()[0]:
                # Hash identique -> Idempotent, pas de réécriture
                return str(card_path)

        card_path.write_text(new_rendered, encoding="utf-8")
        return str(card_path)

    def check_and_restore_manual_edits(self, q_id: str, expected_card_data: QuestionCardData) -> bool:
        """Vérifie si une fiche a été modifiée manuellement et la restaure depuis Kùzu DB (Test 4)."""
        card_path = self.questions_dir / q_id / "card.md"
        if not card_path.exists():
            return False

        current_text = card_path.read_text(encoding="utf-8")
        expected_rendered = render_question_card(expected_card_data)

        if current_text != expected_rendered:
            # Édition manuelle détectée ! Restauration et écriture d'une note
            restored_content = expected_rendered + "\n\n> ⚠️ *Note système : Une modification manuelle directe du fichier a été détectée et restaurée depuis Kùzu DB (source de vérité).*"
            card_path.write_text(restored_content, encoding="utf-8")
            return True

        return False

    def poll_commands(self, q_id: str) -> list[tuple[str, ParsedCommand]]:
        """Lit les commandes depuis questions/<q_id>/commands.md ou answers.json."""
        cmd_file = self.questions_dir / q_id / "commands.md"
        if not cmd_file.exists():
            return []

        text = cmd_file.read_text(encoding="utf-8")
        parsed = CommandParser.parse_comment(text)
        if parsed:
            return [("anonymous", parsed)]
        return []
