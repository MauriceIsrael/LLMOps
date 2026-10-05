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


def cascade_of(repo, access, engagement: str, actor: str):
    """The cascade engine of K20 as the callable a writer runs after a decision changes."""
    from mcp_server.knowledge import tools as knowledge_tools
    from pipelines.engagement.cascade import Cascade

    return lambda: Cascade(repo, access, engagement, knowledge_tools.SNAPSHOTS_DIR, actor).run()


def _adjuster(repo, access, engagement: str, actor: str, cascade=None):
    from mcp_server.knowledge import tools as knowledge_tools
    from pipelines.engagement.rules import RuleAdjuster

    return RuleAdjuster(repo, access, engagement, actor, knowledge_tools.SNAPSHOTS_DIR, cascade)


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
        cascade = cascade_of(repo, access, engagement, member["handle"])
        writer = EngagementWriter(repo, engagement, member["handle"], cascade)
        writer.rules = _adjuster(repo, access, engagement, member["handle"], cascade)  # K21
        status, data = work(writer, body, member)
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
            extra["cascade"] = cascade_of(repo, access, engagement, member["handle"])()  # K20: replaying creates nothing more
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


async def _facts(request):
    """The facts in force of an engagement (K18): only those of asserted decisions, each with its decision."""
    from pipelines.engagement.facts import in_force

    engagement = request.path_params["engagement"]
    guard_engagement(engagement, action="read")
    repo = ElicitationRepository(db_path=get_engagement_path(engagement))
    try:
        return JSONResponse({"status": "ok", "data": in_force(repo.list_decisions(engagement))})
    finally:
        repo.close()


async def _rules(request):
    """The rules an engagement reads (K21): the reference rules of its pinned base, which are deactivated, and its local rules."""
    engagement = request.path_params["engagement"]
    guard_engagement(engagement, action="read")
    access = get_access()
    if access is None or not access.is_managed(engagement):
        return JSONResponse({"status": "error", "error": "engagement_not_managed", "reason": "Rules need a managed engagement."}, status_code=409)
    repo = ElicitationRepository(db_path=get_engagement_path(engagement))
    try:
        return JSONResponse({"status": "ok", "data": _adjuster(repo, access, engagement, "", None).overview()})
    except WriteError as err:
        return JSONResponse(err.body(), status_code=err.status)
    finally:
        repo.close()


async def _lineage(request):
    """The derivation tree of an engagement (K20): subjects the cascade opened, from which decision, by which rule and facts."""
    from mcp_server.knowledge import tools as knowledge_tools
    from pipelines.engagement.cascade import lineage_items, lineage_tree, pinned_snapshot

    engagement = request.path_params["engagement"]
    guard_engagement(engagement, action="read")
    access = get_access()
    repo = ElicitationRepository(db_path=get_engagement_path(engagement))
    try:
        snapshot, reason = (None, "not_managed") if access is None else pinned_snapshot(
            access, engagement, knowledge_tools.SNAPSHOTS_DIR, "", create=False)
        items = lineage_items(repo.list_derived_subjects(engagement), snapshot, repo.list_adjustments(engagement))
        for item in items:
            question = repo.get_question(item["question_id"]) if item["question_id"] else None
            item["question_status"] = question["status"] if question else None
        pin = access.get_pin(engagement) if access else None
        return JSONResponse({"status": "ok", "data": {
            "kb_snapshot": pin, "pin_unavailable": reason if pin and snapshot is None else None,
            "derived": items, "tree": lineage_tree(items)}})
    finally:
        repo.close()


async def _kb_pin(request):
    """Move the knowledge snapshot an engagement is read against (K20), role ``admin``; the cascade then re-evaluates."""
    from mcp_server.knowledge import tools as knowledge_tools
    from pipelines.engagement.cascade import Cascade
    from pipelines.knowledge_ref import SNAPSHOT_ID, ResolutionError, load_snapshot

    engagement = request.path_params["engagement"]
    guard_engagement(engagement, action="pin")
    access = get_access()
    if access is None or not access.is_managed(engagement):
        return JSONResponse({"status": "error", "error": "engagement_not_managed", "reason": "Pinning needs a managed engagement."}, status_code=409)
    member = acting_member(engagement)
    if member is None:
        return JSONResponse({"status": "error", "error": "forbidden", "reason": "actor_required"}, status_code=403)
    try:
        body = await request.json()
    except Exception:
        body = {}
    snapshot_id = body.get("snapshot_id") if isinstance(body, dict) else None
    if not isinstance(snapshot_id, str) or not SNAPSHOT_ID.match(snapshot_id):
        return JSONResponse({"status": "invalid_argument", "argument": "snapshot_id", "reason": "'snapshot_id' is required"}, status_code=400)
    try:
        snapshot = load_snapshot(knowledge_tools.SNAPSHOTS_DIR, snapshot_id)
    except ResolutionError as err:
        try:  # the latest snapshot may be the one designated
            snapshot = load_snapshot(knowledge_tools.SNAPSHOTS_DIR)
            if snapshot["snapshot_id"] != snapshot_id:
                raise err from None
        except ResolutionError:
            return JSONResponse({"status": "invalid_argument", "argument": "snapshot_id", "reason": f"snapshot not usable ({err.reason})"}, status_code=400)
    previous = access.get_pin(engagement)
    access.set_pin(engagement, snapshot["snapshot_id"], snapshot["payload_sha256"], member["handle"], replace=True)
    access.audit(engagement, member["handle"], "pin", "allowed", {"from": (previous or {}).get("snapshot_id"), "to": snapshot["snapshot_id"]})
    repo = ElicitationRepository(db_path=get_engagement_path(engagement))
    try:
        report = Cascade(repo, access, engagement, knowledge_tools.SNAPSHOTS_DIR, member["handle"]).run()
    finally:
        repo.close()
    return JSONResponse({"status": "ok", "data": {"kb_snapshot": access.get_pin(engagement), "previous": previous, "cascade": report}})


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
        return await _handle(request, "contribute", lambda w, b, m: _created(w.answer_question(qid, b, key, m["role"])))

    async def requirements(request):
        return await _handle(request, "contribute", lambda w, b, m: (200, w.add_requirements(b)))

    async def propose_rule(request):
        return await _handle(request, "contribute", lambda w, b, m: (201, w.rules.propose_local(b)))

    async def assert_rule(request):
        tid = request.path_params["trigger_id"]
        return await _handle(request, "decide", lambda w, b, m: (200, w.rules.assert_local(tid)))

    async def withdraw_rule(request):
        tid = request.path_params["trigger_id"]
        return await _handle(request, "contribute", lambda w, b, m: (200, w.rules.withdraw_local(tid, m["role"] in DECIDING_ROLES)))

    async def disable_rule(request):
        tid = request.path_params["trigger_id"]
        return await _handle(request, "decide", lambda w, b, m: (200, w.rules.disable(tid, b)))

    async def enable_rule(request):
        tid = request.path_params["trigger_id"]
        return await _handle(request, "decide", lambda w, b, m: (200, w.rules.enable(tid)))

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
        Route(f"{base}/facts", endpoint=_facts, methods=["GET"]),
        Route(f"{base}/lineage", endpoint=_lineage, methods=["GET"]),
        Route(f"{base}/rules", endpoint=_rules, methods=["GET"]),
        Route(f"{base}/rules", endpoint=propose_rule, methods=["POST"]),
        Route(f"{base}/rules/{{trigger_id}}/disable", endpoint=disable_rule, methods=["POST"]),
        Route(f"{base}/rules/{{trigger_id}}/enable", endpoint=enable_rule, methods=["POST"]),
        Route(f"{base}/rules/{{trigger_id}}/assert", endpoint=assert_rule, methods=["POST"]),
        Route(f"{base}/rules/{{trigger_id}}/withdraw", endpoint=withdraw_rule, methods=["POST"]),
        Route(f"{base}/kb-pin", endpoint=_kb_pin, methods=["PUT"]),
        Route(f"{base}/decisions", endpoint=decisions, methods=["POST"]),
        Route(f"{base}/decisions/{{decision_id}}/assert", endpoint=assert_decision, methods=["POST"]),
        Route(f"{base}/decisions/{{decision_id}}/withdraw", endpoint=withdraw_decision, methods=["POST"]),
        Route(f"{base}/questions", endpoint=questions, methods=["POST"]),
        Route(f"{base}/questions/{{question_id}}/answers", endpoint=answers, methods=["POST"]),
        Route(f"{base}/requirements", endpoint=requirements, methods=["POST"]),
        Route(f"{base}/conflicts/{{conflict_id}}/arbitrate", endpoint=arbitrate, methods=["POST"]),
    ]
