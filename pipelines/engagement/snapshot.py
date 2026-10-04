"""The sealed snapshot of an engagement, emitted by the Hub toward the suite (K11, ADR-KH-01 A10-b and A10-e).

The Hub is the emitter of the "engagement" channel: it holds the engagement base, it can rebuild the snapshot, and it seals
it with the suite's canonical-json v1 profile. Archinex, the workbench where architects deliberate, is a client and appears
nowhere in the snapshot.

What it holds is what the engagement plane holds: requirements, subjects and their maturity, statements with their attribution,
conflicts, gaps. It does **not** invent what the plane does not hold (decisions with alternatives, architecture elements,
compliance links, reuse log): ``schemas/engagement_bundle.schema.json`` remains the target model for those.

Envelope (suite ``ExternalSnapshotEnvelope``): ``schemaVersion, snapshotId, sourceSystem, emitter, createdAt, sourceRevision,
checksum, data``. ``checksum`` is the sha256 of ``data`` alone; ``snapshotId`` derives from it (the same state gives the same
identifier, an issued identifier never designates other content).

Nothing is produced when the verification fails: no e-mail address, only handles; nothing presented as asserted without a
person other than its author; ``is_provisional`` derived, never declared.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import jsonschema

from mcp_server.core.version import CONTRACT_VERSION
from pipelines import canonical
from pipelines.bundle.verify import Problem
from pipelines.engagement.access import CONFIDENTIALITY
from pipelines.snapshot_envelope import provisional
from tools.elicitation.config import SUBJECT_LEVELS

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "engagement_snapshot.schema.json"
SCHEMA_VERSION = "1.2"
EMITTER = "knowledge-hub"
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+")
HANDLE = re.compile(r"^@[a-z0-9][a-z0-9._-]{0,62}$")
ASSERTION_OF = {"active": "asserted", "proposed": "proposed", "superseded": "superseded", "withdrawn": "withdrawn"}
OPEN_QUESTION = ("open", "sent")
UNRIPE = tuple(SUBJECT_LEVELS[: SUBJECT_LEVELS.index("L3_decided")])


class ExportRefused(Exception):  # noqa: N818
    """Nothing was produced. ``code`` is machine-readable; ``problems`` say what and where (never the values)."""

    def __init__(self, code: str, message: str, problems: list[Problem] | None = None) -> None:
        self.code = code
        self.problems = problems or []
        super().__init__(message)


def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


# --- collect (reads the graph) ------------------------------------------------------------------------------------


def collect(repo: Any, engagement: str) -> dict[str, Any]:
    """The raw rows of the engagement plane. No interpretation here: ``build_data`` is the pure part."""
    run = repo.db_client.execute_cypher

    def rows(query: str, **params: Any) -> list[dict[str, Any]]:
        out = run(query, params=params)
        return [r for r in (out or []) if r and "error" not in r]

    conflicts = rows(
        "MATCH (c:Conflict) RETURN c.id as id, c.kind as kind, c.detail as detail, c.status as status, "
        "c.resolution as resolution, c.arbitrated_by as arbitrated_by;")
    involved = rows("MATCH (c:Conflict)-[:INVOLVES]->(s:Statement) RETURN c.id as conflict, s.id as statement;")
    return {
        "requirements": repo.get_requirements(engagement),
        "subjects": rows("MATCH (s:Subject {engagement: $e}) RETURN s.name as name, s.definition as definition, s.level as level;", e=engagement),
        "statements": rows(
            "MATCH (s:Statement {engagement: $e}) RETURN s.id as id, s.subject as subject, s.section as section, "
            "s.predicate as predicate, s.value as value, s.confidence as confidence, s.status as status, "
            "s.origin as origin, s.author as author, s.validated_by as validated_by, s.validated_at as validated_at, "
            "s.based_on as based_on, s.imported_from as imported_from;", e=engagement),
        "conflicts": conflicts,
        "involves": involved,
        "decisions": repo.list_decisions(engagement),
        "questions": rows(
            "MATCH (q:Question {engagement: $e}) OPTIONAL MATCH (q)-[:TARGETS]->(s:Subject) RETURN q.id as id, "
            "q.gap_type as gap_type, q.question as question, q.status as status, s.name as subject;", e=engagement),
    }


# --- build (pure) -------------------------------------------------------------------------------------------------


def _based_on(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "[]")
        except ValueError:
            return []
    return [{"id": str(i["id"]), "resolved": i.get("resolved")} for i in raw or [] if isinstance(i, dict) and i.get("id")]


def build_data(raw: dict[str, Any], engagement: str, confidentiality: str, kb_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    """The ``data`` of the snapshot from raw rows: deterministic, sorted, nothing guessed."""
    from pipelines.knowledge_ref import ResolutionError, resolve  # noqa: PLC0415

    kb_refs: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    def cite(owner: dict[str, str], based_on: list[dict[str, Any]]) -> None:
        for ref in based_on:
            found = None
            if kb_snapshot is not None:
                try:
                    found = resolve(kb_snapshot, ref["id"])
                except ResolutionError:
                    found = None
            if found:
                kb_refs.append({**owner, "knowledge_ref": found["knowledge_ref"], "confidence": found["confidence"]})
            else:
                unresolved.append({**owner, "id": ref["id"]})

    statements = []
    for r in sorted(raw["statements"], key=lambda r: r["id"]):
        based_on = _based_on(r.get("based_on"))
        status = r.get("status") or "proposed"
        statements.append({
            "id": r["id"], "subject": r.get("subject") or "general", "section": r.get("section") or "general",
            "predicate": r.get("predicate") or "has_property", "value": r.get("value") or "",
            "confidence": r.get("confidence") or "assumed", "status": status,
            "assertion_level": ASSERTION_OF.get(status, status), "origin": r.get("origin") or "human",
            "author": r.get("author") or "", "validated_by": r.get("validated_by") or "",
            "validated_at": r.get("validated_at") or "", "based_on": based_on, "imported": bool(r.get("imported_from")),
        })
        cite({"statement_id": r["id"]}, based_on)

    decisions = []
    for r in sorted(raw.get("decisions", []), key=lambda r: r["id"]):
        based_on = _based_on(r.get("based_on"))
        status = r.get("status") or "proposed"
        decisions.append({
            "id": r["id"], "subject": r.get("subject") or "", "decision": r.get("decision") or "",
            "rationale": r.get("rationale") or "", "rejected": list(r.get("rejected") or []),
            "reversibility": r.get("reversibility") or "reversible", "consequences": list(r.get("consequences") or []),
            "accepted_violations": list(r.get("accepted_violations") or []), "based_on": based_on, "status": status,
            "assertion_level": ASSERTION_OF.get(status, status), "origin": r.get("origin") or "human",
            "author": r.get("author") or "", "validated_by": r.get("validated_by") or "",
            "validated_at": r.get("validated_at") or "", "supersedes": r.get("supersedes") or "",
            "imported": bool(r.get("imported_from")),
        })
        cite({"decision_id": r["id"]}, based_on)

    subjects = [{"id": f"{engagement}:{r['name']}", "name": r["name"], "definition": r.get("definition") or "",
                 "maturity": r.get("level") or SUBJECT_LEVELS[0]} for r in sorted(raw["subjects"], key=lambda r: r["name"])]
    members: dict[str, list[str]] = {}
    for link in raw["involves"]:
        members.setdefault(link["conflict"], []).append(link["statement"])
    statement_ids = {s["id"] for s in statements}
    conflicts = [{
        "id": c["id"], "kind": c.get("kind") or "contradiction", "status": c.get("status") or "open",
        "statement_ids": sorted(s for s in members.get(c["id"], []) if s in statement_ids), "detail": c.get("detail") or "",
        "resolution": c.get("resolution") or "", "arbitrated_by": c.get("arbitrated_by") or "",
    } for c in sorted(raw["conflicts"], key=lambda c: c["id"]) if members.get(c["id"])]

    asserted_subjects = {s["subject"] for s in statements if s["status"] == "active"}
    gaps = [{"id": f"G1-{s['name']}", "kind": "G1_empty_section", "description": f"No asserted statement about '{s['name']}'.",
             "subject": s["name"], "blocking": False} for s in subjects if s["name"] not in asserted_subjects]
    gaps += [{"id": q["id"], "kind": q.get("gap_type") or "G2_unanswered_blocking", "description": q.get("question") or "",
              "subject": q.get("subject") or "", "blocking": (q.get("gap_type") or "G2_unanswered_blocking") == "G2_unanswered_blocking"}
             for q in sorted(raw["questions"], key=lambda q: q["id"]) if q.get("status") in OPEN_QUESTION]

    unripe = sum(1 for s in subjects if s["maturity"] in UNRIPE)
    open_conflicts = sum(1 for c in conflicts if c["status"] == "open")
    return {
        "engagement": {"id": engagement, "confidentiality": confidentiality},
        "pins": {"contract_version": CONTRACT_VERSION,
                 "kb_snapshot": {"snapshot_id": kb_snapshot["snapshot_id"], "checksum": kb_snapshot["payload_sha256"]} if kb_snapshot else None},
        **provisional(unripe, open_conflicts),
        "requirements": [{"id": r["id"], "text": r.get("text") or "", "section": r.get("section") or "",
                          "category": r.get("category") or "general", "criticality": r.get("criticality") or "mandatory",
                          "status": r.get("status") or "gap"} for r in sorted(raw["requirements"], key=lambda r: r["id"])],
        "subjects": subjects, "statements": statements, "decisions": decisions, "conflicts": conflicts,
        "gaps": sorted(gaps, key=lambda g: g["id"]),
        "kb_references": kb_refs, "unresolved_references": unresolved,
    }


def snapshot_id(engagement: str, checksum: str) -> str:
    return f"eng-{engagement}-{checksum[len('sha256:'):][:12]}"


def seal(data: dict[str, Any], engagement: str, created_at: str, source_revision: str) -> dict[str, Any]:
    checksum = canonical.sha256(data)
    return {"schemaVersion": SCHEMA_VERSION, "snapshotId": snapshot_id(engagement, checksum), "sourceSystem": EMITTER,
            "emitter": EMITTER, "createdAt": created_at, "sourceRevision": source_revision, "checksum": checksum, "data": data}


def snapshot_ref(envelope: dict[str, Any]) -> dict[str, str]:
    """The suite's ``SnapshotRef``: it travels apart from what it designates, a consumer refuses a content whose hash differs."""
    return {"sourceSystem": envelope["sourceSystem"], "snapshotId": envelope["snapshotId"],
            "checksum": envelope["checksum"], "producedAt": envelope["createdAt"]}


# --- verify -------------------------------------------------------------------------------------------------------


def _strings(node: Any, path: str = "$"):
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from _strings(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _strings(v, f"{path}[{i}]")


def verify(envelope: dict[str, Any]) -> list[Problem]:
    """Everything a schema cannot say. An empty list means the snapshot may be issued."""
    problems: list[Problem] = []
    for err in sorted(jsonschema.Draft7Validator(load_schema()).iter_errors(envelope), key=lambda e: list(e.path)):
        problems.append(Problem("SCHEMA", "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in err.path), err.message[:200]))
    if problems:
        return problems
    data = envelope["data"]
    try:
        checksum = canonical.sha256(data)
    except canonical.CanonicalError as err:
        return [Problem("CANONICAL", "$.data", str(err))]
    if envelope["checksum"] != checksum:
        problems.append(Problem("SEAL", "$.checksum", "the checksum is not the sha256 of data at the canonical-json v1 profile"))
    if envelope["snapshotId"] != snapshot_id(data["engagement"]["id"], checksum):
        problems.append(Problem("SNAPSHOT_ID", "$.snapshotId", "the identifier does not derive from the checksum"))
    if data["engagement"]["confidentiality"] not in CONFIDENTIALITY:
        problems.append(Problem("CONFIDENTIALITY", "$.data.engagement.confidentiality", "confidentiality is required"))

    for collection in ("requirements", "subjects", "statements", "decisions", "conflicts", "gaps"):
        ids = [i["id"] for i in data[collection]]
        for dup in sorted({i for i in ids if ids.count(i) > 1}):
            problems.append(Problem("DUPLICATE_ID", f"$.data.{collection}", f"identifier '{dup}' appears twice"))
    statement_ids = {s["id"] for s in data["statements"]}
    subject_names = {s["name"] for s in data["subjects"]}
    for i, s in enumerate(data["statements"]):
        where = f"$.data.statements[{i}]"
        if s["status"] == "active":
            if not HANDLE.match(s["validated_by"]) or not s["validated_at"]:
                problems.append(Problem("ASSERTED_WITHOUT_PERSON", where, f"{s['id']} is active without a person who asserted it"))
            elif s["validated_by"] == s["author"]:
                problems.append(Problem("SELF_VALIDATION", where, f"{s['id']} was asserted by its own author"))
        elif s["status"] == "proposed" and s["validated_by"]:
            problems.append(Problem("VALIDATOR_ON_PROPOSED", where, f"{s['id']} is proposed but names a validator"))
        if not HANDLE.match(s["author"]):
            problems.append(Problem("AUTHOR_NOT_A_HANDLE", where, f"{s['id']}: the author must be a member handle"))
        if s["origin"] == "llm-derived" and s["status"] == "active" and not s["validated_by"]:
            problems.append(Problem("LLM_ASSERTED", where, f"{s['id']} derived by a model and asserted by nobody"))
    decision_ids = {d["id"] for d in data["decisions"]}
    by_subject: dict[str, list[dict[str, Any]]] = {}
    for i, d in enumerate(data["decisions"]):
        where = f"$.data.decisions[{i}]"
        by_subject.setdefault(d["subject"], []).append(d)
        if d["subject"] not in subject_names:
            problems.append(Problem("DANGLING", where, f"decision {d['id']} cites unknown subject '{d['subject']}'"))
        if d["status"] == "active":
            if not HANDLE.match(d["validated_by"]) or not d["validated_at"]:
                problems.append(Problem("ASSERTED_WITHOUT_PERSON", where, f"decision {d['id']} is active without a person who asserted it"))
            elif d["validated_by"] == d["author"]:
                problems.append(Problem("SELF_VALIDATION", where, f"decision {d['id']} was asserted by its own author"))
        elif d["status"] == "proposed" and d["validated_by"]:
            problems.append(Problem("VALIDATOR_ON_PROPOSED", where, f"decision {d['id']} is proposed but names a validator"))
        if not HANDLE.match(d["author"]):
            problems.append(Problem("AUTHOR_NOT_A_HANDLE", where, f"decision {d['id']}: the author must be a member handle"))
        kept = d["decision"].strip().lower()
        if any(r["option"].strip().lower() == kept for r in d["rejected"]):
            problems.append(Problem("INCONSISTENT_ALTERNATIVES", where, f"decision {d['id']} is also listed among its rejected options"))
        if d["supersedes"]:
            target = next((x for x in data["decisions"] if x["id"] == d["supersedes"]), None)
            if target is None:
                problems.append(Problem("DANGLING", where, f"decision {d['id']} supersedes unknown decision {d['supersedes']}"))
            elif d["status"] == "active" and target["status"] != "superseded":
                problems.append(Problem("SUPERSESSION", where, f"decision {d['supersedes']} must be superseded by {d['id']}"))
    for subject, items in sorted(by_subject.items()):
        if sum(1 for d in items if d["status"] == "active") > 1:
            problems.append(Problem("MULTIPLE_ACTIVE_DECISIONS", "$.data.decisions", f"subject '{subject}' has more than one asserted decision"))
    decided = {d["subject"] for d in data["decisions"] if d["status"] == "active"}
    for i, sub in enumerate(data["subjects"]):
        if sub["maturity"] in ("L3_decided", "L4_specified") and sub["name"] not in decided:
            problems.append(Problem("DECIDED_WITHOUT_DECISION", f"$.data.subjects[{i}]", f"'{sub['name']}' is {sub['maturity']} without an asserted decision"))
    for i, c in enumerate(data["conflicts"]):
        for sid in c["statement_ids"]:
            if sid not in statement_ids:
                problems.append(Problem("DANGLING", f"$.data.conflicts[{i}]", f"conflict {c['id']} cites unknown statement {sid}"))
        if c["status"] == "arbitrated" and not HANDLE.match(c["arbitrated_by"]):
            problems.append(Problem("ARBITRATED_WITHOUT_PERSON", f"$.data.conflicts[{i}]", f"{c['id']} was arbitrated by nobody"))
    for i, g in enumerate(data["gaps"]):
        if g["subject"] and g["subject"] not in subject_names:
            problems.append(Problem("DANGLING", f"$.data.gaps[{i}]", f"gap {g['id']} cites unknown subject '{g['subject']}'"))
    for i, ref in enumerate(data["kb_references"]):
        if ref.get("statement_id", ref.get("decision_id")) not in (statement_ids | decision_ids):
            problems.append(Problem("DANGLING", f"$.data.kb_references[{i}]", "reference cites an unknown statement or decision"))
    unripe = sum(1 for s in data["subjects"] if s["maturity"] in UNRIPE)
    open_conflicts = sum(1 for c in data["conflicts"] if c["status"] == "open")
    expected = provisional(unripe, open_conflicts)
    if data["is_provisional"] != expected["is_provisional"] or data["provisional_reasons"] != expected["provisional_reasons"]:
        problems.append(Problem("PROVISIONAL", "$.data.is_provisional", "is_provisional and its reasons must be derived from the subjects and conflicts"))
    for path, text in _strings(data):
        if EMAIL.search(text):
            problems.append(Problem("EMAIL", path, "an e-mail address cannot leave the Hub: handles only"))
    return problems


# --- export (reads, builds, verifies, stores) ---------------------------------------------------------------------


def _revision() -> str:
    env = os.environ.get("LLMOPS_COMMIT")
    if env:
        return env
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return "unknown"


def export_engagement(access: Any, repo: Any, engagement: str, produced_by: str, snapshots_dir: Path,
                      now: datetime | None = None) -> tuple[dict[str, Any], bool]:
    """Issue the sealed snapshot of a managed engagement: ``(envelope, created)``.

    The same state gives the same identifier: the stored snapshot is returned (``created`` False), never rewritten.
    Raises :class:`ExportRefused` and stores nothing when the verification fails.
    """
    from pipelines.knowledge_ref import ResolutionError, load_snapshot  # noqa: PLC0415

    confidentiality = access.confidentiality(engagement)
    if confidentiality is None:
        raise ExportRefused("engagement_not_managed", "only a managed engagement can be exported")
    raw = collect(repo, engagement)
    needs_kb = any(_based_on(s.get("based_on")) for s in raw["statements"])
    try:
        kb_snapshot = load_snapshot(snapshots_dir)
    except ResolutionError as err:
        if needs_kb:
            raise ExportRefused("kb_snapshot_unavailable", f"statements cite the knowledge base but its snapshot is unusable ({err.reason})") from err
        kb_snapshot = None
    data = build_data(raw, engagement, confidentiality, kb_snapshot)
    try:
        checksum = canonical.sha256(data)
    except canonical.CanonicalError as err:
        raise ExportRefused("not_canonical", str(err)) from err
    existing = access.get_export(snapshot_id(engagement, checksum))
    if existing:
        return existing["envelope"], False
    created_at = (now or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
    envelope = seal(data, engagement, created_at, _revision())
    problems = verify(envelope)
    if problems:
        raise ExportRefused("verification_failed", f"{len(problems)} problem(s): nothing was produced", problems)
    access.put_export(envelope, engagement, produced_by, data["is_provisional"])
    access.audit(engagement, produced_by, "export", "allowed",
                 {"snapshot_id": envelope["snapshotId"], "is_provisional": data["is_provisional"]})
    return envelope, True
