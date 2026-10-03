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
        Route(f"{base}/questions", endpoint=questions, methods=["POST"]),
        Route(f"{base}/questions/{{question_id}}/answers", endpoint=answers, methods=["POST"]),
        Route(f"{base}/requirements", endpoint=requirements, methods=["POST"]),
        Route(f"{base}/conflicts/{{conflict_id}}/arbitrate", endpoint=arbitrate, methods=["POST"]),
    ]
