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
        if request.url.path in ("/health", "/healthz", "/ready", "/readyz"):
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

        # 1. Validation prioritaire contre les jetons locataires ENGAGEMENT_TOKENS à temps constant
        if provided_token and tenant_tokens:
            for t in tenant_tokens:
                if secrets.compare_digest(provided_token, t):
                    caller = t
                    break

        # 2. Sinon, validation du jeton d'administration serveur explicite à temps constant
        if not caller and provided_token and expected_token and secrets.compare_digest(provided_token, expected_token.strip()):
            caller = "server_admin"

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
                    caller = getattr(sse_transport, "_session_callers", {}).get(sid)
                    if caller:
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
        """Liveness probe: returns 200 if the server process is responsive, with engine and KB version metadata."""
        import json
        from pathlib import Path

        kb_meta = {}
        latest_file = Path("data/snapshots/latest.json")
        if latest_file.exists():
            try:
                snap = json.loads(latest_file.read_text(encoding="utf-8"))
                kb_meta = {
                    "snapshot_id": snap.get("snapshot_id"),
                    "source_revision": snap.get("source_revision"),
                    "payload_sha256": snap.get("payload_sha256"),
                    "created_at": snap.get("created_at"),
                }
            except Exception:
                pass

        return JSONResponse(
            {
                "status": "ok",
                "plane": server_config.plane,
                "schema_version": "1.0",
                "service": "llmops-mcp-server",
                "engine_version": "0.1.0",
                "engine_commit": "aa2ec8e",
                "kb": kb_meta,
            },
            status_code=200,
        )

    async def handle_ready(request):
        """Readiness probe: validates actual database connectivity and non-zero knowledge assets."""
        db_path = server_config.knowledge_db_path
        backend = os.getenv("GRAPH_BACKEND", "ladybug")
        try:
            from tools.adapters.kuzu_store import make_graph_store

            store = make_graph_store(db_path, read_only=True)
            res = store.execute_cypher("MATCH (a:Asset) RETURN count(a) as count;")
            asset_count = res[0]["count"] if res and isinstance(res, list) and "count" in res[0] else 0
            store.close()

            if asset_count == 0:
                return JSONResponse(
                    {
                        "status": "not_ready",
                        "error": "Knowledge graph is empty (asset_count is 0)",
                        "plane": server_config.plane,
                        "backend": backend,
                    },
                    status_code=503,
                )

            return JSONResponse(
                {
                    "status": "ready",
                    "plane": server_config.plane,
                    "schema_version": "1.0",
                    "asset_count": asset_count,
                    "backend": backend,
                },
                status_code=200,
            )
        except Exception as e:
            return JSONResponse(
                {
                    "status": "not_ready",
                    "error": f"Database readiness check failed: {e}",
                    "plane": server_config.plane,
                    "backend": backend,
                },
                status_code=503,
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

    async def handle_knowledge_search(request):
        """Recherche REST d'assets dans le graphe de connaissances (Document Studio & clients HTTP)."""
        engagement = (
            request.headers.get("X-Engagement-Id")
            or request.query_params.get("engagement")
            or "default"
        ).strip()
        query = request.query_params.get("query", "").strip()
        res = search_assets(query=query)
        status_code = 200 if res.get("status") == "ok" else 400
        return JSONResponse(res, status_code=status_code)

    async def handle_knowledge_engagements(request):
        """Liste les référentiels d'engagements / bases d'architecture disponibles sur le Hub."""
        engagements = [
            {
                "id": "default",
                "name": "Socle Transverse Télécom & Sécurité",
                "description": "Motifs d'architecture, ADRs et principes directeurs d'entreprise",
                "is_default": True,
            }
        ]
        eng_dir = server_config.engagements_dir
        if eng_dir.exists():
            for f in sorted(eng_dir.glob("*.lbug")):
                eid = f.stem
                if eid == "default":
                    continue
                friendly_name = eid.replace("-", " ").replace("_", " ").title()
                engagements.append({
                    "id": eid,
                    "name": friendly_name,
                    "description": f"Référentiel d'engagement et base projet pour {friendly_name}",
                    "is_default": False,
                })

        return JSONResponse({
            "status": "ok",
            "engagements": engagements,
            "count": len(engagements),
        }, status_code=200)

    async def handle_compliance_conformity_snapshot(request):
        """Exporte un ConformitySnapshot scellé pour injection directe dans document-engine (ADR-DE-05)."""
        engagement = (
            request.headers.get("X-Engagement-Id")
            or request.query_params.get("engagement")
            or "default"
        ).strip()
        framework = request.query_params.get("framework", "ALL").strip()

        try:
            from pipelines.compliance_mapper import to_conformity_snapshot
            snapshot = to_conformity_snapshot(
                engagement=engagement,
                framework=framework,
                controls_dir=server_config.kb_dir / "controls",
            )
            return JSONResponse(snapshot, status_code=200)
        except Exception as e:
            return JSONResponse(
                {"status": "error", "error": f"Échec de génération du ConformitySnapshot : {e}"},
                status_code=500,
            )

    async def handle_knowledge_suggestions(request):
        """Soumission REST d'une suggestion d'amélioration/REX issue de la curation humaine."""
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"status": "error", "error": "Corps de requête JSON invalide ou absent"},
                status_code=400,
            )

        if not isinstance(body, dict):
            return JSONResponse(
                {"status": "error", "error": "Le corps de requête doit être un objet JSON"},
                status_code=400,
            )

        title = str(body.get("title", "")).strip()
        rationale = str(body.get("rationale", "")).strip()
        suggested_change = str(body.get("suggested_change", "")).strip()
        author = str(body.get("author", "document-studio")).strip()
        contact_email = body.get("contact_email")
        source_engagement = body.get("source_engagement")

        res = suggest_knowledge_improvement(
            title=title,
            rationale=rationale,
            suggested_change=suggested_change,
            author=author,
            contact_email=str(contact_email).strip() if contact_email else None,
            source_engagement=str(source_engagement).strip() if source_engagement else None,
        )
        status_code = 200 if res.get("status") == "ok" else 400
        return JSONResponse(res, status_code=status_code)

    async def handle_rfp_shred_to_candidates(request):
        """Déstructure un RFP et produit directement la liste des ExtractedCandidate pour requirements-intake."""
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"status": "error", "error": "Corps de requête JSON invalide ou absent"},
                status_code=400,
            )

        if not isinstance(body, dict):
            return JSONResponse(
                {"status": "error", "error": "Le corps de requête doit être un objet JSON"},
                status_code=400,
            )

        rfp_text = str(body.get("rfp_text", "")).strip()
        document_id = str(body.get("document_id", "doc-rfp")).strip()
        document_version = str(body.get("document_version", "1.0")).strip()
        engagement = str(body.get("engagement", "default")).strip()

        if not rfp_text:
            return JSONResponse(
                {"status": "error", "error": "rfp_text ne peut pas être vide"},
                status_code=400,
            )

        try:
            from pipelines.rfp_shredder import RFPShredder, to_extracted_candidates

            shredder = RFPShredder(kb_dir="data/kb")
            requirements = shredder.shred_text(rfp_text, engagement=engagement)
            candidates = to_extracted_candidates(requirements, document_id, document_version)

            return JSONResponse(
                {
                    "status": "ok",
                    "candidates": candidates,
                    "count": len(candidates),
                    "documentId": document_id,
                    "documentVersion": document_version,
                },
                status_code=200,
            )
        except Exception as e:
            return JSONResponse(
                {"status": "error", "error": f"Échec de l'extraction de candidates : {e}"},
                status_code=500,
            )

    async def handle_zero_draft_blueprint(request):
        """Génère un couple Blueprint + ProseStore pour document-engine à partir des connaissances du Hub."""
        try:
            body = await request.json()
        except Exception:
            body = {}

        engagement = str(body.get("engagement", "default")).strip() if isinstance(body, dict) else "default"
        project_title = str(body.get("project_title", "Système d'Architecture Télécom & Plateforme Sécurisée")).strip() if isinstance(body, dict) else "Système d'Architecture Télécom & Plateforme Sécurisée"
        client_name = str(body.get("client_name", "Client RFP")).strip() if isinstance(body, dict) else "Client RFP"

        try:
            from tools.elicitation.zero_draft import ZeroDraftAssembler

            assembler = ZeroDraftAssembler(
                db_path=server_config.engagements_dir / f"{engagement}.lbug",
                kb_dir=server_config.kb_dir,
            )
            res = assembler.to_blueprint_and_prose(
                engagement=engagement,
                project_title=project_title,
                client_name=client_name,
            )
            return JSONResponse({"status": "ok", "proseStore": res.get("prose_store", {}), **res}, status_code=200)
        except Exception as e:
            return JSONResponse(
                {"status": "error", "error": f"Échec de la génération Blueprint : {e}"},
                status_code=500,
            )

    async def handle_prose_suggest_batch(request):
        """Assistance de rédaction par lot pour les blocs prose de document-engine (ADR-DE-02)."""
        try:
            body = await request.json()
        except Exception:
            return JSONResponse(
                {"status": "error", "error": "Corps de requête JSON invalide ou absent"},
                status_code=400,
            )

        if not isinstance(body, dict):
            return JSONResponse(
                {"status": "error", "error": "Le corps de requête doit être un objet JSON"},
                status_code=400,
            )

        requests = body.get("requests", [])
        if not isinstance(requests, list):
            return JSONResponse(
                {"status": "error", "error": "'requests' doit être une liste"},
                status_code=400,
            )

        import hashlib
        from datetime import datetime, timezone

        drafts = {}
        warnings = []

        for req in requests:
            if not isinstance(req, dict):
                continue
            block_id = req.get("blockId", "")
            if not block_id:
                continue
            anchor_ids = req.get("anchorIds", [])
            instructions = req.get("instructions", "")

            matched_text = []
            for anchor in anchor_ids:
                res = search_assets(query=anchor)
                if res.get("status") == "ok" and res.get("assets"):
                    for a in res["assets"][:2]:
                        matched_text.append(f"{a.get('title', '')} : {a.get('summary', '')}")

            if matched_text:
                draft_content = (
                    f"Conception validée pour le bloc '{block_id}' : "
                    + " ".join(matched_text)
                    + (" " + instructions if instructions else "")
                )
            else:
                draft_content = (
                    f"Le bloc '{block_id}' implémente les composants ({', '.join(anchor_ids) if anchor_ids else 'génériques'}) "
                    f"conformément aux motifs d'architecture du Knowledge Hub et aux exigences contractuelles."
                )

            drafts[block_id] = draft_content

        model_hash = hashlib.sha256(str(body).encode()).hexdigest()[:16]
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        return JSONResponse(
            {
                "drafts": drafts,
                "warnings": warnings,
                "basedOnModelHash": model_hash,
                "generatedAt": now_str,
            },
            status_code=200,
        )

    async def handle_elicitation_trigger(request):
        """Déclenche la génération de questions ciblées pour les exigences RFP non couvertes (gaps)."""
        try:
            body = await request.json()
        except Exception:
            body = {}
        engagement = (
            request.headers.get("X-Engagement-Id")
            or (body.get("engagement") if isinstance(body, dict) else None)
            or request.query_params.get("engagement")
            or "default"
        ).strip()

        res = trigger_rfp_elicitation(engagement=engagement)
        status_code = 200 if res.get("status") == "ok" else 400
        return JSONResponse(res, status_code=status_code)

    async def handle_elicitation_questions(request):
        """Liste les questions ouvertes d'élicitation pour un engagement et un rôle donné."""
        engagement = (
            request.headers.get("X-Engagement-Id")
            or request.query_params.get("engagement")
            or "default"
        ).strip()
        role = request.query_params.get("role")
        res = get_open_questions(engagement=engagement, role=role)
        status_code = 200 if res.get("status") == "ok" else 400
        return JSONResponse(res, status_code=status_code)

    async def handle_arbitration_board(request):
        """Tableau de maturité d'architecture des sujets (L0 à L4)."""
        engagement = (
            request.headers.get("X-Engagement-Id")
            or request.query_params.get("engagement")
            or "default"
        ).strip()
        res = get_board(engagement=engagement)
        status_code = 200 if res.get("status") == "ok" else 400
        return JSONResponse(res, status_code=status_code)

    async def handle_arbitration_conflicts(request):
        """Liste les conflits et controverses d'architecture ouverts ou arbitrés."""
        engagement = (
            request.headers.get("X-Engagement-Id")
            or request.query_params.get("engagement")
            or "default"
        ).strip()
        status = request.query_params.get("status", "open")
        res = get_conflicts(engagement=engagement, status=status)
        status_code = 200 if res.get("status") == "ok" else 400
        return JSONResponse(res, status_code=status_code)

    async def handle_arbitration_statements(request):
        """Liste les énoncés d'architecture actifs."""
        engagement = (
            request.headers.get("X-Engagement-Id")
            or request.query_params.get("engagement")
            or "default"
        ).strip()
        subject = request.query_params.get("subject")
        section = request.query_params.get("section")
        status = request.query_params.get("status")
        res = get_statements(engagement=engagement, subject=subject, section=section, status=status)
        status_code = 200 if res.get("status") == "ok" else 400
        return JSONResponse(res, status_code=status_code)

    async def handle_skills_list(request):
        """Référentiel canonique des compétences d'ingénierie et niveaux de criticité."""
        domain = request.query_params.get("domain")
        res = list_skills(domain=domain)
        status_code = 200 if res.get("status") == "ok" else 400
        return JSONResponse(res, status_code=status_code)

    async def handle_skills_matrix(request):
        """Matrice de couverture de compétences et risque de staffing pour un engagement."""
        engagement = (
            request.headers.get("X-Engagement-Id")
            or request.query_params.get("engagement")
            or "default"
        ).strip()
        blueprint_path = request.query_params.get("blueprint_path", "data/kb/blueprints/BLU-hla-mcx.yaml")
        res = get_skills_matrix(engagement=engagement, blueprint_path=blueprint_path)
        status_code = 200 if res.get("status") == "ok" else 400
        return JSONResponse(res, status_code=status_code)

    return Starlette(
        debug=settings.DEBUG,
        routes=[
            Route("/health", endpoint=handle_health, methods=["GET"]),
            Route("/healthz", endpoint=handle_health, methods=["GET"]),
            Route("/ready", endpoint=handle_ready, methods=["GET"]),
            Route("/readyz", endpoint=handle_ready, methods=["GET"]),
            Route("/sse", endpoint=handle_sse),
            Route("/messages", endpoint=handle_messages, methods=["POST"]),
            Route("/visualize", endpoint=handle_visualize, methods=["GET"]),
            Route("/snapshot/latest", endpoint=handle_snapshot_latest, methods=["GET"]),
            Route("/snapshot/{snapshot_id}", endpoint=handle_snapshot_by_id, methods=["GET"]),
            Route("/api/knowledge/search", endpoint=handle_knowledge_search, methods=["GET"]),
            Route("/api/knowledge/engagements", endpoint=handle_knowledge_engagements, methods=["GET"]),
            Route("/api/knowledge/suggestions", endpoint=handle_knowledge_suggestions, methods=["POST"]),
            Route("/api/compliance/conformity-snapshot", endpoint=handle_compliance_conformity_snapshot, methods=["GET"]),
            Route("/api/rfp/shred-to-candidates", endpoint=handle_rfp_shred_to_candidates, methods=["POST"]),
            Route("/api/documents/zero-draft-blueprint", endpoint=handle_zero_draft_blueprint, methods=["POST"]),
            Route("/api/prose/suggest-batch", endpoint=handle_prose_suggest_batch, methods=["POST"]),
            Route("/api/elicitation/trigger", endpoint=handle_elicitation_trigger, methods=["POST"]),
            Route("/api/elicitation/questions", endpoint=handle_elicitation_questions, methods=["GET"]),
            Route("/api/arbitration/board", endpoint=handle_arbitration_board, methods=["GET"]),
            Route("/api/arbitration/conflicts", endpoint=handle_arbitration_conflicts, methods=["GET"]),
            Route("/api/arbitration/statements", endpoint=handle_arbitration_statements, methods=["GET"]),
            Route("/api/skills", endpoint=handle_skills_list, methods=["GET"]),
            Route("/api/skills/matrix", endpoint=handle_skills_matrix, methods=["GET"]),
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
