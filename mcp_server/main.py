"""Point d'entrée du serveur FastMCP pour la Base de Connaissances d'Architecture."""

import asyncio
import logging
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
    ENGAGEMENT_CREATE_SCOPE,
    Unauthorised,
    acting_member,
    authorise_action,
    caller_label,
    has_scope,
    open_access_warning,
    parse_engagement_tokens,
    set_current_actor_email,
    set_current_caller,
)
from mcp_server.core.config import server_config
from mcp_server.core.db import guard_engagement
from mcp_server.core.envelope import invalid_argument_response
from mcp_server.core.exceptions import InvalidEngagementIdError
from mcp_server.core.version import CONTRACT_VERSION
from mcp_server.engagement.export_routes import build_export_routes
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
from mcp_server.engagement.write_routes import build_write_routes
from mcp_server.knowledge.tools import (
    _suggest_knowledge_improvement,
    add_eval_case,
    add_ingestion_link_proposals,
    annotate_eval_case,
    annotate_similarity_case,
    apply_framework_ingestion,
    assign_kb_candidate,
    check_option,
    comment_kb_candidate,
    confirm_reuse,
    convert_verdict_feedback,
    create_framework_ingestion,
    decide_ingestion_row,
    declare_framework_coverage,
    generate_zero_draft_hld,
    get_asset,
    get_asset_template,
    get_assets,
    get_compliance_matrix,
    get_compliance_trail,
    get_decision_trail,
    get_doctrine_context,
    get_embeddings_pending,
    get_eval_dataset,
    get_eval_run,
    get_framework_coverage,
    get_framework_ingestion,
    get_glossary_term,
    get_governance_events,
    get_graph_summary,
    get_kb_candidate,
    get_kb_health,
    get_kb_me,
    get_principles_for,
    get_review_inbox,
    get_rfp_compliance_matrix,
    get_similarity_eval,
    get_similarity_eval_run,
    get_skills_matrix,
    list_assets,
    list_controls,
    list_domain_owners,
    list_framework_ingestions,
    list_frameworks,
    list_kb_candidates,
    list_kb_comments,
    list_reuse_confirmations,
    list_skills,
    list_trigger_rules,
    list_verdict_feedback,
    merge_fact_key_candidate,
    preview_triggers,
    promote_kb_candidate,
    publish_kb_candidates,
    put_embeddings,
    query_graph,
    request_kb_review,
    resolve_asset_reference,
    review_kb_candidate,
    run_eval,
    run_similarity_eval,
    search_assets,
    shred_rfp,
    similar_knowledge,
    simulate_checks,
    submit_kb_candidate,
    submit_verdict_feedback,
    suggest_knowledge_improvement,
    trigger_rfp_elicitation,
    update_domain_owners,
    validate_kb_candidate,
    validate_trigger_rule,
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
mcp.tool()(get_doctrine_context)
mcp.tool()(check_option)
mcp.tool()(submit_kb_candidate)
mcp.tool()(list_kb_candidates)
mcp.tool()(get_kb_candidate)
mcp.tool()(review_kb_candidate)
mcp.tool()(get_framework_coverage)
mcp.tool()(get_kb_me)
mcp.tool()(get_review_inbox)
mcp.tool()(assign_kb_candidate)
mcp.tool()(request_kb_review)
mcp.tool()(comment_kb_candidate)
mcp.tool()(list_domain_owners)

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
from datetime import UTC


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

        set_current_actor_email(request.headers.get("X-Actor-Email"))
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

        import os
        import subprocess

        engine_commit = os.environ.get("LLMOPS_COMMIT")
        if not engine_commit:
            try:
                engine_commit = subprocess.check_output(
                    ["git", "rev-parse", "--short", "HEAD"],
                    stderr=subprocess.DEVNULL,
                    text=True,
                ).strip()
            except Exception:
                engine_commit = "d7d3291"

        return JSONResponse(
            {
                "status": "ok",
                "plane": server_config.plane,
                "schema_version": CONTRACT_VERSION,
                "service": "llmops-mcp-server",
                "engine_version": "0.1.0",
                "engine_commit": engine_commit,
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
                    "schema_version": CONTRACT_VERSION,
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

    async def handle_knowledge_asset(request):
        """Citable resolution of one element from a sealed snapshot (K3): ``?version=`` and ``?snapshot=`` are optional."""
        res = resolve_asset_reference(
            request.path_params.get("asset_id", ""),
            version=request.query_params.get("version"),
            snapshot=request.query_params.get("snapshot"),
        )
        status_code = {"ok": 200, "not_found": 404, "invalid_argument": 400}.get(res.get("status"), 500)
        return JSONResponse(res, status_code=status_code)

    async def handle_knowledge_search(request):
        """Recherche REST d'assets dans le graphe de connaissances (Document Studio & clients HTTP)."""
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
            caller = getattr(request.state, "caller", None)
            for f in sorted(eng_dir.glob("*.lbug")):
                eid = f.stem
                if eid == "default":
                    continue
                try:  # K9: a token only sees the engagements its scopes cover
                    authorise_action(eid, "read", caller)
                except Unauthorised:
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
        source_system = (
            request.query_params.get("source_system")
            or request.headers.get("X-Source-System")
            or "knowledge-hub"
        ).strip()
        guard_engagement(engagement)  # K9

        try:
            from pipelines.compliance_mapper import to_conformity_snapshot
            snapshot = to_conformity_snapshot(
                engagement=engagement,
                framework=framework,
                controls_dir=server_config.kb_dir / "controls",
                source_system=source_system,
            )
            return JSONResponse(snapshot, status_code=200)
        except Exception as e:
            return JSONResponse(
                {"status": "error", "error": f"Échec de génération du ConformitySnapshot : {e}"},
                status_code=500,
            )

    async def handle_compliance_frameworks(request):
        """Liste les référentiels réglementaires disponibles dans la base de connaissances."""
        res = list_frameworks()
        status_code = 200 if res.get("status") == "ok" else 400
        return JSONResponse(res, status_code=status_code)

    async def handle_compliance_applicable_frameworks_get(request):
        """Récupère la liste des référentiels applicables pour un engagement donné."""
        engagement = (
            request.headers.get("X-Engagement-Id")
            or request.query_params.get("engagement")
            or "default"
        ).strip()
        from pipelines.compliance_mapper import (
            compute_framework_coverage,
            get_applicable_frameworks,
        )
        guard_engagement(engagement)  # K9
        fws = get_applicable_frameworks(engagement=engagement)
        payload: dict[str, Any] = {
            "status": "ok",
            "engagement": engagement,
            "applicable_frameworks": fws,
            "count": len(fws),
        }
        # Contract 1.3 (optional field): coverage of each applicable framework by the KB.
        try:
            payload["coverage"] = compute_framework_coverage(fws, server_config.kb_dir)
        except Exception:
            pass
        return JSONResponse(payload, status_code=200)

    async def handle_compliance_applicable_frameworks_put(request):
        """Définit la liste des référentiels applicables pour un engagement donné."""
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
        fws = body.get("frameworks", []) if isinstance(body, dict) else []
        from pipelines.compliance_mapper import set_applicable_frameworks
        guard_engagement(engagement, action="decide")  # K9/K14: the applicable frameworks frame the engagement
        res = set_applicable_frameworks(engagement=engagement, frameworks=fws)
        return JSONResponse(res, status_code=200)

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

        source_system = str(body.get("source_system") or "document-studio").strip()
        if source_system not in ("archinex", "document-studio", "mcp", "cli-ingestion"):
            source_system = "document-studio"
        res = _suggest_knowledge_improvement(
            system=source_system,
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
        destination = str(body.get("destination", "knowledge-hub-reference")).strip()

        if not rfp_text:
            return JSONResponse(
                {"status": "error", "error": "rfp_text ne peut pas être vide"},
                status_code=400,
            )

        try:
            from pipelines.rfp_shredder import RFPShredder, to_extracted_candidates

            shredder = RFPShredder(kb_dir="data/kb")
            requirements = shredder.shred_text(rfp_text, engagement=engagement)
            candidates = to_extracted_candidates(
                requirements,
                document_id,
                document_version,
                destination=destination,
            )

            return JSONResponse(
                {
                    "status": "ok",
                    "candidates": candidates,
                    "count": len(candidates),
                    "documentId": document_id,
                    "documentVersion": document_version,
                    "requirements": [r.to_dict() for r in requirements],
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
        guard_engagement(engagement)  # K9

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
        from datetime import datetime

        # The hub provides knowledge, never narrative: grounded excerpts of the doctrine or NO draft (a warning).
        from pipelines.prose_grounding import ground_block

        drafts: dict[str, str] = {}
        warnings: list[dict[str, str]] = []

        for req in requests:
            if not isinstance(req, dict):
                continue
            block_id = req.get("blockId", "")
            if not isinstance(block_id, str) or not block_id:
                continue
            draft, reason = ground_block(req, get_doctrine_context)
            if draft:
                drafts[block_id] = draft
            else:
                warnings.append({"blockId": block_id, "message": reason or "Aucun brouillon."})

        model_hash = hashlib.sha256(str(body).encode()).hexdigest()[:16]
        now_str = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

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

    def _query_list(request, name: str) -> list[str]:
        """List query parameter: repeated (?x=a&x=b) and/or comma-separated (?x=a,b)."""
        values: list[str] = []
        for raw in request.query_params.getlist(name):
            values.extend(v.strip() for v in raw.split(",") if v.strip())
        return values

    async def handle_knowledge_context(request):
        """Paquet de doctrine applicable à un sujet (déterministe, sans LLM)."""
        params = request.query_params
        try:
            max_items = int(params.get("max_items", "20"))
            max_chars = int(params.get("max_chars", "8000"))
        except ValueError:
            return JSONResponse(
                invalid_argument_response("max_items", "'max_items' and 'max_chars' must be integers."),
                status_code=400,
            )
        res = get_doctrine_context(
            subject=params.get("subject", ""),
            domains=_query_list(request, "domains"),
            frameworks=_query_list(request, "frameworks"),
            phase=params.get("phase"),
            max_items=max_items,
            max_chars=max_chars,
        )
        status_code = 200 if res.get("status") == "ok" else 400
        return JSONResponse(res, status_code=status_code)

    async def handle_knowledge_check(request):
        """Juge d'option : clauses de contrôle structurées de la doctrine (déterministe, sans LLM)."""
        try:
            body = await request.json()
        except Exception:
            body = None
        if not isinstance(body, dict):
            return JSONResponse(
                invalid_argument_response("body", "Le corps de requête doit être un objet JSON"),
                status_code=400,
            )
        res = check_option(
            option=body.get("option"),
            subject=body.get("subject"),
            domains=body.get("domains"),
            frameworks=body.get("frameworks"),
        )
        status_code = 200 if res.get("status") == "ok" else 400
        return JSONResponse(res, status_code=status_code)

    def _candidate_status_code(res: dict, ok_code: int = 200) -> int:
        status = res.get("status")
        if status == "ok":
            return ok_code
        if status == "not_found":
            return 404
        if status == "unauthorized":
            return 403
        if status == "unavailable":
            return 503
        if status == "invalid_argument":
            return 409 if res.get("conflict") else 400
        return 500

    async def handle_candidates_create(request):
        """Soumission d'un candidat d'enrichissement de la base (contrôles automatiques immédiats)."""
        try:
            body = await request.json()
        except Exception:
            body = None
        if not isinstance(body, dict):
            return JSONResponse(
                invalid_argument_response("body", "Le corps de requête doit être un objet JSON"), status_code=400
            )
        res = submit_kb_candidate(body)
        return JSONResponse(res, status_code=_candidate_status_code(res, ok_code=201))

    async def handle_candidates_list(request):
        """File des candidats (filtres : status, source, domain, engagement)."""
        params = request.query_params
        res = list_kb_candidates(
            status=params.get("status") or None,
            source=params.get("source") or None,
            domain=params.get("domain") or None,
            engagement=params.get("engagement") or None,
        )
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_candidate_get(request):
        res = get_kb_candidate(request.path_params["candidate_id"])
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_candidate_review(request):
        """Revue d'un candidat (scope de jeton kb:review requis)."""
        try:
            body = await request.json()
        except Exception:
            body = None
        if not isinstance(body, dict):
            return JSONResponse(
                invalid_argument_response("body", "Le corps de requête doit être un objet JSON"), status_code=400
            )
        res = review_kb_candidate(
            request.path_params["candidate_id"],
            action=str(body.get("action") or ""),
            reviewer=str(body.get("reviewer") or ""),
            reason=body.get("reason"),
            amended_content=body.get("amended_content"),
        )
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def _json_body(request):
        try:
            body = await request.json()
        except Exception:
            body = None
        return body if isinstance(body, dict) else None

    def _bad_body():
        return JSONResponse(
            invalid_argument_response("body", "Le corps de requête doit être un objet JSON"), status_code=400
        )

    async def handle_review_inbox(request):
        res = get_review_inbox()
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_candidate_assign(request):
        body = await _json_body(request)
        if body is None:
            return _bad_body()
        res = assign_kb_candidate(request.path_params["candidate_id"], str(body.get("handle") or ""),
                                  body.get("reason"))
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_candidate_request_review(request):
        body = await _json_body(request)
        if body is None:
            return _bad_body()
        res = request_kb_review(request.path_params["candidate_id"], str(body.get("handle") or ""),
                                str(body.get("kind") or "second_review"), body.get("message"), body.get("due_at"))
        return JSONResponse(res, status_code=_candidate_status_code(res, ok_code=201))

    async def handle_candidate_comment_create(request):
        body = await _json_body(request)
        if body is None:
            return _bad_body()
        res = comment_kb_candidate(request.path_params["candidate_id"], str(body.get("body") or ""))
        return JSONResponse(res, status_code=_candidate_status_code(res, ok_code=201))

    async def handle_candidate_comments_list(request):
        res = list_kb_comments(request.path_params["candidate_id"])
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_governance_events(request):
        params = request.query_params
        try:
            since, limit = int(params.get("since") or 0), int(params.get("limit") or 100)
        except ValueError:
            return JSONResponse(invalid_argument_response("since", "'since' and 'limit' must be integers"),
                                status_code=400)
        res = get_governance_events(since, limit)
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_owners_list(request):
        res = list_domain_owners()
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_owners_update(request):
        body = await _json_body(request)
        if body is None:
            return _bad_body()
        res = update_domain_owners(body)
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_template(request):
        res = get_asset_template(request.path_params["asset_type"])
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_candidate_validate(request):
        body = await _json_body(request)
        if body is None:
            return _bad_body()
        res = validate_kb_candidate(body)
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_trigger_rules(request):
        res = list_trigger_rules()
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_trigger_validate(request):
        body = await _json_body(request)
        if body is None:
            return _bad_body()
        res = validate_trigger_rule(body)
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_trigger_preview(request):
        body = await _json_body(request)
        if body is None:
            return _bad_body()
        res = preview_triggers(body)
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_merge_key(request):
        body = await _json_body(request)
        if body is None:
            return _bad_body()
        res = merge_fact_key_candidate(request.path_params["candidate_id"], str(body.get("into") or ""),
                                       str(body.get("reviewer") or ""), body.get("reason"))
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_checks_simulate(request):
        body = await _json_body(request)
        if body is None:
            return _bad_body()
        res = simulate_checks(body)
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_eval_dataset(request):
        res = get_eval_dataset(request.path_params["dataset"])
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_eval_case_annotate(request):
        body = await _json_body(request)
        if body is None:
            return _bad_body()
        res = annotate_eval_case(request.path_params["dataset"], request.path_params["case_id"], body)
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_eval_case_add(request):
        body = await _json_body(request)
        if body is None:
            return _bad_body()
        res = add_eval_case(request.path_params["dataset"], body)
        return JSONResponse(res, status_code=_candidate_status_code(res, ok_code=201))

    async def handle_eval_run_create(request):
        body = await _json_body(request) or {}
        res = run_eval(request.path_params["dataset"], bool(body.get("validated_only")))
        return JSONResponse(res, status_code=_candidate_status_code(res, ok_code=201))

    async def handle_eval_run_get(request):
        try:
            run_id = int(request.path_params["run_id"])
        except ValueError:
            return JSONResponse(invalid_argument_response("run_id", "'run_id' must be an integer"), status_code=400)
        res = get_eval_run(request.path_params["dataset"], run_id)
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_feedback_create(request):
        body = await _json_body(request)
        if body is None:
            return _bad_body()
        res = submit_verdict_feedback(body)
        return JSONResponse(res, status_code=_candidate_status_code(res, ok_code=201))

    async def handle_feedback_list(request):
        res = list_verdict_feedback(request.query_params.get("status") or None)
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_feedback_convert(request):
        body = await _json_body(request)
        if body is None:
            return _bad_body()
        try:
            feedback_id = int(request.path_params["feedback_id"])
        except ValueError:
            return JSONResponse(invalid_argument_response("feedback_id", "must be an integer"), status_code=400)
        res = convert_verdict_feedback(feedback_id, body)
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_ingestion_create(request):
        try:
            form = await request.form()
        except Exception:
            return JSONResponse(invalid_argument_response("body", "multipart/form-data expected"), status_code=400)
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            return JSONResponse(invalid_argument_response("file", "'file' is required (multipart field)"), status_code=400)
        data = await upload.read(21 * 1024 * 1024)
        res = create_framework_ingestion(str(form.get("framework") or ""), str(form.get("version") or ""),
                                         str(form.get("tag") or ""), getattr(upload, "filename", "") or "", data)
        return JSONResponse(res, status_code=_candidate_status_code(res, ok_code=201))

    async def handle_ingestion_list(request):
        res = list_framework_ingestions()
        return JSONResponse(res, status_code=_candidate_status_code(res))

    def _ingestion_id(request):
        try:
            return int(request.path_params["ingestion_id"])
        except ValueError:
            return None

    async def handle_ingestion_get(request):
        ingestion_id = _ingestion_id(request)
        if ingestion_id is None:
            return JSONResponse(invalid_argument_response("ingestion_id", "must be an integer"), status_code=400)
        res = get_framework_ingestion(ingestion_id)
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_ingestion_row(request):
        ingestion_id, body = _ingestion_id(request), await _json_body(request)
        if ingestion_id is None or body is None:
            return _bad_body()
        res = decide_ingestion_row(ingestion_id, request.path_params["requirement_id"], body)
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_ingestion_proposals(request):
        ingestion_id, body = _ingestion_id(request), await _json_body(request)
        if ingestion_id is None or body is None:
            return _bad_body()
        res = add_ingestion_link_proposals(ingestion_id, body)
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_ingestion_apply(request):
        ingestion_id = _ingestion_id(request)
        if ingestion_id is None:
            return _bad_body()
        res = apply_framework_ingestion(ingestion_id)
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_coverage_declaration(request):
        res = declare_framework_coverage(request.path_params["framework"])
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_candidate_promote(request):
        res = promote_kb_candidate(request.path_params["candidate_id"])
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_publications_create(request):
        res = publish_kb_candidates()
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_kb_health(request):
        res = get_kb_health()
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_embeddings_pending(request):
        res = get_embeddings_pending(request.query_params.get("model") or "")
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_embeddings_put(request):
        body = await _json_body(request)
        if body is None:
            return _bad_body()
        res = put_embeddings(body)
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_similar(request):
        body = await _json_body(request)
        if body is None:
            return _bad_body()
        res = similar_knowledge(body)
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_reuse_confirm(request):
        body = await _json_body(request)
        if body is None:
            return _bad_body()
        res = confirm_reuse(body)
        return JSONResponse(res, status_code=_candidate_status_code(res, ok_code=201))

    async def handle_reuse_list(request):
        q = request.query_params
        res = list_reuse_confirmations(q.get("matched_ref"), q.get("outcome"), q.get("subject_fingerprint"))
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_simeval_get(request):
        res = get_similarity_eval(request.path_params["dataset"])
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_simeval_annotate(request):
        body = await _json_body(request)
        if body is None:
            return _bad_body()
        res = annotate_similarity_case(request.path_params["dataset"], request.path_params["case_id"], body)
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_simeval_run(request):
        body = await _json_body(request)
        if body is None:
            return _bad_body()
        res = run_similarity_eval(request.path_params["dataset"], body)
        return JSONResponse(res, status_code=_candidate_status_code(res, ok_code=201))

    async def handle_simeval_run_get(request):
        try:
            run_id = int(request.path_params["run_id"])
        except ValueError:
            return JSONResponse(invalid_argument_response("run_id", "must be an integer"), status_code=400)
        res = get_similarity_eval_run(request.path_params["dataset"], run_id)
        return JSONResponse(res, status_code=_candidate_status_code(res))

    async def handle_kb_me(request):
        """Expert au nom duquel le client agit (jeton kb:delegate + X-Actor-Email)."""
        res = get_kb_me()
        return JSONResponse(res, status_code=_candidate_status_code(res))

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
        blueprint_path = request.query_params.get("blueprint_path") or None
        res = get_skills_matrix(engagement=engagement, blueprint_path=blueprint_path)
        status_code = 200 if res.get("status") == "ok" else 400
        return JSONResponse(res, status_code=status_code)

    async def handle_invalid_engagement(request, exc):
        """K9: a malformed engagement identifier is a 400 in the usual envelope."""
        return JSONResponse(
            {"status": "invalid_argument", "argument": "engagement", "reason": str(exc)},
            status_code=400,
        )


    # --- Engagement access (K14, ADR-KH-01 A11) -----------------------------------------------------------------

    def _access_or_503():
        from pipelines.engagement.access import get_access

        access = get_access()
        if access is None:
            return None, JSONResponse(
                {"status": "error", "error": "governance_database_required",
                 "message": "Managed engagements need a governance database (GOVERNANCE_DATABASE_URL or CANDIDATES_BACKEND=sql)."},
                status_code=503)
        return access, None

    def _access_error(err):
        return JSONResponse({"status": "invalid_argument", "argument": err.argument, "reason": err.reason}, status_code=400)

    async def handle_engagement_create(request):
        """Create a managed engagement with its first admin. Operator token (``server_admin``) or scope ``eng:create``."""
        from pipelines.engagement.access import AccessError

        caller = getattr(request.state, "caller", "")
        if caller != "server_admin" and not has_scope(ENGAGEMENT_CREATE_SCOPE, caller):
            return JSONResponse({"status": "error", "error": "forbidden", "reason": "eng_create_scope_required"}, status_code=403)
        access, failure = _access_or_503()
        if failure:
            return failure
        try:
            body = await request.json()
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        try:
            created = access.create(
                str(body.get("engagement", "")), str(body.get("confidentiality", "")),
                body.get("admin_email", ""), str(body.get("admin_handle", "")), caller_label(caller))
        except AccessError as err:
            return JSONResponse({"status": "invalid_argument", "argument": err.argument, "reason": err.reason},
                                status_code=409 if "already exists" in err.reason else 400)
        for m in created["members"]:
            m.pop("email", None)  # e-mails never leave the registry through a response either
        return JSONResponse({"status": "ok", "data": created}, status_code=201)

    async def handle_engagement_members(request):
        """GET: the members (handles and roles; e-mails only to an admin member). PUT: replace the list (role admin)."""
        from pipelines.engagement.access import AccessError

        engagement = request.path_params["engagement"]
        guard_engagement(engagement, action="members")
        access, failure = _access_or_503()
        if failure:
            return failure
        if not access.is_managed(engagement):
            return JSONResponse({"status": "not_found", "id": engagement, "reason": "not_managed"}, status_code=404)
        if request.method == "PUT":
            try:
                body = await request.json()
                members = access.replace_members(engagement, body.get("members") if isinstance(body, dict) else None,
                                                 (acting_member(engagement) or {}).get("handle") or caller_label(request.state.caller))
            except AccessError as err:
                return _access_error(err)
            return JSONResponse({"status": "ok", "data": {"engagement": engagement, "members": members}})
        return JSONResponse({"status": "ok", "data": {"engagement": engagement, "members": access.members(engagement)}})

    async def handle_engagement_me(request):
        """The caller's own role on an engagement: managed or not, role, allowed actions."""
        from pipelines.engagement.access import ROLE_ACTIONS, get_access

        engagement = request.path_params["engagement"]
        guard_engagement(engagement, action="read")
        access = get_access()
        if access is None or not access.is_managed(engagement):
            return JSONResponse({"status": "ok", "data": {"engagement": engagement, "managed": False, "handle": None,
                                                           "role": None, "actions": [], "confidentiality": None}})
        member = acting_member(engagement)
        role = member["role"] if member else None
        return JSONResponse({"status": "ok", "data": {
            "engagement": engagement, "managed": True, "handle": member["handle"] if member else None, "role": role,
            "actions": sorted(ROLE_ACTIONS[role]) if role else ["read"],  # a read-only service token has no role
            "confidentiality": access.confidentiality(engagement)}})

    async def handle_engagement_audit(request):
        """The access journal of an engagement (role admin): refusals and every non-read action."""
        engagement = request.path_params["engagement"]
        guard_engagement(engagement, action="members")
        access, failure = _access_or_503()
        if failure:
            return failure
        limit = int(request.query_params.get("limit", "100") or 100)
        return JSONResponse({"status": "ok", "data": {"engagement": engagement, "events": access.audit_events(engagement, limit)}})

    async def handle_unauthorised(request, exc):
        """K9: a caller outside the scopes of an engagement gets a 403 in the usual error envelope, never a 500."""
        body = {
            "status": "error",
            "error": "forbidden",
            "message": "The token is not authorised for this engagement",
            "engagement": exc.engagement,
        }
        if getattr(exc, "reason", None):  # K14: the role a managed engagement requires
            body.update(action=exc.action, reason=exc.reason, message="The caller lacks the role this action requires")
        return JSONResponse(body, status_code=403)

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
            Route("/api/knowledge/assets/{asset_id}", endpoint=handle_knowledge_asset, methods=["GET"]),
            Route("/api/knowledge/search", endpoint=handle_knowledge_search, methods=["GET"]),
            Route("/api/knowledge/engagements", endpoint=handle_knowledge_engagements, methods=["GET"]),
            Route("/api/engagements", endpoint=handle_engagement_create, methods=["POST"]),
            Route("/api/engagements/{engagement}/members", endpoint=handle_engagement_members, methods=["GET", "PUT"]),
            Route("/api/engagements/{engagement}/me", endpoint=handle_engagement_me, methods=["GET"]),
            Route("/api/engagements/{engagement}/audit", endpoint=handle_engagement_audit, methods=["GET"]),
            *build_write_routes(),  # K15
            *build_export_routes(),  # K11
            Route("/api/knowledge/suggestions", endpoint=handle_knowledge_suggestions, methods=["POST"]),
            Route("/api/compliance/conformity-snapshot", endpoint=handle_compliance_conformity_snapshot, methods=["GET"]),
            Route("/api/compliance/frameworks", endpoint=handle_compliance_frameworks, methods=["GET"]),
            Route("/api/compliance/frameworks/applicable", endpoint=handle_compliance_applicable_frameworks_get, methods=["GET"]),
            Route("/api/compliance/frameworks/applicable", endpoint=handle_compliance_applicable_frameworks_put, methods=["PUT", "POST"]),
            Route("/api/rfp/shred-to-candidates", endpoint=handle_rfp_shred_to_candidates, methods=["POST"]),
            Route("/api/documents/zero-draft-blueprint", endpoint=handle_zero_draft_blueprint, methods=["POST"]),
            Route("/api/prose/suggest-batch", endpoint=handle_prose_suggest_batch, methods=["POST"]),
            Route("/api/elicitation/trigger", endpoint=handle_elicitation_trigger, methods=["POST"]),
            Route("/api/elicitation/questions", endpoint=handle_elicitation_questions, methods=["GET"]),
            Route("/api/arbitration/board", endpoint=handle_arbitration_board, methods=["GET"]),
            Route("/api/arbitration/conflicts", endpoint=handle_arbitration_conflicts, methods=["GET"]),
            Route("/api/arbitration/statements", endpoint=handle_arbitration_statements, methods=["GET"]),
            Route("/api/knowledge/context", endpoint=handle_knowledge_context, methods=["GET"]),
            Route("/api/knowledge/check", endpoint=handle_knowledge_check, methods=["POST"]),
            Route("/api/knowledge/me", endpoint=handle_kb_me, methods=["GET"]),
            Route("/api/knowledge/embeddings/pending", endpoint=handle_embeddings_pending, methods=["GET"]),
            Route("/api/knowledge/embeddings", endpoint=handle_embeddings_put, methods=["PUT"]),
            Route("/api/knowledge/similar", endpoint=handle_similar, methods=["POST"]),
            Route("/api/knowledge/similarity-evals/{dataset}", endpoint=handle_simeval_get, methods=["GET"]),
            Route("/api/knowledge/similarity-evals/{dataset}/cases/{case_id}", endpoint=handle_simeval_annotate,
                  methods=["PATCH"]),
            Route("/api/knowledge/similarity-evals/{dataset}/runs", endpoint=handle_simeval_run, methods=["POST"]),
            Route("/api/knowledge/similarity-evals/{dataset}/runs/{run_id}", endpoint=handle_simeval_run_get,
                  methods=["GET"]),
            Route("/api/knowledge/reuse-confirmations", endpoint=handle_reuse_confirm, methods=["POST"]),
            Route("/api/knowledge/reuse-confirmations", endpoint=handle_reuse_list, methods=["GET"]),
            Route("/api/knowledge/health", endpoint=handle_kb_health, methods=["GET"]),
            Route("/api/knowledge/publications", endpoint=handle_publications_create, methods=["POST"]),
            Route("/api/knowledge/candidates/{candidate_id}/promote", endpoint=handle_candidate_promote,
                  methods=["POST"]),
            Route("/api/frameworks/ingestions", endpoint=handle_ingestion_create, methods=["POST"]),
            Route("/api/frameworks/ingestions", endpoint=handle_ingestion_list, methods=["GET"]),
            Route("/api/frameworks/ingestions/{ingestion_id}", endpoint=handle_ingestion_get, methods=["GET"]),
            Route("/api/frameworks/ingestions/{ingestion_id}/rows/{requirement_id}", endpoint=handle_ingestion_row,
                  methods=["PATCH"]),
            Route("/api/frameworks/ingestions/{ingestion_id}/link-proposals", endpoint=handle_ingestion_proposals,
                  methods=["POST"]),
            Route("/api/frameworks/ingestions/{ingestion_id}/apply", endpoint=handle_ingestion_apply, methods=["POST"]),
            Route("/api/frameworks/{framework}/coverage-declaration", endpoint=handle_coverage_declaration,
                  methods=["POST"]),
            Route("/api/knowledge/templates/{asset_type}", endpoint=handle_template, methods=["GET"]),
            Route("/api/knowledge/candidates/validate", endpoint=handle_candidate_validate, methods=["POST"]),
            Route("/api/knowledge/triggers", endpoint=handle_trigger_rules, methods=["GET"]),
            Route("/api/knowledge/triggers/validate", endpoint=handle_trigger_validate, methods=["POST"]),
            Route("/api/knowledge/triggers/preview", endpoint=handle_trigger_preview, methods=["POST"]),
            Route("/api/knowledge/candidates/{candidate_id}/merge-key", endpoint=handle_merge_key, methods=["POST"]),
            Route("/api/knowledge/checks/simulate", endpoint=handle_checks_simulate, methods=["POST"]),
            Route("/api/knowledge/evals/{dataset}", endpoint=handle_eval_dataset, methods=["GET"]),
            Route("/api/knowledge/evals/{dataset}/cases", endpoint=handle_eval_case_add, methods=["POST"]),
            Route("/api/knowledge/evals/{dataset}/cases/{case_id}", endpoint=handle_eval_case_annotate, methods=["PATCH"]),
            Route("/api/knowledge/evals/{dataset}/runs", endpoint=handle_eval_run_create, methods=["POST"]),
            Route("/api/knowledge/evals/{dataset}/runs/{run_id}", endpoint=handle_eval_run_get, methods=["GET"]),
            Route("/api/knowledge/verdict-feedback", endpoint=handle_feedback_create, methods=["POST"]),
            Route("/api/knowledge/verdict-feedback", endpoint=handle_feedback_list, methods=["GET"]),
            Route("/api/knowledge/verdict-feedback/{feedback_id}/convert", endpoint=handle_feedback_convert,
                  methods=["POST"]),
            Route("/api/knowledge/reviews/inbox", endpoint=handle_review_inbox, methods=["GET"]),
            Route("/api/knowledge/events", endpoint=handle_governance_events, methods=["GET"]),
            Route("/api/knowledge/owners", endpoint=handle_owners_list, methods=["GET"]),
            Route("/api/knowledge/owners", endpoint=handle_owners_update, methods=["PUT"]),
            Route("/api/knowledge/candidates/{candidate_id}/assign", endpoint=handle_candidate_assign, methods=["POST"]),
            Route("/api/knowledge/candidates/{candidate_id}/request-review",
                  endpoint=handle_candidate_request_review, methods=["POST"]),
            Route("/api/knowledge/candidates/{candidate_id}/comments",
                  endpoint=handle_candidate_comment_create, methods=["POST"]),
            Route("/api/knowledge/candidates/{candidate_id}/comments",
                  endpoint=handle_candidate_comments_list, methods=["GET"]),
            Route("/api/knowledge/candidates", endpoint=handle_candidates_create, methods=["POST"]),
            Route("/api/knowledge/candidates", endpoint=handle_candidates_list, methods=["GET"]),
            Route("/api/knowledge/candidates/{candidate_id}", endpoint=handle_candidate_get, methods=["GET"]),
            Route("/api/knowledge/candidates/{candidate_id}", endpoint=handle_candidate_review, methods=["PATCH"]),
            Route("/api/skills", endpoint=handle_skills_list, methods=["GET"]),
            Route("/api/skills/matrix", endpoint=handle_skills_matrix, methods=["GET"]),
        ],
        middleware=[Middleware(AuthMiddleware)],
        exception_handlers={Unauthorised: handle_unauthorised, InvalidEngagementIdError: handle_invalid_engagement},
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
        from pipelines.governance.bootstrap import ensure_governance_ready

        ensure_governance_ready(server_config.kb_dir)
        expected_token = os.getenv("SERVER_TOKEN") or os.getenv("LLMOPS_AUTH_TOKEN") or settings.AUTH_TOKEN
        if not expected_token or not expected_token.strip():
            raise RuntimeError(
                "CRITICAL SECURITY FAILURE: SERVER_TOKEN or LLMOPS_AUTH_TOKEN environment variable must be set to start the HTTP/SSE server. Refusing to run in unauthenticated mode."
            )
        warning = open_access_warning()
        if warning:
            logging.getLogger("mcp_server.auth").warning(warning)
        asyncio.run(run_sse_authenticated(host=host, port=port))
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
