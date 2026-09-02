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
from pipelines.ingestion.markdown_parser import MarkdownDocParser


def get_git_revision() -> str:
    """Retrieve current Git commit hash or fallback string."""
    try:
        rev = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT_DIR), stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        return rev
    except Exception:
        return "06f3455"


def format_typed_id(asset_id: str, asset_type: str | None) -> str:
    """Format an asset identifier with a normalized type prefix (type:slug)."""
    t = (asset_type or "").lower()
    if t in ("decision", "adr") or asset_id.startswith("ADR-"):
        return f"decision:{asset_id}"
    elif t in ("principle",) or asset_id.startswith("P-"):
        return f"principle:{asset_id}"
    elif t in ("pattern",) or asset_id.startswith("PAT-"):
        return f"pattern:{asset_id}"
    elif t in ("template",) or asset_id.startswith("TPL-"):
        return f"template:{asset_id}"
    elif t in ("risk",) or asset_id.startswith("RSK-") or asset_id.startswith("R-"):
        return f"risk:{asset_id}"
    elif t in ("questionnaire", "framework"):
        return f"{t}:{asset_id}"
    return f"asset:{asset_id}"


def compute_sha256(data: str | bytes) -> str:
    """Compute standard hex SHA-256 digest."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def export_sealed_snapshot(
    output_fixtures_path: Path | None = None,
    output_snapshot_dir: Path | None = None,
) -> dict[str, Any]:
    """Generates a canonical sealed snapshot of the knowledge base."""
    if output_fixtures_path is None:
        output_fixtures_path = ROOT_DIR / "fixtures" / "sealed_snapshot.json"
    if output_snapshot_dir is None:
        output_snapshot_dir = ROOT_DIR / "data" / "snapshots"

    output_fixtures_path.parent.mkdir(parents=True, exist_ok=True)
    output_snapshot_dir.mkdir(parents=True, exist_ok=True)

    git_rev = get_git_revision()
    now_utc = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    snapshot_id = f"snapshot-{now_utc[:10]}-{git_rev[:7]}"

    client = ReadOnlyKuzuClient(db_path=server_config.knowledge_db_path)
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

    # 4. Build enriched asset list and applicability index
    enriched_assets = []
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

        provenance = {
            "document": f"{aid}.md",
            "version": "1.0",
            "section": "architecture",
            "text_sha256": text_hash,
        }

        vendor_name = None
        if confidence == "vendor-stated":
            vendor_name = item.get("owner") or "vendor"

        asset_obj: dict[str, Any] = {
            "id": aid,
            "typed_id": format_typed_id(aid, atype),
            "title": item.get("title") or aid,
            "type": atype,
            "status": status,
            "confidence": confidence,
            "domain": domain_str or None,
            "phase": phase_str or None,
            "owner": item.get("owner") or None,
            "last_reviewed": item.get("last_reviewed") or None,
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

    # 5. Build sealed snapshot payload
    payload_data = {
        "applicability_index": applicability_index,
        "assets": enriched_assets,
        "glossary": glossary,
    }

    # Canonical serialization to compute checksum
    canonical_payload_json = json.dumps(payload_data, sort_keys=True, indent=2, default=str)
    payload_sha256 = compute_sha256(canonical_payload_json)

    envelope = {
        "snapshot_id": snapshot_id,
        "created_at": now_utc,
        "source_revision": git_rev,
        "payload_sha256": f"sha256:{payload_sha256}",
        "schema_version": "1.0",
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

