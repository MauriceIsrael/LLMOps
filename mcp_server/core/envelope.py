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


def error_response(reason: str, correlation_id: str | None = None) -> dict[str, Any]:
    """Erreur générique d'exécution avec raison assainie et corrélation optionnelle."""
    res: dict[str, Any] = {
        "status": "error",
        "reason": reason,
    }
    if correlation_id:
        res["correlation_id"] = correlation_id
    return res


def handle_exception_response(exc: Exception, context_action: str = "operation") -> dict[str, Any]:
    """Intercepte une exception, trace le log serveur avec ID, et retourne une enveloppe assainie."""
    import logging
    import uuid

    from mcp_server.core.config import server_config
    from mcp_server.core.exceptions import EngagementNotFound, QueryRejected, SchemaError

    corr_id = uuid.uuid4().hex[:8]
    logger = logging.getLogger("mcp_server")
    logger.error("Error [%s] during %s: %s", corr_id, context_action, exc, exc_info=True)

    if isinstance(exc, QueryRejected):
        return error_response(f"Query rejected: {exc.reason}", correlation_id=corr_id)
    if isinstance(exc, EngagementNotFound):
        return error_response(f"Engagement not found: {exc.engagement}", correlation_id=corr_id)
    if isinstance(exc, SchemaError):
        clean_schema_err = str(exc).replace("/home/momo/Dev/LLMOps/", "")
        return error_response(f"Database schema error: table or property does not exist ({clean_schema_err})", correlation_id=corr_id)

    if server_config.env == "production":
        return error_response(f"Internal error during {context_action}. Correlation ID: {corr_id}", correlation_id=corr_id)

    # En développement : message descriptif sans fuite de chemins absolus système
    clean_msg = str(exc).replace("/home/momo/Dev/LLMOps/", "")
    return error_response(clean_msg, correlation_id=corr_id)


def unauthorized_response(engagement: str, reason: str = "Unauthorized to access engagement") -> dict[str, Any]:
    """Accès non autorisé à un engagement (403-equivalent)."""
    return {
        "status": "unauthorized",
        "engagement": engagement,
        "reason": f"{reason}: '{engagement}'",
    }
