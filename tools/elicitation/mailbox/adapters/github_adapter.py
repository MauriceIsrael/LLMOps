"""Adaptateur GitHubIssuesMailboxAdapter pour l'interaction via GitHub Issues REST API."""

import os
from typing import Any

import httpx

from tools.elicitation.mailbox.models import QuestionCardData
from tools.elicitation.mailbox.parser import CommandParser, ParsedCommand
from tools.elicitation.mailbox.renderers import render_question_card


class GitHubIssuesMailboxAdapter:
    """Adaptateur de boîte aux lettres communiquant avec l'API REST v3 de GitHub Issues."""

    def __init__(self, repo_slug: str = "org/repo", token: str | None = None) -> None:
        self.repo_slug = repo_slug
        self.token = token or os.getenv("GITHUB_TOKEN", "")
        self.api_url = f"https://api.github.com/repos/{self.repo_slug}"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def render_body(self, data: QuestionCardData) -> str:
        """Génère le corps Markdown strict d'une fiche question (identique au FileMailboxAdapter)."""
        return render_question_card(data)

    def post_question_issue(self, data: QuestionCardData) -> dict[str, Any]:
        """Crée ou met à jour une Issue GitHub pour la question élicitée."""
        body = self.render_body(data)
        title = f"[{data.question_id}] {data.question_text[:55]}..."
        labels = [
            f"role:{data.routed_to}",
            f"section:{data.section}",
            f"engagement:{data.engagement}",
            f"blocks:{data.frame.blocking_count}",
        ]

        if not self.token:
            # Mode Offline / Stub : retourne les données de projection
            return {
                "id": data.question_id,
                "title": title,
                "labels": labels,
                "body": body,
                "url": f"https://github.com/{self.repo_slug}/issues/1",
            }

        with httpx.Client() as client:
            resp = client.post(
                f"{self.api_url}/issues",
                headers=self.headers,
                json={"title": title, "body": body, "labels": labels},
            )
            if resp.status_code in (200, 201):
                return resp.json()
            return {"error": resp.text}

    def poll_comments(self, issue_number: int) -> list[tuple[str, ParsedCommand]]:
        """Relève les commentaires d'une issue GitHub et extrait les commandes d'experts."""
        if not self.token:
            return []

        with httpx.Client() as client:
            resp = client.get(f"{self.api_url}/issues/{issue_number}/comments", headers=self.headers)
            if resp.status_code != 200:
                return []

            results = []
            for item in resp.json():
                user_login = item.get("user", {}).get("login", "anonymous")
                comment_text = item.get("body", "")
                parsed = CommandParser.parse_comment(comment_text)
                if parsed:
                    results.append((user_login, parsed))
            return results
