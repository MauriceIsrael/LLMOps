"""Serveur MCP pour le Plan de Connaissances (Knowledge Plane Server).

Expose uniquement les outils relatifs aux actifs réutilisables d'architecture (Asset, GlossaryTerm, Principle, ADR).
Conforme à T2.2 / ADR-0014.
"""

from fastmcp import FastMCP
from mcp_server.core.config import server_config
from mcp_server.core.registration import register_tools
from mcp_server.knowledge.tools import (
    get_asset,
    get_assets,
    get_decision_trail,
    get_glossary_term,
    get_graph_summary,
    get_principles_for,
    list_assets,
    query_graph,
    search_assets,
)

server_config.plane = "knowledge"
mcp = FastMCP("LLMOps Knowledge Base")

register_tools(
    mcp,
    [
        list_assets,
        get_asset,
        get_assets,
        get_decision_trail,
        get_glossary_term,
        search_assets,
        get_principles_for,
        query_graph,
        get_graph_summary,
    ],
)

def main() -> None:
    """Point d'entrée pour le Knowledge Server."""
    mcp.run()


if __name__ == "__main__":
    main()
