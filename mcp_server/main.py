"""Point d'entrée du serveur FastMCP pour la Base de Connaissances d'Architecture."""

from fastmcp import FastMCP
from mcp_server.config import settings
from mcp_server.tools.asset_tools import (
    get_asset,
    get_decision_trail,
    get_glossary_term,
    list_assets,
)
from mcp_server.tools.graph_tools import get_graph_summary, query_graph

# Initialisation de l'instance FastMCP
mcp = FastMCP(settings.APP_NAME)

# Enregistrement des outils typés d'architecture
mcp.tool()(list_assets)
mcp.tool()(get_asset)
mcp.tool()(get_decision_trail)
mcp.tool()(get_glossary_term)

# Enregistrement des outils de graphe Cypher & résumé Kùzu DB
mcp.tool()(query_graph)
mcp.tool()(get_graph_summary)


import os


def main() -> None:
    """Point d'entrée CLI exécutable pour démarrer le serveur FastMCP sur STDIO ou SSE/HTTP."""
    transport = os.getenv("LLMOPS_TRANSPORT", settings.TRANSPORT).lower()
    port = int(os.getenv("PORT", settings.PORT))
    host = os.getenv("HOST", settings.HOST)

    if transport in ("sse", "http"):
        mcp.run(transport="sse")
    else:
        mcp.run(transport="stdio")



if __name__ == "__main__":
    main()
