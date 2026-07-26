"""Composant Boîte aux Lettres (Mailbox) — Interface d'échange asynchrone avec les experts."""

import json
from pathlib import Path
from typing import Protocol


class QuestionMessage:
    """Structure d'une question postée dans la boîte aux lettres."""

    def __init__(
        self,
        question_id: str,
        engagement: str,
        question_text: str,
        why_it_matters: str,
        expected_shape: str,
        routed_to: str,
    ) -> None:
        self.question_id = question_id
        self.engagement = engagement
        self.question_text = question_text
        self.why_it_matters = why_it_matters
        self.expected_shape = expected_shape
        self.routed_to = routed_to


class IncomingAnswer:
    """Structure d'une réponse d'expert lue dans la boîte aux lettres."""

    def __init__(
        self,
        question_id: str,
        answer_text: str,
        author: str,
        role: str,
    ) -> None:
        self.question_id = question_id
        self.answer_text = answer_text
        self.author = author
        self.role = role


class Mailbox(Protocol):
    """Protocol d'interface pour l'émission de questions et la réception de réponses."""

    def post(self, question: QuestionMessage) -> str:
        ...

    def notify(self, ref: str, message: str) -> None:
        ...

    def poll(self) -> list[IncomingAnswer]:
        ...


class FileMailbox:
    """Implémentation FileMailbox écrivant et lisant des fichiers JSON sous projects/<engagement>/mailbox/."""

    def __init__(self, engagement: str = "demo-2026", base_dir: str | Path = "projects") -> None:
        self.engagement = engagement
        self.mailbox_dir = Path(base_dir) / engagement / "mailbox"
        self.questions_dir = self.mailbox_dir / "questions"
        self.answers_dir = self.mailbox_dir / "answers"
        self.notifications_dir = self.mailbox_dir / "notifications"

        self.questions_dir.mkdir(parents=True, exist_ok=True)
        self.answers_dir.mkdir(parents=True, exist_ok=True)
        self.notifications_dir.mkdir(parents=True, exist_ok=True)

    def post(self, question: QuestionMessage) -> str:
        """Écrit un fichier JSON de question sous projects/<engagement>/mailbox/questions/<id>.json."""
        filepath = self.questions_dir / f"{question.question_id}.json"
        data = {
            "id": question.question_id,
            "engagement": question.engagement,
            "question": question.question_text,
            "why_it_matters": question.why_it_matters,
            "expected_shape": question.expected_shape,
            "routed_to": question.routed_to,
        }
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(filepath)

    def notify(self, ref: str, message: str) -> None:
        """Écrit une notification texte/json pour la référence."""
        filepath = self.notifications_dir / f"note_{ref.replace('/', '_')}.json"
        filepath.write_text(json.dumps({"ref": ref, "message": message}, indent=2), encoding="utf-8")

    def poll(self) -> list[IncomingAnswer]:
        """Lit tous les fichiers JSON d'ingestion sous projects/<engagement>/mailbox/answers/."""
        answers: list[IncomingAnswer] = []
        for p in self.answers_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                answers.append(
                    IncomingAnswer(
                        question_id=data["question_id"],
                        answer_text=data["text"],
                        author=data.get("author", "anonymous"),
                        role=data.get("role", "expert"),
                    )
                )
            except Exception:
                continue
        return answers


class GitHubIssuesMailbox:
    """Stub d'intégration GitHub Issues."""

    def post(self, question: QuestionMessage) -> str:
        return f"https://github.com/org/repo/issues/{question.question_id}"

    def notify(self, ref: str, message: str) -> None:
        pass

    def poll(self) -> list[IncomingAnswer]:
        return []
