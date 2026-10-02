"""Seal and verify an engagement bundle (schemas/engagement_bundle.schema.json).

JSON Schema checks the shape; this module checks what a schema cannot express and what the zero-tolerance rule
needs: the seal (suite canonical-json profile, ``pipelines/canonical.py``), unique and resolving identifiers, assertion
levels DERIVED from epistemic statuses, claims backed by a person, reuse backed by a confirmation, cited KB assets listed,
the two-stage provisional rule, no e-mail address.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jsonschema

from pipelines import canonical

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "engagement_bundle.schema.json"

ASSERTION_OF = {
    "validated": "asserted",
    "reused_confirmed": "asserted",
    "ai_proposed": "proposed",
    "assumption": "assumption",
    "contested": "open",
}
HUMAN_BASES = ("human_validation", "reuse_confirmation")
UNRIPE = ("L0_named", "L1_framed", "L2_decomposed")  # below L3_decided
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9.-]+")
CLAIM_COLLECTIONS = ("decisions", "statements", "compliance")


@dataclass(frozen=True)
class Problem:
    code: str
    path: str
    message: str

    def __str__(self) -> str:
        return f"[{self.code}] {self.path}: {self.message}"


def payload_sha256(data: Any) -> str:
    """Checksum of ``data`` under the suite canonical-json profile v1 (raises ``canonical.CanonicalError`` if refused)."""
    return canonical.sha256(data)


def seal(bundle: dict[str, Any]) -> dict[str, Any]:
    """Set the checksum over ``data`` (returns the same dict)."""
    bundle["checksum"] = payload_sha256(bundle["data"])
    return bundle


def load_schema() -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return loaded


def schema_problems(bundle: dict[str, Any]) -> list[Problem]:
    validator = jsonschema.Draft7Validator(load_schema(), format_checker=jsonschema.FormatChecker())
    return [
        Problem("SCHEMA", "/" + "/".join(str(p) for p in err.absolute_path), err.message)
        for err in sorted(validator.iter_errors(bundle), key=lambda e: list(map(str, e.absolute_path)))
    ]


def _walk_strings(node: Any, path: str = ""):
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from _walk_strings(v, f"{path}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk_strings(v, f"{path}/{i}")


def invariant_problems(bundle: dict[str, Any]) -> list[Problem]:
    out: list[Problem] = []
    data = bundle.get("data", {})
    try:
        if bundle.get("checksum") != payload_sha256(data):
            out.append(Problem("SEAL", "/checksum", "does not match the suite canonical-json serialisation of data"))
    except canonical.CanonicalError as err:
        out.append(Problem("CANONICAL", "/data", str(err)))

    # identifiers: one namespace, unique, and every reference resolves
    owners: dict[str, str] = {}

    def register(ident: str, where: str) -> None:
        if ident in owners:
            out.append(Problem("DUPLICATE_ID", where, f"'{ident}' is already used at {owners[ident]}"))
        owners.setdefault(ident, where)

    arch = data.get("architecture") or {}
    collections: dict[str, list[dict[str, Any]]] = {
        "source_documents": data.get("source_documents", []), "requirements": data.get("requirements", []),
        "subjects": data.get("subjects", []), "decisions": data.get("decisions", []),
        "statements": data.get("statements", []), "compliance": data.get("compliance", []),
        "gaps": data.get("gaps", []), "reuse_log": data.get("reuse_log", []), "conflicts": data.get("conflicts", []),
        "elements": arch.get("elements", []), "relations": arch.get("relations", []),
    }
    for name, items in collections.items():
        for i, item in enumerate(items):
            register(item.get("id", ""), f"/data/{name}/{i}")
    for i, subject in enumerate(collections["subjects"]):
        for j, q in enumerate(subject.get("open_questions", [])):
            register(q.get("id", ""), f"/data/subjects/{i}/open_questions/{j}")

    ids = {name: {it.get("id") for it in items} for name, items in collections.items()}

    def must_resolve(value: str | None, collection: str, where: str) -> None:
        if value is not None and value not in ids[collection]:
            out.append(Problem("DANGLING_REF", where, f"'{value}' is not in {collection}"))

    for i, r in enumerate(collections["requirements"]):
        must_resolve(r.get("source_document_id"), "source_documents", f"/data/requirements/{i}/source_document_id")
    for i, s in enumerate(collections["subjects"]):
        for rid in s.get("requirement_ids", []):
            must_resolve(rid, "requirements", f"/data/subjects/{i}/requirement_ids")
        for did in s.get("decision_ids", []):
            must_resolve(did, "decisions", f"/data/subjects/{i}/decision_ids")
    for name in ("decisions", "statements"):
        for i, it in enumerate(collections[name]):
            must_resolve(it.get("subject_id"), "subjects", f"/data/{name}/{i}/subject_id")
    for i, c in enumerate(collections["compliance"]):
        must_resolve(c.get("requirement_id"), "requirements", f"/data/compliance/{i}/requirement_id")
    for name in ("compliance", "elements", "relations"):
        for i, it in enumerate(collections[name]):
            for did in it.get("decision_ids", []):
                must_resolve(did, "decisions", f"/data/{name}/{i}/decision_ids")
    for i, c in enumerate(collections["conflicts"]):
        for sid in c.get("statement_ids", []):
            must_resolve(sid, "statements", f"/data/conflicts/{i}/statement_ids")
    for i, g in enumerate(collections["gaps"]):
        must_resolve(g.get("subject_id"), "subjects", f"/data/gaps/{i}/subject_id")
        must_resolve(g.get("requirement_id"), "requirements", f"/data/gaps/{i}/requirement_id")
    for i, e in enumerate(collections["elements"]):
        must_resolve(e.get("boundary_id"), "elements", f"/data/architecture/elements/{i}/boundary_id")
    for i, rel in enumerate(collections["relations"]):
        must_resolve(rel.get("from"), "elements", f"/data/architecture/relations/{i}/from")
        must_resolve(rel.get("to"), "elements", f"/data/architecture/relations/{i}/to")
    for name in CLAIM_COLLECTIONS:
        for i, it in enumerate(collections[name]):
            for ref in (it.get("provenance") or {}).get("references", []):
                if ref not in owners:
                    out.append(Problem("DANGLING_REF", f"/data/{name}/{i}/provenance/references", f"'{ref}' is not an identifier of this bundle"))

    # cited KB assets are listed
    listed = {k.get("ref") for k in data.get("kb_references", [])}
    cited: list[tuple[str, str]] = []
    cited += [(f"/data/decisions/{i}/derived_from/kb_ref", d["derived_from"]["kb_ref"]) for i, d in enumerate(collections["decisions"]) if d.get("derived_from")]
    cited += [(f"/data/compliance/{i}/control_ref", c.get("control_ref", "")) for i, c in enumerate(collections["compliance"])]
    cited += [(f"/data/reuse_log/{i}/matched_ref", r.get("matched_ref", "")) for i, r in enumerate(collections["reuse_log"])]
    cited += [(f"/data/glossary/{i}/kb_ref", g["kb_ref"]) for i, g in enumerate(data.get("glossary", [])) if g.get("kb_ref")]
    for where, ref in cited:
        if ref not in listed:
            out.append(Problem("KB_REF_UNLISTED", where, f"'{ref}' is cited but missing from data.kb_references"))

    # assertion levels are derived, and only a person can make a claim 'asserted'
    claims = [(f"/data/{n}/{i}", it) for n in CLAIM_COLLECTIONS for i, it in enumerate(collections[n])]
    claims += [(f"/data/architecture/{n}/{i}", it) for n in ("elements", "relations") for i, it in enumerate(collections[n])]
    for where, it in claims:
        status, level = it.get("epistemic_status"), it.get("assertion_level")
        if ASSERTION_OF.get(str(status)) != level:
            out.append(Problem("LEVEL", where, f"assertion_level '{level}' is not the one derived from epistemic_status '{status}' ({ASSERTION_OF.get(str(status))})"))
        prov = it.get("provenance") or {}
        if level == "asserted" and (prov.get("basis") not in HUMAN_BASES or not prov.get("by")):
            out.append(Problem("UNBACKED_CLAIM", where, "an asserted item needs provenance.basis human_validation or reuse_confirmation and at least one validator"))

    # reuse is backed by a confirmation judged assumption by assumption
    log = {r["id"]: r for r in collections["reuse_log"]}
    for i, d in enumerate(collections["decisions"]):
        where, status = f"/data/decisions/{i}", d.get("status")
        if status in ("validated", "reused") and d.get("assertion_level") != "asserted":
            out.append(Problem("STATUS", where, f"a {status} decision must be asserted"))
        if status == "proposed" and d.get("assertion_level") == "asserted":
            out.append(Problem("STATUS", where, "a proposed decision cannot be asserted"))
        if status != "reused":
            continue
        derived = d.get("derived_from") or {}
        entry = log.get(derived.get("reuse_log_id", ""))
        if entry is None:
            out.append(Problem("REUSE_UNBACKED", where, "a reused decision needs derived_from.reuse_log_id pointing to a reuse_log entry"))
            continue
        if entry["matched_ref"] != derived.get("kb_ref"):
            out.append(Problem("REUSE_UNBACKED", where, "the reuse_log entry is about another KB asset"))
        if entry["outcome"] not in ("reused", "reused_with_exception"):
            out.append(Problem("REUSE_UNBACKED", where, f"the reuse_log outcome is '{entry['outcome']}', not a reuse"))
        judged = entry.get("assumptions", [])
        if not judged:
            out.append(Problem("REUSE_UNBACKED", where, "a reuse without any judged assumption is not allowed"))
        if entry["outcome"] == "reused" and any(a["status"] != "holds" for a in judged):
            out.append(Problem("REUSE_UNBACKED", where, "outcome 'reused' requires every assumption to hold"))
        if entry["outcome"] == "reused_with_exception" and not (entry.get("comment") or "").strip():
            out.append(Problem("REUSE_UNBACKED", where, "a reuse with exception needs its comment"))

    # a subject is decided only if a person decided something
    decisions = {d["id"]: d for d in collections["decisions"]}
    for i, s in enumerate(collections["subjects"]):
        if s.get("status") == "decided" and not any(decisions.get(x, {}).get("assertion_level") == "asserted" for x in s.get("decision_ids", [])):
            out.append(Problem("DECIDED_WITHOUT_DECISION", f"/data/subjects/{i}", "a decided subject needs at least one asserted decision"))

    # two-stage epistemics: one unripe subject or open conflict makes the whole bundle provisional
    unripe = sorted(s["id"] for s in collections["subjects"] if s.get("maturity") in UNRIPE)
    open_conflicts = sorted(c["id"] for c in collections["conflicts"] if c.get("status") == "open")
    reasons = data.get("provisional_reasons") or {}
    if bool(data.get("is_provisional")) != bool(unripe or open_conflicts):
        out.append(Problem("PROVISIONAL", "/data/is_provisional", f"must be {bool(unripe or open_conflicts)}: unripe subjects {unripe}, open conflicts {open_conflicts}"))
    if sorted(reasons.get("unripe_subjects", [])) != unripe or sorted(reasons.get("open_conflicts", [])) != open_conflicts:
        out.append(Problem("PROVISIONAL", "/data/provisional_reasons", "must list exactly the subjects below L3_decided and the open conflicts"))

    # privacy: owner handles only
    for path, text in _walk_strings(bundle):
        if EMAIL.search(text):
            out.append(Problem("EMAIL", path, "an e-mail address must not appear in a bundle (use owner handles)"))
    return out


def verify_bundle(bundle: dict[str, Any]) -> list[Problem]:
    """All problems of a bundle; an empty list means it can be handed to a generator."""
    shape = schema_problems(bundle)
    return shape if shape else invariant_problems(bundle)
