"""Point d'entrée du serveur FastMCP pour la Base de Connaissances d'Architecture."""

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import anyio
import uvicorn
from fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from sse_starlette.sse import EventSourceResponse
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route
from starlette.types import Receive, Scope, Send

from mcp_server.config import settings
from mcp_server.core.config import server_config
from mcp_server.engagement.tools import (
    get_board,
    get_conflicts,
    get_dangling_references,
    get_diagram_graph,
    get_engagement_export,
    get_open_questions,
    get_render_payload,
    get_statements,
    get_subject,
    get_subject_trajectory,
)
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

active_plane = os.getenv("LLMOPS_PLANE", server_config.plane).lower()
mcp = FastMCP(server_config.app_name)

# Enregistrement des outils typés du plan de connaissances
mcp.tool()(list_assets)
mcp.tool()(get_asset)
mcp.tool()(get_assets)
mcp.tool()(get_decision_trail)
mcp.tool()(get_glossary_term)
mcp.tool()(search_assets)
mcp.tool()(get_principles_for)
mcp.tool()(query_graph)
mcp.tool()(get_graph_summary)

# Enregistrement des outils du plan d'engagement (uniquement hors mode knowledge-only)
if active_plane != "knowledge":
    mcp.tool()(get_subject)
    mcp.tool()(get_subject_trajectory)
    mcp.tool()(get_board)
    mcp.tool()(get_statements)
    mcp.tool()(get_conflicts)
    mcp.tool()(get_open_questions)
    mcp.tool()(get_diagram_graph)
    mcp.tool()(get_render_payload)
    mcp.tool()(get_dangling_references)
    mcp.tool()(get_engagement_export)


import secrets


class TokenPreservingSseServerTransport(SseServerTransport):
    """Transport SSE qui génère le callback /messages pour les sessions SSE."""

    @asynccontextmanager
    async def connect_sse(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            raise ValueError("connect_sse can only handle HTTP requests")

        read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
        write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

        session_id = uuid4()
        self._read_stream_writers[session_id] = read_stream_writer

        root_path = scope.get("root_path", "")
        full_message_path = root_path.rstrip("/") + self._endpoint
        client_post_uri = f"{quote(full_message_path)}?session_id={session_id.hex}"

        sse_stream_writer, sse_stream_reader = anyio.create_memory_object_stream[dict[str, Any]](0)

        async def sse_writer():
            async with sse_stream_writer, write_stream_reader:
                await sse_stream_writer.send({"event": "endpoint", "data": client_post_uri})
                async for session_message in write_stream_reader:
                    await sse_stream_writer.send(
                        {
                            "event": "message",
                            "data": session_message.message.model_dump_json(by_alias=True, exclude_none=True),
                        }
                    )

        try:
            async with anyio.create_task_group() as tg:
                async def response_wrapper(scope: Scope, receive: Receive, send: Send):
                    await EventSourceResponse(content=sse_stream_reader, data_sender_callable=sse_writer)(
                        scope, receive, send
                    )
                    await read_stream_writer.aclose()
                    await write_stream_reader.aclose()
                    await sse_stream_reader.aclose()

                tg.start_soon(response_wrapper, scope, receive, send)
                yield (read_stream, write_stream)
        finally:
            self._read_stream_writers.pop(session_id, None)


# Transport SSE global
sse_transport = TokenPreservingSseServerTransport("/messages")


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware pour sécuriser l'accès HTTP/SSE par jeton Bearer ou Header HTTP (constant-time)."""

    async def dispatch(self, request, call_next):
        if request.url.path in ("/health", "/healthz"):
            return await call_next(request)

        expected_token = os.getenv("SERVER_TOKEN") or os.getenv("LLMOPS_AUTH_TOKEN") or settings.AUTH_TOKEN
        if not expected_token or not expected_token.strip():
            return JSONResponse(
                {"error": "Unauthorized: SERVER_TOKEN or LLMOPS_AUTH_TOKEN is not configured on server"},
                status_code=500,
            )

        auth_header = request.headers.get("Authorization")
        header_token = request.headers.get("X-API-Key") or request.headers.get("X-Server-Token")
        session_id = request.query_params.get("session_id")

        provided_token = None
        if auth_header and auth_header.startswith("Bearer "):
            provided_token = auth_header[7:].strip()
        elif header_token:
            provided_token = header_token.strip()

        # 1. Validation du jeton explicite à temps constant (secrets.compare_digest)
        if provided_token and secrets.compare_digest(provided_token, expected_token):
            return await call_next(request)

        # 2. Validation de secours si session_id appartient à une session SSE active sur la même instance
        if session_id and hasattr(sse_transport, "_read_stream_writers"):
            if session_id in sse_transport._read_stream_writers:
                return await call_next(request)

        return JSONResponse(
            {"error": "Unauthorized: Invalid or missing LLMOps authentication token in Authorization header"},
            status_code=401,
        )


async def run_sse_authenticated(host: str, port: int) -> None:
    """Démarre le serveur SSE FastMCP enveloppé dans le middleware d'authentification."""

    async def handle_health(request):
        try:
            from tools.adapters.kuzu_store import make_graph_store
            store = make_graph_store("data/knowledge.kuzu", read_only=True)
            res = store.execute_cypher("RETURN 1 as ok;")
            store.close()
            return JSONResponse({"status": "ok", "backend": os.getenv("GRAPH_BACKEND", "ladybug"), "db_check": res}, status_code=200)
        except Exception as e:
            return JSONResponse({"status": "ok", "backend": os.getenv("GRAPH_BACKEND", "ladybug"), "warning": str(e)}, status_code=200)

    async def handle_sse(request):
        async with sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await mcp._mcp_server.run(
                streams[0],
                streams[1],
                mcp._mcp_server.create_initialization_options(),
            )

    async def handle_messages(request):
        await sse_transport.handle_post_message(
            request.scope, request.receive, request._send
        )

    async def handle_visualize(request):
        from pathlib import Path

        from pipelines.visualization.graph_visualizer import GraphVisualizer

        db_path = os.getenv("KUZU_DB_PATH", "data/kuzu_db")
        viz = GraphVisualizer(db_path=db_path)
        temp_html_path = viz.generate_html(output_path="/tmp/graph_explorer.html")
        html_content = Path(temp_html_path).read_text(encoding="utf-8")
        return HTMLResponse(content=html_content)


    starlette_app = Starlette(
        debug=settings.DEBUG,
        routes=[
            Route("/health", endpoint=handle_health, methods=["GET"]),
            Route("/sse", endpoint=handle_sse),
            Route("/messages", endpoint=handle_messages, methods=["POST"]),
            Route("/visualize", endpoint=handle_visualize, methods=["GET"]),
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
        expected_token = os.getenv("SERVER_TOKEN") or os.getenv("LLMOPS_AUTH_TOKEN") or settings.AUTH_TOKEN
        if not expected_token or not expected_token.strip():
            raise RuntimeError(
                "CRITICAL SECURITY FAILURE: SERVER_TOKEN or LLMOPS_AUTH_TOKEN environment variable must be set to start the HTTP/SSE server. Refusing to run in unauthenticated mode."
            )
        asyncio.run(run_sse_authenticated(host=host, port=port))
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
