"""Enveloppe de réponse normalisée (Response Envelope) pour les outils MCP.

Conforme à T1.1 de TPL-fixes-server-contract / ADR-0014.
"""

from typing import Any


def ok_response(data: Any, count: int | None = None, **extra: Any) -> dict[str, Any]:
    """Succès avec résultats."""
    if count is None:
        if isinstance(data, list):
            count = len(data)
        elif isinstance(data, dict) and ("nodes" in data or "items" in data):
            items_list = data.get("nodes") if "nodes" in data else data.get("items")
            count = len(items_list) if isinstance(items_list, list) else (1 if data else 0)
        elif data is not None:
            count = 1
        else:
            count = 0
    res = {
        "status": "ok",
        "count": count,
        "data": data,
    }
    res.update(extra)
    return res


def not_found_response(id_val: str, data: Any = None) -> dict[str, Any]:
    """Identifiant introuvable."""
    return {
        "status": "not_found",
        "id": id_val,
        "data": data,
    }


def not_implemented_response(
    tool_name: str,
    reason: str = "engagement graph not served by this deployment",
    see: str = "ADR-0014",
) -> dict[str, Any]:
    """Capacité absente ou non implémentée sur ce déploiement."""
    return {
        "status": "not_implemented",
        "tool": tool_name,
        "reason": reason,
        "see": see,
    }


def invalid_argument_response(argument: str, reason: str) -> dict[str, Any]:
    """Argument invalide ou manquant."""
    return {
        "status": "invalid_argument",
        "argument": argument,
        "reason": reason,
    }


def error_response(reason: str) -> dict[str, Any]:
    """Erreur générique d'exécution."""
    return {
        "status": "error",
        "reason": reason,
    }


def unauthorized_response(engagement: str, reason: str = "Unauthorized to access engagement") -> dict[str, Any]:
    """Accès non autorisé à un engagement (403-equivalent)."""
    return {
        "status": "unauthorized",
        "engagement": engagement,
        "reason": f"{reason}: '{engagement}'",
    }
