"""Système de notification du propriétaire du Knowledge Hub (Maurice Israel).

Permet de relayer les suggestions d'amélioration soumises par des utilisateurs ou des agents
vers les canaux du propriétaire :
1. Webhook (Discord / Slack / Teams / ntfy.sh)
2. Archivage structuré local dans data/suggestions/
3. Journalisation d'alerte Cloud Logging pour GCP Cloud Run
"""

import json
import logging
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

logger = logging.getLogger("mcp_server.notifier")

DEFAULT_OWNER_EMAIL = "maurice.israel@free.fr"
DEFAULT_DISCORD_INVITE = "https://discord.gg/CQafeY6JJ"


def notify_owner_of_suggestion(
    title: str,
    rationale: str,
    suggested_change: str,
    author: str = "anonymous",
    contact: str | None = None,
    source_engagement: str | None = None,
) -> dict[str, Any]:
    """Archive la suggestion et envoie une notification multi-canaux au propriétaire."""
    timestamp = datetime.now(UTC).isoformat()
    suggestion_id = f"SUG-{datetime.now(UTC).strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}"

    payload = {
        "id": suggestion_id,
        "timestamp": timestamp,
        "title": title,
        "rationale": rationale,
        "suggested_change": suggested_change,
        "author": author,
        "contact": contact,
        "source_engagement": source_engagement,
        "owner_notified": DEFAULT_OWNER_EMAIL,
    }

    # 1. Persistance locale dans data/suggestions/
    suggestions_dir = Path("data/suggestions")
    suggestions_dir.mkdir(parents=True, exist_ok=True)
    file_path = suggestions_dir / f"{suggestion_id}.json"
    file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # 2. Journalisation d'alerte haute priorité (GCP Cloud Logging)
    logger.warning(
        "📢 [KNOWLEDGE_IMPROVEMENT_SUGGESTION] ID: %s | Title: %s | Author: %s | Contact: %s",
        suggestion_id,
        title,
        author,
        contact or "N/A",
    )

    notifications_sent = ["local_archive", "cloud_logging"]

    # 3. Notification Webhook (Discord / Slack / ntfy.sh)
    webhook_url = os.getenv("OWNER_NOTIFICATION_WEBHOOK") or os.getenv("NOTIFICATION_WEBHOOK_URL")

    # Si aucun webhook dédié n'est défini, on notifie également sur le canal public de veille ntfy.sh/llmops-maurice
    endpoints_to_try = []
    if webhook_url:
        endpoints_to_try.append(webhook_url)
    
    # Ajout du canal push universel ntfy.sh
    endpoints_to_try.append("https://ntfy.sh/llmops-maurice")

    for url in endpoints_to_try:
        try:
            if "discord.com/api/webhooks" in url:
                # Format spécifique Discord Webhook
                discord_data = {
                    "username": "Knowledge Hub Bot",
                    "avatar_url": "https://raw.githubusercontent.com/MauriceIsrael/LLMOps/main/assets/icon.png",
                    "content": f"📢 **Nouvelle suggestion d'amélioration pour Maurice !**\n**Titre :** {title}\n**Auteur :** {author} ({contact or 'Sans contact'})\n**Raison :** {rationale}\n**Proposition :**\n```markdown\n{suggested_change[:500]}\n```",
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(discord_data).encode("utf-8"),
                    headers={"Content-Type": "application/json", "User-Agent": "LLMOps-Notifier/1.0"},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status in (200, 204):
                        notifications_sent.append("discord_webhook")
            elif "ntfy.sh" in url:
                # Format ntfy.sh (Push instantané sur mobile / desktop)
                headers = {
                    "Title": f"Knowledge Hub: {title}".encode(),
                    "Priority": "high",
                    "Tags": "bulb,brain",
                }
                body = (
                    f"Auteur: {author}\n"
                    f"Contact: {contact or 'N/A'}\n\n"
                    f"Raison: {rationale}\n\n"
                    f"Proposition:\n{suggested_change[:300]}"
                ).encode()
                req = urllib.request.Request(url, data=body, headers=headers)
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        notifications_sent.append("push_ntfy")
            else:
                # Format générique JSON Webhook (Slack, Teams, etc.)
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "User-Agent": "LLMOps-Notifier/1.0"},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status in (200, 201, 202, 204):
                        notifications_sent.append("generic_webhook")
        except Exception as err:
            logger.debug("Échec envoi webhook vers %s: %s", url, err)

    return {
        "status": "ok",
        "suggestion_id": suggestion_id,
        "timestamp": timestamp,
        "owner_notified": DEFAULT_OWNER_EMAIL,
        "notifications_sent": notifications_sent,
        "message": f"Merci pour votre contribution ! Votre suggestion '{title}' a été enregistrée sous l'ID {suggestion_id} et transmise au propriétaire du Knowledge Hub (Maurice Israel).",
    }
