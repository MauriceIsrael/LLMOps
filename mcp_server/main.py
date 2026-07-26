"""Point d'entrée du serveur FastMCP pour la Base de Connaissances d'Architecture."""

import asyncio
import os

import uvicorn
from fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route

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


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware pour sécuriser l'accès HTTP/SSE par jeton Bearer, Header ou Paramètre d'URL."""

    async def dispatch(self, request, call_next):
        expected_token = os.getenv("LLMOPS_AUTH_TOKEN", settings.AUTH_TOKEN)
        if not expected_token:
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        query_token = request.query_params.get("token")
        header_token = request.headers.get("X-API-Key")

        provided_token = None
        if auth_header and auth_header.startswith("Bearer "):
            provided_token = auth_header[7:].strip()
        elif header_token:
            provided_token = header_token.strip()
        elif query_token:
            provided_token = query_token.strip()

        if provided_token != expected_token:
            return JSONResponse(
                {"error": "Unauthorized: Invalid or missing LLMOps authentication token"},
                status_code=401,
            )

        return await call_next(request)


async def run_sse_authenticated(host: str, port: int) -> None:
    """Démarre le serveur SSE FastMCP enveloppé dans le middleware d'authentification."""
    sse = SseServerTransport("/messages")

    async def handle_sse(request):
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await mcp._mcp_server.run(
                streams[0],
                streams[1],
                mcp._mcp_server.create_initialization_options(),
            )

    async def handle_messages(request):
        await sse.handle_post_message(request.scope, request.receive, request._send)

    starlette_app = Starlette(
        debug=settings.DEBUG,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Route("/messages", endpoint=handle_messages, methods=["POST"]),
        ],
        middleware=[Middleware(AuthMiddleware)],
    )

    config = uvicorn.Config(
        starlette_app,
        host=host,
        port=port,
        log_level="info",
    )
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    """Point d'entrée CLI exécutable pour démarrer le serveur FastMCP sur STDIO ou SSE/HTTP."""
    transport = os.getenv("LLMOPS_TRANSPORT", settings.TRANSPORT).lower()
    port = int(os.getenv("PORT", settings.PORT))
    host = os.getenv("HOST", settings.HOST)

    if transport in ("sse", "http"):
        asyncio.run(run_sse_authenticated(host=host, port=port))
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()


