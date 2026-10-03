"""REST routes for the sealed engagement snapshot (K11): issue (role admin), list and fetch (any reader)."""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.routing import Route

from mcp_server.core.auth import acting_member
from mcp_server.core.db import get_engagement_path, guard_engagement
from pipelines import canonical
from pipelines.engagement.access import get_access
from pipelines.engagement.snapshot import ExportRefused, export_engagement, snapshot_ref
from tools.elicitation.repository import ElicitationRepository


def _not_managed():
    return JSONResponse({"status": "error", "error": "engagement_not_managed",
                         "reason": "Only a managed engagement has a snapshot (POST /api/engagements)."}, status_code=409)


def build_export_routes() -> list[Route]:
    base = "/api/engagements/{engagement}/exports"

    async def issue(request):
        """Issue the sealed snapshot of the engagement toward the suite. The same state gives the same snapshot (200)."""
        from mcp_server.knowledge import tools as knowledge_tools

        engagement = request.path_params["engagement"]
        guard_engagement(engagement, action="export")
        access = get_access()
        if access is None or not access.is_managed(engagement):
            return _not_managed()
        member = acting_member(engagement)
        if member is None:
            return JSONResponse({"status": "error", "error": "forbidden", "reason": "actor_required"}, status_code=403)
        repo = ElicitationRepository(db_path=get_engagement_path(engagement))
        try:
            envelope, created = export_engagement(access, repo, engagement, member["handle"], knowledge_tools.SNAPSHOTS_DIR)
        except ExportRefused as err:
            return JSONResponse(
                {"status": "error", "error": err.code, "reason": str(err),
                 "problems": [{"code": p.code, "path": p.path, "message": p.message} for p in err.problems]},
                status_code=409 if err.code == "engagement_not_managed" else 422)
        finally:
            repo.close()
        return JSONResponse({"status": "ok", "data": {
            "snapshotRef": snapshot_ref(envelope), "created": created, "is_provisional": envelope["data"]["is_provisional"]}},
            status_code=201 if created else 200)

    async def listing(request):
        engagement = request.path_params["engagement"]
        guard_engagement(engagement, action="read")
        access = get_access()
        if access is None or not access.is_managed(engagement):
            return _not_managed()
        return JSONResponse({"status": "ok", "data": {"engagement": engagement, "exports": access.list_exports(engagement)}})

    async def fetch(request):
        engagement = request.path_params["engagement"]
        guard_engagement(engagement, action="read")
        access = get_access()
        if access is None or not access.is_managed(engagement):
            return _not_managed()
        stored = access.get_export(request.path_params["snapshot_id"])
        if stored is None or stored["engagement"] != engagement:  # another engagement's snapshot is not disclosed
            return JSONResponse({"status": "not_found", "error": "unknown_snapshot", "id": request.path_params["snapshot_id"]}, status_code=404)
        envelope = stored["envelope"]
        if canonical.sha256(envelope["data"]) != envelope["checksum"]:
            return JSONResponse({"status": "error", "error": "snapshot_corrupt",
                                 "reason": "the stored content does not match its checksum"}, status_code=500)
        return JSONResponse(envelope, headers={"ETag": envelope["checksum"], "Cache-Control": "private, max-age=86400"})

    return [
        Route(base, endpoint=issue, methods=["POST"]),
        Route(base, endpoint=listing, methods=["GET"]),
        Route(f"{base}/{{snapshot_id}}", endpoint=fetch, methods=["GET"]),
    ]
