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
from mcp_server.core.auth import (
    parse_engagement_tokens,
    set_current_caller,
)
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
    generate_zero_draft_hld,
    get_asset,
    get_assets,
    get_compliance_matrix,
    get_compliance_trail,
    get_decision_trail,
    get_glossary_term,
    get_graph_summary,
    get_principles_for,
    get_rfp_compliance_matrix,
    get_skills_matrix,
    list_assets,
    list_controls,
    list_frameworks,
    list_skills,
    query_graph,
    search_assets,
    shred_rfp,
    suggest_knowledge_improvement,
    trigger_rfp_elicitation,
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
mcp.tool()(list_frameworks)
mcp.tool()(list_controls)
mcp.tool()(get_compliance_trail)
mcp.tool()(get_compliance_matrix)
mcp.tool()(list_skills)
mcp.tool()(get_skills_matrix)
mcp.tool()(suggest_knowledge_improvement)
mcp.tool()(shred_rfp)
mcp.tool()(generate_zero_draft_hld)
mcp.tool()(get_rfp_compliance_matrix)
mcp.tool()(trigger_rfp_elicitation)

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
    """Transport SSE qui génère le callback /messages pour les sessions SSE avec traçabilité du caller."""

    def __init__(self, endpoint: str):
        super().__init__(endpoint)
        self._session_callers: dict[Any, str] = {}

    @asynccontextmanager
    async def connect_sse(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            raise ValueError("connect_sse can only handle HTTP requests")

        read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
        write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

        session_id = uuid4()
        self._read_stream_writers[session_id] = read_stream_writer

        caller = scope.get("caller") or "default_user"
        self._session_callers[session_id] = caller

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
            self._session_callers.pop(session_id, None)


# Transport SSE global
sse_transport = TokenPreservingSseServerTransport("/messages")


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware pour sécuriser l'accès HTTP/SSE par jeton Bearer ou Header HTTP (constant-time, multi-tenant)."""

    async def dispatch(self, request, call_next):
        if request.url.path in ("/health", "/healthz"):
            return await call_next(request)

        expected_token = os.getenv("SERVER_TOKEN") or os.getenv("LLMOPS_AUTH_TOKEN") or settings.AUTH_TOKEN
        env_tokens = os.getenv("ENGAGEMENT_TOKENS", "").strip()
        tenant_tokens = parse_engagement_tokens(env_tokens) if env_tokens else {}

        if (not expected_token or not expected_token.strip()) and not tenant_tokens:
            return JSONResponse(
                {"error": "Unauthorized: SERVER_TOKEN or LLMOPS_AUTH_TOKEN is not configured on server"},
                status_code=500,
            )

        auth_header = request.headers.get("Authorization")
        header_token = request.headers.get("X-API-Key") or request.headers.get("X-Server-Token")
        session_id_str = request.query_params.get("session_id")

        provided_token = None
        if auth_header and auth_header.startswith("Bearer "):
            provided_token = auth_header[7:].strip()
        elif header_token:
            provided_token = header_token.strip()

        caller = None

        # 1. Validation du jeton serveur explicite à temps constant (secrets.compare_digest)
        if provided_token and expected_token and secrets.compare_digest(provided_token, expected_token.strip()):
            caller = "server_admin"

        # 2. Validation contre les jetons locataires ENGAGEMENT_TOKENS à temps constant
        if not caller and provided_token and tenant_tokens:
            for t in tenant_tokens:
                if secrets.compare_digest(provided_token, t):
                    caller = t
                    break

        if caller:
            request.state.caller = caller
            request.scope["caller"] = caller
            set_current_caller(caller)
            return await call_next(request)

        # 3. Validation de secours si session_id appartient à une session SSE active sur la même instance
        if session_id_str and hasattr(sse_transport, "_read_stream_writers"):
            try:
                from uuid import UUID
                sid = UUID(session_id_str)
                if sid in sse_transport._read_stream_writers:
                    caller = getattr(sse_transport, "_session_callers", {}).get(sid, "default_user")
                    request.state.caller = caller
                    request.scope["caller"] = caller
                    set_current_caller(caller)
                    return await call_next(request)
            except Exception:
                pass

        return JSONResponse(
            {"error": "Unauthorized: Invalid or missing LLMOps authentication token in Authorization header"},
            status_code=401,
        )


def create_starlette_app() -> Starlette:
    """Crée et configure l'application Starlette avec ses routes et son middleware d'authentification."""

    async def handle_health(request):
        active_plane = os.getenv("LLMOPS_PLANE", server_config.plane).lower()
        backend = os.getenv("GRAPH_BACKEND", "ladybug")
        try:
            from tools.adapters.kuzu_store import make_graph_store
            store = make_graph_store("data/knowledge.kuzu", read_only=True)
            res = store.execute_cypher("MATCH (a:Asset) RETURN count(a) as count;")
            asset_count = res[0]["count"] if res and isinstance(res, list) and "count" in res[0] else 0
            store.close()
            return JSONResponse(
                {
                    "status": "ok",
                    "plane": active_plane,
                    "schema_version": "1.0",
                    "asset_count": asset_count,
                    "backend": backend,
                },
                status_code=200,
            )
        except Exception as e:
            return JSONResponse(
                {
                    "status": "ok",
                    "plane": active_plane,
                    "schema_version": "1.0",
                    "backend": backend,
                    "warning": str(e),
                },
                status_code=200,
            )

    async def handle_sse(request):
        caller = getattr(request.state, "caller", None) or request.scope.get("caller") or "default_user"
        set_current_caller(caller)
        async with sse_transport.connect_sse(
            request.scope, request.receive, request._send
        ) as streams:
            await mcp._mcp_server.run(
                streams[0],
                streams[1],
                mcp._mcp_server.create_initialization_options(),
            )

    async def handle_messages(request):
        session_id_str = request.query_params.get("session_id")
        caller = getattr(request.state, "caller", None)
        if not caller and session_id_str:
            try:
                from uuid import UUID
                sid = UUID(session_id_str)
                caller = getattr(sse_transport, "_session_callers", {}).get(sid, "default_user")
            except Exception:
                caller = "default_user"
        if caller:
            set_current_caller(caller)

        class SsePostResponse:
            async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
                await sse_transport.handle_post_message(scope, receive, send)

        return SsePostResponse()

    async def handle_visualize(request):
        from pathlib import Path

        from pipelines.visualization.graph_visualizer import GraphVisualizer

        db_path = os.getenv("KUZU_DB_PATH", "data/kuzu_db")
        viz = GraphVisualizer(db_path=db_path)
        temp_html_path = viz.generate_html(output_path="/tmp/graph_explorer.html")
        html_content = Path(temp_html_path).read_text(encoding="utf-8")
        return HTMLResponse(content=html_content)

    async def handle_snapshot_latest(request):
        from pathlib import Path
        latest_file = Path("data/snapshots/latest.json")
        if not latest_file.exists():
            latest_file = Path("fixtures/sealed_snapshot.json")
        if not latest_file.exists():
            from scripts.export_sealed_snapshot import export_sealed_snapshot
            snapshot_data = export_sealed_snapshot()
            return JSONResponse(snapshot_data, headers={"Cache-Control": "public, max-age=3600"})
        import json
        data = json.loads(latest_file.read_text(encoding="utf-8"))
        etag = data.get("payload_sha256", "")
        return JSONResponse(data, headers={"ETag": etag, "Cache-Control": "public, max-age=3600"})

    async def handle_snapshot_by_id(request):
        import json
        from pathlib import Path

        snap_id = request.path_params.get("snapshot_id", "")
        snap_file = Path("data/snapshots") / f"{snap_id}.json"
        if not snap_file.exists():
            return JSONResponse({"error": f"Snapshot '{snap_id}' not found"}, status_code=404)
        data = json.loads(snap_file.read_text(encoding="utf-8"))
        etag = data.get("payload_sha256", "")
        return JSONResponse(data, headers={"ETag": etag, "Cache-Control": "public, max-age=86400"})

    return Starlette(
        debug=settings.DEBUG,
        routes=[
            Route("/health", endpoint=handle_health, methods=["GET"]),
            Route("/sse", endpoint=handle_sse),
            Route("/messages", endpoint=handle_messages, methods=["POST"]),
            Route("/visualize", endpoint=handle_visualize, methods=["GET"]),
            Route("/snapshot/latest", endpoint=handle_snapshot_latest, methods=["GET"]),
            Route("/snapshot/{snapshot_id}", endpoint=handle_snapshot_by_id, methods=["GET"]),
        ],
        middleware=[Middleware(AuthMiddleware)],
    )


async def run_sse_authenticated(host: str, port: int) -> None:
    """Démarre le serveur SSE FastMCP enveloppé dans le middleware d'authentification."""
    starlette_app = create_starlette_app()
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
