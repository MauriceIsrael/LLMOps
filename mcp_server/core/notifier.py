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

    suggested_controls = []
    try:
        from pipelines.compliance_mapper import match_text_to_controls
        matches = match_text_to_controls(
            title=title,
            text=f"{rationale}\n{suggested_change}",
            threshold=0.35,
        )
        suggested_controls = [m.control_id for m in matches]
    except Exception as match_err:
        logger.debug("Échec détection automatique des contrôles : %s", match_err)

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
        "suggested_controls": suggested_controls,
    }

    # 1. Persistance locale dans data/suggestions/
    suggestions_dir = Path("data/suggestions")
    suggestions_dir.mkdir(parents=True, exist_ok=True)
    file_path = suggestions_dir / f"{suggestion_id}.json"
    file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # 2. Journalisation d'alerte haute priorité (GCP Cloud Logging)
    logger.warning(
        "📢 [KNOWLEDGE_IMPROVEMENT_SUGGESTION] ID: %s | Title: %s | Author: %s | Controls: %s",
        suggestion_id,
        title,
        author,
        ", ".join(suggested_controls) or "none",
    )

    notifications_sent = ["local_archive", "cloud_logging"]

    # 3. Notification Webhook (Discord / Slack / ntfy.sh)
    webhook_url = os.getenv("OWNER_NOTIFICATION_WEBHOOK") or os.getenv("NOTIFICATION_WEBHOOK_URL")

    endpoints_to_try = []
    if webhook_url:
        endpoints_to_try.append(webhook_url)

    # Ajout du canal push universel ntfy.sh
    endpoints_to_try.append("https://ntfy.sh/llmops-maurice")

    for url in endpoints_to_try:
        try:
            if "discord.com/api/webhooks" in url:
                fields = [
                    {"name": "Auteur", "value": author, "inline": True},
                    {"name": "Contact", "value": contact or "Non renseigné", "inline": True},
                    {"name": "Engagement", "value": source_engagement or "Global KB", "inline": True},
                    {"name": "ID Notification", "value": suggestion_id, "inline": True},
                ]
                if suggested_controls:
                    fields.append({
                        "name": "🛡️ Contrôles Réglementaires Détectés",
                        "value": ", ".join(suggested_controls),
                        "inline": False,
                    })

                discord_data = {
                    "username": "Knowledge Hub Bot",
                    "avatar_url": "https://raw.githubusercontent.com/MauriceIsrael/LLMOps/main/assets/icon.png",
                    "embeds": [
                        {
                            "title": f"📢 Nouvelle Suggestion d'Amélioration : {title}",
                            "description": f"**Raison / Valeur Architecturale :**\n{rationale}\n\n**Proposition :**\n```markdown\n{suggested_change[:600]}\n```",
                            "color": 3066993,  # Vert émeraude
                            "fields": fields,
                            "footer": {"text": "Knowledge Hub LLMOps • Détection & Harvest Automatique"},
                            "timestamp": timestamp,
                        }
                    ],
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
                headers: dict[str, str] = {
                    "Title": f"Knowledge Hub: {title}",
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


# ---------------------------------------------------------------------------
# KB candidate cycle (plan L2): owner routing and consumer notifications.
# ---------------------------------------------------------------------------

OWNER_EVENT_TITLES = {
    "in_review": "Candidat à relire",
    "second_review": "Seconde revue requise",
    "reminder": "Relance : candidat en attente de revue",
}


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def _post(url: str, data: bytes, headers: dict[str, str]) -> bool:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "LLMOps-Notifier/1.0", **headers})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return 200 <= resp.status < 300


def _send_email(to: str, subject: str, body: str) -> bool:
    """SMTP e-mail, disabled unless KB_NOTIFY_EMAIL_ENABLED=true and SMTP_HOST is set."""
    host = os.getenv("SMTP_HOST")
    if not _truthy(os.getenv("KB_NOTIFY_EMAIL_ENABLED")) or not host or not to:
        return False
    import smtplib
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.getenv("SMTP_FROM", "knowledge-hub@localhost")
    msg["To"] = to
    msg.set_content(body)
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=10) as smtp:
        if _truthy(os.getenv("SMTP_STARTTLS", "true")):
            smtp.starttls()
        if os.getenv("SMTP_USER"):
            smtp.login(os.getenv("SMTP_USER", ""), os.getenv("SMTP_PASSWORD", ""))
        smtp.send_message(msg)
    return True


def notify_owner(owner: dict[str, Any], event: str, candidate: dict[str, Any]) -> list[str]:
    """Notify a domain owner about a KB candidate on the owner's configured channels.

    ``owner``: ``{"handle", "email", "discord_webhook", "ntfy_topic"}`` (data/kb/owners.yaml).
    Returns the channels actually used (``log`` is always used).
    """
    handle = owner.get("handle") or "@maintainers"
    title = f"{OWNER_EVENT_TITLES.get(event, event)} : {candidate.get('title', '')}"
    failed = [c["name"] for c in candidate.get("checks") or [] if c.get("status") != "pass"]
    body = (
        f"Candidat {candidate.get('id')} ({candidate.get('kind')}, {candidate.get('asset_type') or 'n/a'})\n"
        f"Domaines : {', '.join(candidate.get('domain') or []) or 'n/a'}\n"
        f"Source : {(candidate.get('source') or {}).get('system')} / {(candidate.get('source') or {}).get('author') or 'n/a'}\n"
        f"Contrôles à examiner : {', '.join(failed) or 'aucun'}\n"
        f"Revue : PATCH /api/knowledge/candidates/{candidate.get('id')}"
    )
    logger.warning("📥 [KB_CANDIDATE_%s] %s -> %s | %s", event.upper(), candidate.get("id"), handle, title)
    sent = ["log"]
    if owner.get("delegated"):
        # The owner has an Archinex account: Archinex delivers the notification from the event feed.
        return sent + ["archinex"]
    try:
        # The webhook is a credential: besides the per-owner value, OWNER_DISCORD_WEBHOOK (environment / secret
        # manager, never git) serves every owner that has none of its own.
        webhook = owner.get("discord_webhook") or os.getenv("OWNER_DISCORD_WEBHOOK", "").strip()
        if webhook:
            payload = {"username": "Knowledge Hub Bot", "content": f"{handle} — **{title}**\n{body}"}
            if _post(webhook, json.dumps(payload).encode("utf-8"), {"Content-Type": "application/json"}):
                sent.append("discord")
    except Exception as err:
        logger.debug("Discord notification to %s failed: %s", handle, err)
    try:
        if owner.get("ntfy_topic"):
            base = os.getenv("NTFY_BASE_URL", "https://ntfy.sh").rstrip("/")
            if _post(f"{base}/{owner['ntfy_topic']}", body.encode("utf-8"), {"Title": title[:200], "Tags": "books"}):
                sent.append("ntfy")
    except Exception as err:
        logger.debug("ntfy notification to %s failed: %s", handle, err)
    try:
        if _send_email(str(owner.get("email") or ""), f"[Knowledge Hub] {title}", body):
            sent.append("email")
    except Exception as err:
        logger.debug("E-mail notification to %s failed: %s", handle, err)
    return sent


def notify_consumers(event: str, payload: dict[str, Any]) -> list[str]:
    """Notify knowledge base consumers (e.g. a new published version).

    Channels: ``KB_CONSUMER_WEBHOOKS`` (comma-separated JSON webhooks) and
    ``KB_CONSUMER_NTFY_TOPIC``. Returns the channels actually used (``log`` always).
    """
    logger.warning("📦 [KB_%s] %s", event.upper(), json.dumps(payload, ensure_ascii=False, default=str)[:500])
    sent = ["log"]
    for url in [u.strip() for u in os.getenv("KB_CONSUMER_WEBHOOKS", "").split(",") if u.strip()]:
        try:
            if _post(url, json.dumps({"event": event, **payload}, default=str).encode("utf-8"),
                     {"Content-Type": "application/json"}):
                sent.append("webhook")
        except Exception as err:
            logger.debug("Consumer webhook %s failed: %s", url, err)
    topic = os.getenv("KB_CONSUMER_NTFY_TOPIC")
    if topic:
        base = os.getenv("NTFY_BASE_URL", "https://ntfy.sh").rstrip("/")
        try:
            text = f"{event}: {payload.get('snapshot_id') or ''} ({len(payload.get('candidates') or [])} candidate(s))"
            if _post(f"{base}/{topic}", text.encode("utf-8"), {"Title": "Knowledge Hub"}):
                sent.append("ntfy")
        except Exception as err:
            logger.debug("Consumer ntfy notification failed: %s", err)
    return sent
