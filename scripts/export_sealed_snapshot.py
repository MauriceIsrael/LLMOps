"""Script to generate sealed architecture knowledge snapshots for client suites (Architecture Studio)."""

import gc
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Ensure root directory is in sys.path when script is executed directly
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mcp_server.core.config import server_config
from mcp_server.core.db import ReadOnlyKuzuClient
from mcp_server.core.version import SNAPSHOT_SCHEMA_VERSION
from pipelines import canonical, triggers
from pipelines.engagement import facts
from pipelines.ingestion.markdown_parser import MarkdownDocParser
from pipelines.knowledge_ref import (
    LEDGER_NAME,
    check_revisions,
    content_sha256,
    format_typed_id,
    knowledge_ref,
    load_ledger,
    revision_of,
    write_ledger,
)
from pipelines.snapshot_envelope import channel_envelope


def get_git_revision() -> str:
    """Retrieve current Git commit hash or fallback string."""
    try:
        rev = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT_DIR), stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        return rev
    except Exception:
        return "06f3455"


def compute_sha256(data: str | bytes) -> str:
    """Compute standard hex SHA-256 digest."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def export_sealed_snapshot(
    output_fixtures_path: Path | None = None,
    output_snapshot_dir: Path | None = None,
    db_path: Path | None = None,
    ledger_path: Path | None = None,
    record_revisions: bool = False,
) -> dict[str, Any]:
    """Generates a canonical sealed snapshot of the knowledge base.

    K3: every asset carries its ``revision``, its ``content`` and ``content_sha256`` and its ``knowledge_ref``. The content
    hash of each revision is checked against ``version-ledger.json`` (default: the one of the knowledge base directory): a
    revision whose content changed is refused; a new revision is refused unless ``record_revisions`` (the regeneration
    command) records it.
    """
    if output_fixtures_path is None:
        output_fixtures_path = ROOT_DIR / "fixtures" / "sealed_snapshot.json"
    if output_snapshot_dir is None:
        output_snapshot_dir = ROOT_DIR / "data" / "snapshots"

    output_fixtures_path.parent.mkdir(parents=True, exist_ok=True)
    output_snapshot_dir.mkdir(parents=True, exist_ok=True)

    git_rev = get_git_revision()
    now_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    snapshot_id = f"snapshot-{now_utc[:10]}-{git_rev[:7]}"

    client = ReadOnlyKuzuClient(db_path=db_path or server_config.knowledge_db_path)
    parser = MarkdownDocParser()

    # 1. Assets
    try:
        raw_assets = client.execute_cypher(
            "MATCH (a:Asset) "
            "RETURN a.id as id, a.title as title, a.type as type, a.status as status, "
            "a.confidence as confidence, a.domain as domain, a.phase as phase, "
            "a.owner as owner, a.last_reviewed as last_reviewed, a.source_path as source_path;"
        )
    except Exception:
        raw_assets = []

    # 2. Relations (SUPERSEDES)
    try:
        raw_supersedes = client.execute_cypher(
            "MATCH (a1:Asset)-[:SUPERSEDES]->(a2:Asset) "
            "RETURN a1.id as source, a2.id as target, a2.title as target_title;"
        )
    except Exception:
        raw_supersedes = []

    supersedes_map: dict[str, list[dict[str, str]]] = {}
    superseded_by_map: dict[str, list[dict[str, str]]] = {}
    for edge in raw_supersedes:
        src = edge["source"]
        tgt = edge["target"]
        title = edge.get("target_title", "")
        supersedes_map.setdefault(src, []).append({"id": tgt, "title": title})
        superseded_by_map.setdefault(tgt, []).append({"id": src, "title": ""})

    # 3. Glossary
    try:
        raw_glossary = client.execute_cypher(
            "MATCH (g:GlossaryTerm) RETURN g.term as term, g.definition as definition, g.context as context;"
        )
    except Exception:
        raw_glossary = []

    glossary = sorted(raw_glossary, key=lambda x: x.get("term", ""))

    # 4. Regulatory Controls & Compliance Index
    try:
        raw_controls = client.execute_cypher(
            "MATCH (c:Control) "
            "OPTIONAL MATCH (a:Asset)-[:IMPLEMENTS]->(c) "
            "RETURN c.id as id, c.framework as framework, c.version as version, c.title as title, "
            "c.domain as domain, c.severity as severity, c.status as status, c.target_entities as target_entities, "
            "c.external_ref as external_ref, collect(a.id) as implementing_assets;"
        )
    except Exception:
        raw_controls = []

    frameworks_map: dict[str, Any] = {}
    compliance_index: dict[str, dict[str, Any]] = {}
    controls_list = []

    # Sorted by id: the framework entry takes the version of its first control, which must not depend on the order in
    # which the graph returns rows (a framework such as GSMA mixes several versions).
    for ctrl in sorted(raw_controls, key=lambda c: c["id"]):
        cid = ctrl["id"]
        fw = ctrl.get("framework") or "UNKNOWN"
        ver = ctrl.get("version") or "1.0.0"
        title = ctrl.get("title") or cid
        impl = sorted([a for a in (ctrl.get("implementing_assets") or []) if a])

        frameworks_map.setdefault(fw, {"framework": fw, "version": ver, "controls_count": 0})
        frameworks_map[fw]["controls_count"] += 1

        ctrl_entry = {
            "id": cid,
            "framework": fw,
            "version": ver,
            "title": title,
            "domain": ctrl.get("domain"),
            "severity": ctrl.get("severity") or "mandatory",
            "implemented_by": impl,
        }
        controls_list.append(ctrl_entry)

        compliance_index.setdefault(fw, {})[cid] = {
            "title": title,
            "version": ver,
            "severity": ctrl.get("severity") or "mandatory",
            "implemented_by": impl,
        }

    controls_list.sort(key=lambda x: x["id"])

    # 5. Build enriched asset list and applicability index
    enriched_assets = []
    published: dict[str, tuple[int, str]] = {}
    applicability_index: dict[str, dict[str, list[str]]] = {}

    for item in raw_assets:
        aid = item["id"]
        atype = item.get("type", "asset")
        status = item.get("status", "active")
        confidence = item.get("confidence") or "assumed"
        domain_str = item.get("domain") or ""
        phase_str = item.get("phase") or ""

        domains = [d.strip() for d in domain_str.split(",") if d.strip()]
        phases = [p.strip() for p in phase_str.split(",") if p.strip()]

        # Resolve content & provenance from MarkdownDocParser
        src_path_str = item.get("source_path")
        doc_parsed = None
        if src_path_str and Path(src_path_str).exists():
            doc_parsed = parser.parse_file(src_path_str)

        text_content = ""
        if doc_parsed:
            text_content = doc_parsed.get("raw_content") or doc_parsed.get("content") or ""
            confidence = doc_parsed.get("confidence") or confidence

        text_hash = compute_sha256(text_content) if text_content else compute_sha256(aid)

        # K3: the exact text of the element (front matter included: it carries the revision). The database stores the body
        # only, so the source file is the reference; an element whose file cannot be read cannot be sealed.
        if not (src_path_str and Path(src_path_str).exists()):
            raise ValueError(f"asset '{aid}': source file '{src_path_str}' not found, its content cannot be sealed")
        full_content = Path(src_path_str).read_text(encoding="utf-8")
        revision = revision_of(full_content)
        typed_key = format_typed_id(aid, atype)
        published[typed_key] = (revision, content_sha256(full_content))

        provenance = {
            "document": f"{aid}.md",
            "version": str(revision),
            "section": "architecture",
            "text_sha256": text_hash,
        }

        vendor_name = None
        if confidence == "vendor-stated":
            vendor_name = item.get("owner") or "vendor"

        asset_obj: dict[str, Any] = {
            "id": aid,
            "typed_id": typed_key,
            "title": item.get("title") or aid,
            "type": atype,
            "status": status,
            "confidence": confidence,
            "domain": domain_str or None,
            "phase": phase_str or None,
            "owner": item.get("owner") or None,
            "last_reviewed": item.get("last_reviewed") or None,
            "revision": revision,
            "knowledge_ref": knowledge_ref(typed_key, revision),
            "content_sha256": published[typed_key][1],
            "content": full_content,
            "provenance": provenance,
            "supersedes": supersedes_map.get(aid, []),
            "superseded_by": superseded_by_map.get(aid, []),
        }
        if vendor_name:
            asset_obj["vendor"] = vendor_name

        enriched_assets.append(asset_obj)

        applicability_index[aid] = {
            "domains": domains,
            "phases": phases,
            "rules": [f"rule:{aid.lower()}"],
        }

    enriched_assets.sort(key=lambda x: x["id"])

    # K18: the vocabulary of architecture facts is an element of the knowledge base like the others: citable, versioned,
    # and guarded by the ledger (same {knowledgeKey, version}, same bytes).
    vocabulary = facts.load(server_config.kb_dir / "vocabulary" / "facts.yaml")
    for item in facts.public_keys(vocabulary):
        ref = item.get("asset")
        if ref and not any(a["id"] == ref for a in enriched_assets):
            raise ValueError(f"fact vocabulary: key '{item['key']}' cites asset '{ref}', which is not in the knowledge base")
    published[facts.VOCABULARY_KEY] = (vocabulary["version"], vocabulary["content_sha256"])

    # K19: the question triggers attached to the elements of the knowledge base: validated against the facts vocabulary (a rule
    # that is not valid is not published), resolved to their carrier, and guarded by the ledger like any element (K3).
    rules = triggers.load_all(server_config.kb_dir, vocabulary)
    by_asset = {a["id"]: a for a in enriched_assets}
    by_control = {c["id"]: c for c in controls_list}
    published_rules: list[dict[str, Any]] = []
    for rule in rules:
        if rule["asset"] in by_asset:
            a = by_asset[rule["asset"]]
            carrier = {"kind": "asset", "id": a["id"], "typed_id": a["typed_id"], "knowledge_ref": a["knowledge_ref"]}
        elif rule["asset"] in by_control:
            carrier = {"kind": "control", "id": rule["asset"], "framework": by_control[rule["asset"]]["framework"]}
        else:
            raise ValueError(f"trigger '{rule['trigger_id']}': carrier '{rule['asset']}' is not in the knowledge base graph (run the ingestion)")
        published[triggers.trigger_key(rule["trigger_id"])] = (rule["version"], rule["content_sha256"])
        published_rules.append(triggers.public(rule, carrier))

    ledger_file = ledger_path or (server_config.kb_dir / LEDGER_NAME)
    updated_ledger = check_revisions(load_ledger(ledger_file), published, record=record_revisions)
    if record_revisions:
        write_ledger(ledger_file, updated_ledger)

    # 6. Build sealed snapshot payload
    payload_data = {
        "applicability_index": applicability_index,
        "assets": enriched_assets,
        "glossary": glossary,
        "frameworks": sorted(list(frameworks_map.values()), key=lambda x: x["framework"]),
        "controls": controls_list,
        "compliance_index": compliance_index,
    }

    # The seal follows the suite's canonical-json v1 profile (K1): a value the profile refuses (NaN, an integer beyond
    # 2**53 - 1, a non-JSON type) fails the export instead of being approximated.
    payload_sha256 = canonical.sha256(payload_data)

    envelope = {
        "snapshot_id": snapshot_id,
        "created_at": now_utc,
        "source_revision": git_rev,
        "payload_sha256": payload_sha256,
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        **channel_envelope(payload_sha256),  # K2: emitter, checksum, rebuiltByEmitterTest, regenerate, is_provisional
        # K18: sealed by its own content_sha256 and guarded by the version ledger, but **outside** payload_sha256: a consumer
        # that recomputes the checksum over the six payload sections keeps verifying (additive, backward compatible).
        "fact_vocabulary": {
            "version": vocabulary["version"],
            "knowledge_ref": vocabulary["knowledge_ref"],
            "content_sha256": vocabulary["content_sha256"],
            "keys": facts.public_keys(vocabulary),
        },
        # K19: same treatment (own seal, outside payload_sha256); the rules are recomputed from data/kb/triggers by the emitter.
        "question_triggers": {"items": published_rules, "content_sha256": canonical.sha256(published_rules)},
        **payload_data,
    }

    formatted_json = json.dumps(envelope, indent=2, default=str) + "\n"

    # Write to fixtures/sealed_snapshot.json
    output_fixtures_path.write_text(formatted_json, encoding="utf-8")
    try:
        rel_fix = output_fixtures_path.relative_to(ROOT_DIR)
    except ValueError:
        rel_fix = output_fixtures_path
    print(f"Exported sealed snapshot fixture to: {rel_fix}")

    # Write to data/snapshots/latest.json
    latest_path = output_snapshot_dir / "latest.json"
    latest_path.write_text(formatted_json, encoding="utf-8")
    try:
        rel_latest = latest_path.relative_to(ROOT_DIR)
    except ValueError:
        rel_latest = latest_path
    print(f"Exported sealed snapshot latest to: {rel_latest}")

    # Write versioned snapshot file
    versioned_path = output_snapshot_dir / f"{snapshot_id}.json"
    versioned_path.write_text(formatted_json, encoding="utf-8")
    try:
        rel_ver = versioned_path.relative_to(ROOT_DIR)
    except ValueError:
        rel_ver = versioned_path
    print(f"Exported versioned snapshot to: {rel_ver}")

    gc.collect()
    return envelope


if __name__ == "__main__":
    export_sealed_snapshot()
    os._exit(0)

