"""REST routes that write into a managed engagement (K15). Every route is gated by the roles of K14 and attributes the
write to the member behind the call (see ``pipelines/engagement/write.py``)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from starlette.responses import JSONResponse
from starlette.routing import Route

from mcp_server.core.auth import acting_member
from mcp_server.core.db import get_engagement_path, guard_engagement
from pipelines.engagement.access import get_access
from pipelines.engagement.write import EngagementWriter, WriteError
from tools.elicitation.repository import ElicitationRepository

DECIDING_ROLES = ("decider", "admin")


async def _handle(request, action: str, work: Callable[[EngagementWriter, dict[str, Any], dict[str, str]], tuple[int, dict[str, Any]]]):
    engagement = request.path_params["engagement"]
    guard_engagement(engagement, action=action)  # token scopes, then the member's role; 403 / 400 are raised
    access = get_access()
    if access is None or not access.is_managed(engagement):
        return JSONResponse(
            {"status": "error", "error": "engagement_not_managed",
             "reason": "Writes need a managed engagement (POST /api/engagements): attribution and roles depend on it."},
            status_code=409)
    member = acting_member(engagement)
    if member is None:  # cannot happen after authorise_action for a write; kept as a refusal, never a guess
        return JSONResponse({"status": "error", "error": "forbidden", "reason": "actor_required"}, status_code=403)
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    repo = ElicitationRepository(db_path=get_engagement_path(engagement))
    try:
        status, data = work(EngagementWriter(repo, engagement, member["handle"]), body, member)
    except WriteError as err:
        return JSONResponse(err.body(), status_code=err.status)
    finally:
        repo.close()
    return JSONResponse({"status": "ok", "data": data}, status_code=status)


def _created(result: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    return (201 if result.get("created") else 200), result


async def _import(request):
    """Import a batch from another system (K12), role ``admin``. ``?dry_run=true`` writes nothing."""
    from pipelines.engagement.importer import Importer
    from pipelines.engagement.write import KEY

    engagement = request.path_params["engagement"]
    guard_engagement(engagement, action="import")
    access = get_access()
    if access is None or not access.is_managed(engagement):
        return JSONResponse({"status": "error", "error": "engagement_not_managed",
                             "reason": "An import needs a managed engagement (POST /api/engagements)."}, status_code=409)
    member = acting_member(engagement)
    if member is None:
        return JSONResponse({"status": "error", "error": "forbidden", "reason": "actor_required"}, status_code=403)
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    batch_id = body.get("batch_id")
    if not isinstance(batch_id, str) or not KEY.match(batch_id):
        return JSONResponse({"status": "invalid_argument", "argument": "batch_id",
                             "reason": "'batch_id' is required (letters, digits . _ : -)"}, status_code=400)
    dry_run = request.query_params.get("dry_run", "").lower() in ("1", "true", "yes") or body.get("dry_run") is True
    partial = body.get("allow_partial") is True
    members = {m["handle"]: m["role"] for m in access.members(engagement)}
    repo = ElicitationRepository(db_path=get_engagement_path(engagement))
    try:
        importer = Importer(repo, engagement, members, batch_id)
        try:
            plan = importer.plan(body)
        except WriteError as err:
            return JSONResponse(err.body(), status_code=err.status)
        applied = False
        extra: dict = {}
        if not dry_run and (not plan.rejected or partial):
            extra = importer.apply(plan)
            applied = True
            access.audit(engagement, member["handle"], "import", "allowed", {
                "batch_id": batch_id, "accepted": len(plan.accepted), "unchanged": len(plan.unchanged),
                "adjusted": len(plan.adjusted), "rejected": len(plan.rejected)})
    finally:
        repo.close()
    report = {
        "batch_id": batch_id, "dry_run": dry_run, "applied": applied,
        "counts": {"accepted": len(plan.accepted), "unchanged": len(plan.unchanged), "adjusted": len(plan.adjusted),
                   "rejected": len(plan.rejected)},
        "accepted": plan.accepted, "unchanged": plan.unchanged, "adjusted": plan.adjusted, "rejected": plan.rejected,
        **extra,
    }
    if dry_run:
        report["notes"] = ["A dry run does not simulate the conflict detection run on asserted statements."]
    if plan.rejected and not dry_run and not partial:
        return JSONResponse({"status": "error", "error": "import_refused",
                             "reason": f"{len(plan.rejected)} item(s) rejected: nothing was written", "data": report}, status_code=422)
    return JSONResponse({"status": "ok", "data": report})


def build_write_routes() -> list[Route]:
    base = "/api/engagements/{engagement}"

    async def subjects(request):
        return await _handle(request, "contribute", lambda w, b, m: _created(w.add_subject(b)))

    async def maturity(request):
        name = request.path_params["name"]
        return await _handle(request, "decide", lambda w, b, m: (200, w.advance_subject(name, b)))

    async def statements(request):
        key = request.headers.get("Idempotency-Key")
        return await _handle(request, "contribute", lambda w, b, m: _created(w.add_statement(b, key)))

    async def assert_statement(request):
        sid = request.path_params["statement_id"]
        return await _handle(request, "decide", lambda w, b, m: (200, w.assert_statement(sid)))

    async def withdraw_statement(request):
        sid = request.path_params["statement_id"]
        return await _handle(request, "contribute",
                             lambda w, b, m: (200, w.withdraw_statement(sid, m["role"] in DECIDING_ROLES)))

    async def decisions(request):
        key = request.headers.get("Idempotency-Key")
        return await _handle(request, "contribute", lambda w, b, m: _created(w.add_decision(b, key)))

    async def assert_decision(request):
        did = request.path_params["decision_id"]
        return await _handle(request, "decide", lambda w, b, m: (200, w.assert_decision(did)))

    async def withdraw_decision(request):
        did = request.path_params["decision_id"]
        return await _handle(request, "contribute",
                             lambda w, b, m: (200, w.withdraw_decision(did, m["role"] in DECIDING_ROLES)))

    async def questions(request):
        key = request.headers.get("Idempotency-Key")
        return await _handle(request, "contribute", lambda w, b, m: _created(w.add_question(b, key)))

    async def answers(request):
        qid = request.path_params["question_id"]
        key = request.headers.get("Idempotency-Key")
        return await _handle(request, "contribute", lambda w, b, m: _created(w.answer_question(qid, b, key)))

    async def requirements(request):
        return await _handle(request, "contribute", lambda w, b, m: (200, w.add_requirements(b)))

    async def arbitrate(request):
        cid = request.path_params["conflict_id"]
        return await _handle(request, "decide", lambda w, b, m: (200, w.arbitrate(cid, b)))

    return [
        Route(f"{base}/subjects", endpoint=subjects, methods=["POST"]),
        Route(f"{base}/subjects/{{name}}/maturity", endpoint=maturity, methods=["POST"]),
        Route(f"{base}/statements", endpoint=statements, methods=["POST"]),
        Route(f"{base}/statements/{{statement_id}}/assert", endpoint=assert_statement, methods=["POST"]),
        Route(f"{base}/statements/{{statement_id}}/withdraw", endpoint=withdraw_statement, methods=["POST"]),
        Route(f"{base}/import", endpoint=_import, methods=["POST"]),
        Route(f"{base}/decisions", endpoint=decisions, methods=["POST"]),
        Route(f"{base}/decisions/{{decision_id}}/assert", endpoint=assert_decision, methods=["POST"]),
        Route(f"{base}/decisions/{{decision_id}}/withdraw", endpoint=withdraw_decision, methods=["POST"]),
        Route(f"{base}/questions", endpoint=questions, methods=["POST"]),
        Route(f"{base}/questions/{{question_id}}/answers", endpoint=answers, methods=["POST"]),
        Route(f"{base}/requirements", endpoint=requirements, methods=["POST"]),
        Route(f"{base}/conflicts/{{conflict_id}}/arbitrate", endpoint=arbitrate, methods=["POST"]),
    ]
