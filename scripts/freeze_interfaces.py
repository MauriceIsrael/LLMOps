"""Freeze the response *shape* of every public interface (contract v1).

Each MCP tool and REST route of the frozen v1 contract is called on the demo data,
and the recursive shape of its response is written to
``tests/contract/frozen/<name>.shape.json``. ``tests/contract/test_frozen_interfaces.py``
compares the current shapes with the frozen ones: a key that disappears or changes
type fails the test, a key that is added passes.

The shapes are generated ONCE and committed. Do not re-run this script to "fix" a
failing contract test. Only run it to freeze a newly added interface:

    poetry run python scripts/freeze_interfaces.py --only <interface-name> [...]

Shape format (recursive):

* scalar: ``{"type": ["string"]}`` (``string``, ``number``, ``boolean``, ``null``);
* object: ``{"type": ["object"], "keys": {<key>: <shape>}}``;
* array:  ``{"type": ["array"], "items": <shape> | null}`` — the items shape is the
  merge of all elements' shapes, so that the order of the demo data does not matter;
* map:    ``{"type": ["object"], "values": <shape> | null}`` — objects keyed by data
  (asset ids, control ids, section numbers...), listed in ``MAP_KEYS``. Their keys
  depend on the knowledge base content, not on the interface.

When a value is observed with several types, ``type`` lists all of them.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

FROZEN_DIR = ROOT_DIR / "tests" / "contract" / "frozen"
STATUS_CODES_FILE = FROZEN_DIR / "_status_codes.json"

# Engagement served by the demo instance and used to exercise the engagement plane.
DEMO_ENGAGEMENT = "nordwave-mcx-2027"
# Scratch engagement used by the tools that write (RFP shredding, zero draft, elicitation).
SCRATCH_ENGAGEMENT = "contract-freeze"
CONTRACT_TOKEN = "contract-freeze-token"

SAMPLE_RFP = """\
# Exigences techniques

REQ-001: The platform shall provide end-to-end encryption of group voice communications.
REQ-002: The operator must guarantee 99.999% availability of the mission-critical core.
REQ-003: Le système doit journaliser tous les accès administrateurs et les conserver un an.
REQ-004: The solution shall support geo-redundant deployment across two data centres.
"""

REVIEWER_TOKEN = "contract-reviewer-token"
SAMPLE_CANDIDATE = {
    "kind": "rex",
    "title": "Contract freeze return of experience",
    "rationale": "Exercise the candidate contract.",
    "proposed_content": "Break-glass access must be tested every quarter.",
    "source": {"system": "mcp", "author": "contract-test"},
    "evidence": [{"kind": "engagement", "ref": "contract-engagement"}],
}
# Candidate ids created during the run (MCP and REST flows).
_STATE: dict[str, str] = {}

SAMPLE_OPTION = {
    "title": "Closed-loop auto-remediation of network incidents",
    "description": "Automated remediation playbooks triggered by alarms, without human approval.",
    "statements": [{"subject": "remediation", "predicate": "has_property", "value": "fully autonomous remediation"}],
}


# ---------------------------------------------------------------------------
# Shapes
# ---------------------------------------------------------------------------

# Keys whose value is a data-keyed object (map), with the number of nested map levels.
MAP_KEYS: dict[str, int] = {
    "applicability_index": 1,   # snapshot: asset id -> applicability
    "compliance_index": 2,      # snapshot: framework -> control id -> entry
    "sections": 1,              # asset sections by heading / skills matrix by section id
    "breakdown_by_category": 1,  # RFP shredding: category -> counts
    "drafts": 1,                # prose suggest-batch: block id -> draft
}


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"  # serialized with default=str


def merge_shapes(a: dict[str, Any] | None, b: dict[str, Any] | None) -> dict[str, Any] | None:
    """Union of two shapes (types, object keys and array items are merged)."""
    if a is None:
        return b
    if b is None:
        return a
    merged: dict[str, Any] = {"type": sorted(set(a["type"]) | set(b["type"]))}
    if "keys" in a or "keys" in b:
        keys: dict[str, Any] = {}
        for k in sorted(set(a.get("keys", {})) | set(b.get("keys", {}))):
            keys[k] = merge_shapes(a.get("keys", {}).get(k), b.get("keys", {}).get(k))
        merged["keys"] = keys
    if "items" in a or "items" in b:
        merged["items"] = merge_shapes(a.get("items"), b.get("items"))
    if "values" in a or "values" in b:
        merged["values"] = merge_shapes(a.get("values"), b.get("values"))
    return merged


def shape_of(value: Any, map_depth: int = 0) -> dict[str, Any]:
    """Recursive shape of a JSON value (``map_depth``: nested map levels at this value)."""
    t = _json_type(value)
    if t == "object" and map_depth > 0:
        values: dict[str, Any] | None = None
        for v in value.values():
            values = merge_shapes(values, shape_of(v, map_depth - 1))
        return {"type": ["object"], "values": values}
    if t == "object":
        return {
            "type": ["object"],
            "keys": {
                str(k): shape_of(v, MAP_KEYS.get(str(k), 0))
                for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))
            },
        }
    if t == "array":
        items: dict[str, Any] | None = None
        for element in value:
            items = merge_shapes(items, shape_of(element))
        return {"type": ["array"], "items": items}
    return {"type": [t]}


def compare_shapes(frozen: dict[str, Any] | None, current: dict[str, Any] | None, path: str = "$") -> list[str]:
    """Return the list of breaking differences between a frozen and a current shape.

    Breaking: a frozen key is missing, or a value takes a type that was never frozen.
    Not breaking: added keys, and ``null`` on either side (an optional value).
    Arrays that are empty on either side are not compared item-wise.
    """
    if frozen is None or current is None:
        return []
    errors: list[str] = []
    frozen_types = set(frozen["type"]) - {"null"}
    current_types = set(current["type"]) - {"null"}
    if frozen_types and current_types - frozen_types:
        errors.append(
            f"{path}: type changed from {sorted(frozen_types)} to {sorted(current_types)}"
        )
        return errors
    if "keys" in frozen and "object" in current_types:
        current_keys = current.get("keys", {})
        for key, sub in frozen["keys"].items():
            if key not in current_keys:
                errors.append(f"{path}.{key}: key removed")
            else:
                errors.extend(compare_shapes(sub, current_keys[key], f"{path}.{key}"))
    if frozen.get("items") is not None and "array" in current_types:
        errors.extend(compare_shapes(frozen["items"], current.get("items"), f"{path}[]"))
    if frozen.get("values") is not None and "object" in current_types:
        errors.extend(compare_shapes(frozen["values"], current.get("values"), f"{path}.*"))
    return errors


# ---------------------------------------------------------------------------
# Interface catalogue
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Interface:
    name: str
    kind: str  # "mcp" | "rest"
    call: Callable[[Any], Any]
    # For REST: frozen alongside the body shape.
    method: str | None = None
    path: str | None = None


def _mcp(name: str, call: Callable[[], Any]) -> Interface:
    return Interface(name=f"mcp.{name}", kind="mcp", call=lambda _client: call())


def _remember(key: str, result: dict[str, Any]) -> dict[str, Any]:
    _STATE[key] = result["data"]["id"]
    return result


def _as_reviewer(call: Callable[[], Any], set_caller: bool = True) -> Any:
    """Run ``call`` with a kb:review token declared (and, for MCP calls, as that caller).

    ENGAGEMENT_TOKENS is only set for the duration of the call: once set, it also makes
    engagement authorization strict for the other (local, unauthenticated) MCP calls.
    """
    from mcp_server.core.auth import get_current_caller, set_current_caller

    previous_caller = get_current_caller()
    previous_tokens = os.environ.get("ENGAGEMENT_TOKENS")
    os.environ["ENGAGEMENT_TOKENS"] = f"{REVIEWER_TOKEN}:kb:review"
    if set_caller:
        set_current_caller(REVIEWER_TOKEN)
    try:
        return call()
    finally:
        set_current_caller(previous_caller)
        if previous_tokens is None:
            os.environ.pop("ENGAGEMENT_TOKENS", None)
        else:
            os.environ["ENGAGEMENT_TOKENS"] = previous_tokens


def _rest(method: str, path: str, url: str | None = None, *, json_body: Any = None,
          headers: dict[str, str] | None = None, stream: bool = False, remember: str | None = None,
          reviewer: bool = False) -> Interface:
    def call(client: Any) -> Any:
        if reviewer:
            return _as_reviewer(lambda: _call(client), set_caller=False)
        return _call(client)

    def _call(client: Any) -> Any:
        if stream:
            return {"route_registered": True}
        hdrs = {"Authorization": f"Bearer {CONTRACT_TOKEN}", **(headers or {})}
        kwargs: dict[str, Any] = {"headers": hdrs}
        if json_body is not None:
            kwargs["json"] = json_body
        res = client.request(method, (url or path).format(**_STATE), **kwargs)
        content_type = res.headers.get("content-type", "").split(";")[0]
        body: Any
        if content_type == "application/json":
            body = res.json()
        else:
            body = {"text": res.text[:0]}
        if remember and isinstance(body, dict) and isinstance(body.get("data"), dict):
            _STATE[remember] = body["data"].get("id", "")
        return {
            "status_code": res.status_code,
            "content_type": content_type,
            "etag": res.headers.get("etag"),
            "body": body,
        }

    name = f"rest.{method} {path}"
    return Interface(name=name, kind="rest", call=call, method=method, path=path)


def build_catalogue() -> list[Interface]:
    from mcp_server.engagement import tools as eng
    from mcp_server.knowledge import tools as kn

    demo = DEMO_ENGAGEMENT
    scratch = SCRATCH_ENGAGEMENT
    return [
        # --- MCP Knowledge -------------------------------------------------
        _mcp("list_assets", lambda: kn.list_assets()),
        _mcp("get_asset", lambda: kn.get_asset("P-002")),
        _mcp("get_assets", lambda: kn.get_assets(["P-002", "ADR-0014", "UNKNOWN-ID"])),
        _mcp("get_decision_trail", lambda: kn.get_decision_trail("ADR-0015")),
        _mcp("get_glossary_term", lambda: kn.get_glossary_term("Closed loop")),
        _mcp("get_principles_for", lambda: kn.get_principles_for()),
        _mcp("search_assets", lambda: kn.search_assets("MCX")),
        _mcp("query_graph", lambda: kn.query_graph("MATCH (a:Asset) RETURN a.id as id, a.type as type ORDER BY a.id LIMIT 5")),
        _mcp("get_graph_summary", lambda: kn.get_graph_summary()),
        _mcp("get_knowledge_analytics", lambda: kn.get_knowledge_analytics()),
        _mcp("get_domain_prominence_report", lambda: kn.get_domain_prominence_report()),
        _mcp("list_frameworks", lambda: kn.list_frameworks()),
        _mcp("list_controls", lambda: kn.list_controls()),
        _mcp("get_compliance_trail", lambda: kn.get_compliance_trail("NIS2-ART21-2A")),
        _mcp("get_compliance_matrix", lambda: kn.get_compliance_matrix(demo, "NIS2")),
        _mcp("suggest_knowledge_improvement", lambda: kn.suggest_knowledge_improvement(
            title="Contract freeze suggestion",
            rationale="Exercise the suggestion contract.",
            suggested_change="Add a pattern describing geo-redundant deployment.",
            author="contract-test",
        )),
        _mcp("list_skills", lambda: kn.list_skills()),
        _mcp("get_skills_matrix", lambda: kn.get_skills_matrix(engagement=demo)),
        _mcp("shred_rfp", lambda: kn.shred_rfp(SAMPLE_RFP, engagement=scratch)),
        _mcp("generate_zero_draft_hld", lambda: kn.generate_zero_draft_hld(engagement=scratch)),
        _mcp("get_rfp_compliance_matrix", lambda: kn.get_rfp_compliance_matrix(engagement=scratch)),
        _mcp("trigger_rfp_elicitation", lambda: kn.trigger_rfp_elicitation(engagement=scratch)),
        # Contract 1.1 — doctrine context & option judge
        _mcp("get_doctrine_context", lambda: kn.get_doctrine_context(
            "closed loop remediation of network incidents", frameworks=["NIS2"], max_items=12)),
        _mcp("check_option", lambda: kn.check_option(SAMPLE_OPTION, subject="Network incident remediation",
                                                     frameworks=["NIS2"])),
        # Contract 1.2 — KB candidate cycle
        _mcp("submit_kb_candidate", lambda: _remember("mcp", kn.submit_kb_candidate(SAMPLE_CANDIDATE))),
        _mcp("list_kb_candidates", lambda: kn.list_kb_candidates(source="mcp")),
        _mcp("get_kb_candidate", lambda: kn.get_kb_candidate(_STATE["mcp"])),
        _mcp("review_kb_candidate", lambda: _as_reviewer(lambda: kn.review_kb_candidate(
            _STATE["mcp"], "reject", "@maintainers", reason="Contract freeze"))),
        # --- MCP Engagement ------------------------------------------------
        _mcp("get_subject", lambda: eng.get_subject("mcx-services", engagement=demo)),
        _mcp("get_subject_trajectory", lambda: eng.get_subject_trajectory("mcx-services", engagement=demo)),
        _mcp("get_board", lambda: eng.get_board(engagement=demo)),
        _mcp("get_statements", lambda: eng.get_statements(engagement=demo)),
        _mcp("get_conflicts", lambda: eng.get_conflicts(engagement=demo, status="open")),
        _mcp("get_open_questions", lambda: eng.get_open_questions(engagement=demo)),
        _mcp("get_diagram_graph", lambda: eng.get_diagram_graph(engagement=demo)),
        _mcp("get_dangling_references", lambda: eng.get_dangling_references(engagement=demo)),
        _mcp("get_render_payload", lambda: eng.get_render_payload(engagement=demo)),
        _mcp("get_engagement_export", lambda: eng.get_engagement_export(engagement=demo)),
        # --- REST ----------------------------------------------------------
        _rest("GET", "/health"),
        _rest("GET", "/healthz"),
        _rest("GET", "/ready"),
        _rest("GET", "/readyz"),
        _rest("GET", "/sse", stream=True),
        _rest("POST", "/messages", stream=True),
        _rest("GET", "/visualize"),
        _rest("GET", "/snapshot/latest"),
        _rest("GET", "/snapshot/{snapshot_id}", "/snapshot/snapshot-does-not-exist"),
        _rest("GET", "/api/knowledge/search", "/api/knowledge/search?query=MCX"),
        _rest("GET", "/api/knowledge/engagements"),
        _rest("POST", "/api/knowledge/suggestions", json_body={
            "title": "Contract freeze suggestion",
            "rationale": "Exercise the suggestion contract.",
            "suggested_change": "Add a pattern describing geo-redundant deployment.",
            "author": "contract-test",
        }),
        _rest("GET", "/api/compliance/conformity-snapshot", f"/api/compliance/conformity-snapshot?engagement={demo}&framework=NIS2"),
        _rest("GET", "/api/compliance/frameworks"),
        _rest("GET", "/api/compliance/frameworks/applicable", f"/api/compliance/frameworks/applicable?engagement={scratch}"),
        _rest("PUT", "/api/compliance/frameworks/applicable", json_body={"engagement": scratch, "frameworks": ["NIS2", "SecNumCloud"]}),
        _rest("POST", "/api/compliance/frameworks/applicable", json_body={"engagement": scratch, "frameworks": ["NIS2"]}),
        _rest("POST", "/api/rfp/shred-to-candidates", json_body={"rfp_text": SAMPLE_RFP, "engagement": scratch}),
        _rest("POST", "/api/documents/zero-draft-blueprint", json_body={"engagement": scratch}),
        _rest("POST", "/api/prose/suggest-batch", json_body={"requests": [{"blockId": "b1", "anchorIds": ["MCX"], "instructions": ""}]}),
        _rest("POST", "/api/elicitation/trigger", json_body={"engagement": scratch}),
        _rest("GET", "/api/elicitation/questions", headers={"X-Engagement-Id": demo}),
        _rest("GET", "/api/arbitration/board", headers={"X-Engagement-Id": demo}),
        _rest("GET", "/api/arbitration/conflicts", headers={"X-Engagement-Id": demo}),
        _rest("GET", "/api/arbitration/statements", headers={"X-Engagement-Id": demo}),
        _rest("GET", "/api/knowledge/context",
              "/api/knowledge/context?subject=closed%20loop%20remediation&frameworks=NIS2&max_items=12"),
        _rest("POST", "/api/knowledge/check", json_body={
            "option": SAMPLE_OPTION, "subject": "Network incident remediation", "frameworks": ["NIS2"]}),
        _rest("POST", "/api/knowledge/candidates", json_body=SAMPLE_CANDIDATE, remember="rest"),
        _rest("GET", "/api/knowledge/candidates", "/api/knowledge/candidates?source=mcp"),
        _rest("GET", "/api/knowledge/candidates/{candidate_id}", "/api/knowledge/candidates/{rest}"),
        _rest("PATCH", "/api/knowledge/candidates/{candidate_id}", "/api/knowledge/candidates/{rest}",
              json_body={"action": "reject", "reviewer": "@maintainers", "reason": "Contract freeze"},
              headers={"Authorization": f"Bearer {REVIEWER_TOKEN}"}, reviewer=True),
        _rest("GET", "/api/skills"),
        _rest("GET", "/api/skills/matrix", headers={"X-Engagement-Id": demo}),
    ]


def file_name(interface_name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in interface_name)
    return f"{safe}.shape.json"


# ---------------------------------------------------------------------------
# Isolated execution environment
# ---------------------------------------------------------------------------

@contextmanager
def isolated_environment() -> Iterator[Any]:
    """Run the calls against a scratch copy of the engagement databases.

    Yields a Starlette TestClient. Tools that write (RFP shredding, elicitation,
    applicable frameworks) only touch temporary copies; the repository is left as is.
    """
    from starlette.testclient import TestClient

    from mcp_server.core.config import server_config
    from tools.adapters.ladybug_store import LadybugGraphStore

    tmp = Path(tempfile.mkdtemp(prefix="llmops-freeze-"))
    eng_dir = tmp / "engagements"
    shutil.copytree(server_config.engagements_dir, eng_dir, ignore=shutil.ignore_patterns(f"{SCRATCH_ENGAGEMENT}*"))
    saved_eng_dir = server_config.engagements_dir
    saved_env = {k: os.environ.get(k) for k in ("SERVER_TOKEN", "LLMOPS_AUTH_TOKEN", "ENGAGEMENT_TOKENS", "KUZU_DB_PATH",
                                                  "CANDIDATES_DIR",
                                                  "OWNER_NOTIFICATION_WEBHOOK", "NOTIFICATION_WEBHOOK_URL")}
    os.environ["SERVER_TOKEN"] = CONTRACT_TOKEN
    os.environ.pop("ENGAGEMENT_TOKENS", None)
    # /visualize reads KUZU_DB_PATH (legacy default: data/kuzu_db); serve the knowledge graph.
    os.environ["KUZU_DB_PATH"] = str(server_config.knowledge_db_path)
    os.environ["CANDIDATES_DIR"] = str(tmp / "candidates")
    for k in ("LLMOPS_AUTH_TOKEN", "OWNER_NOTIFICATION_WEBHOOK", "NOTIFICATION_WEBHOOK_URL"):
        os.environ.pop(k, None)
    server_config.engagements_dir = eng_dir
    meta_file = Path("data/engagements") / f"{SCRATCH_ENGAGEMENT}.meta.json"
    try:
        from mcp_server.main import create_starlette_app

        yield TestClient(create_starlette_app())
    finally:
        LadybugGraphStore.clear_cache()
        server_config.engagements_dir = saved_eng_dir
        for k, v in saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        meta_file.unlink(missing_ok=True)
        shutil.rmtree(tmp, ignore_errors=True)


def run_catalogue() -> dict[str, Any]:
    """Call every interface (in catalogue order) and return the JSON-normalized results."""
    results: dict[str, Any] = {}
    with isolated_environment() as client:
        for interface in build_catalogue():
            results[interface.name] = json.loads(json.dumps(interface.call(client), default=str))
    return results


def current_shapes(results: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Current shape of every interface."""
    results = run_catalogue() if results is None else results
    return {name: shape_of(result) for name, result in results.items()}


def status_codes(results: dict[str, Any]) -> dict[str, int]:
    """HTTP status code of every (non-streaming) REST interface."""
    return {
        name: result["status_code"]
        for name, result in results.items()
        if name.startswith("rest.") and isinstance(result, dict) and "status_code" in result
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", nargs="+", help="Freeze only these interfaces (e.g. a newly added one).")
    parser.add_argument("--force", action="store_true", help="Overwrite existing frozen shapes (never for v1 interfaces).")
    args = parser.parse_args()

    names = set(args.only) if args.only else None
    FROZEN_DIR.mkdir(parents=True, exist_ok=True)
    results = run_catalogue()
    for name, shape in current_shapes(results).items():
        if names is not None and name not in names:
            continue
        target = FROZEN_DIR / file_name(name)
        if target.exists() and not args.force:
            print(f"skip (already frozen): {name}")
            continue
        target.write_text(json.dumps({"interface": name, "shape": shape}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"frozen: {name} -> {target.relative_to(ROOT_DIR)}")

    codes = json.loads(STATUS_CODES_FILE.read_text(encoding="utf-8")) if STATUS_CODES_FILE.exists() else {}
    for name, code in status_codes(results).items():
        if (names is None or name in names) and (name not in codes or args.force):
            codes[name] = code
    STATUS_CODES_FILE.write_text(json.dumps(codes, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
    os._exit(0)
