"""Serveur MCP pour le Plan d'Engagement (Engagement Plane Server).

Expose uniquement les outils relatifs aux données d'engagement (Subject, Statement, Question, Conflict).
Conforme à T2.2 / ADR-0014.
"""

from fastmcp import FastMCP

from mcp_server.core.config import server_config
from mcp_server.core.registration import register_tools
from mcp_server.engagement.tools import (
    get_board,
    get_conflicts,
    get_dangling_references,
    get_diagram_graph,
    get_engagement_export,
    get_graph_summary,
    get_open_questions,
    get_render_payload,
    get_statements,
    get_subject,
    get_subject_trajectory,
    query_graph,
)

server_config.plane = "engagement"
mcp = FastMCP("LLMOps Engagement Server")

register_tools(
    mcp,
    [
        get_subject,
        get_subject_trajectory,
        get_board,
        get_statements,
        get_conflicts,
        get_open_questions,
        get_diagram_graph,
        get_render_payload,
        get_dangling_references,
        get_engagement_export,
        query_graph,
        get_graph_summary,
    ],
)

def main() -> None:
    """Point d'entrée pour l'Engagement Server."""
    mcp.run()


if __name__ == "__main__":
    main()
