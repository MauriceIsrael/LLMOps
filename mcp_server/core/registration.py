"""Mécanisme d'enregistrement et d'initialisation du serveur FastMCP.

Conforme à T2.1 de TPL-fixes-server-contract / ADR-0014.
"""

from typing import Callable, Any
from fastmcp import FastMCP
from mcp_server.core.config import ServerConfig, server_config


def create_mcp_server(config: ServerConfig = server_config) -> FastMCP:
    """Crée et configure une instance FastMCP d'après la configuration du serveur."""
    return FastMCP(config.app_name)


def register_tools(mcp: FastMCP, tools: list[Callable[..., Any]]) -> None:
    """Enregistre une liste de fonctions d'outils sur le serveur FastMCP."""
    for tool_fn in tools:
        mcp.tool()(tool_fn)
