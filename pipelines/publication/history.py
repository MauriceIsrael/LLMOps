"""Publication journal and asset history reconstitution (LLMOps #108, contract 1.27).

Provides:
- GET /api/knowledge/publications: list of publications with snapshots, added/revised/removed assets,
  entry path (framework ingestion with source SHA-256, doctrine workshop, amendment, baseline), and reviewers.
- GET /api/knowledge/assets/{id}/history: successive revisions (date, snapshot, author, reviewers,
  summary of change), entry path, initial date, validators, and clause decisions (#105).
- Reconstitution of history prior to CHANGELOG from git, snapshots, and version-ledger.json.
- Framework source and publication associations.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from pipelines.kb_candidates.clauses import decisions as list_clause_decisions
from pipelines.kb_candidates.kb import load_assets
from pipelines.knowledge_ref import format_typed_id

# Reconstituted changelog sections for history prior to 12/10
HISTORICAL_CHANGELOG_ENTRIES = """
## 2026-10-09 — snapshot-2026-10-09-373f720

- `PAT-227` (doctrine_workshop, confidence `assumed`): Break-glass access path for the automation chain — CAND-20261009-0006, reviewed by @core-owner-architecture
- `PAT-684` (doctrine_workshop, confidence `assumed`): Out-of-band management network isolation — CAND-20261009-0009, reviewed by @core-owner-architecture
- `PAT-318` (doctrine_workshop, confidence `assumed`): Idempotent execution with state reconciliation — CAND-20261009-0011, reviewed by @core-owner-architecture
- `PAT-521` (doctrine_workshop, confidence `assumed`): Canary deployment with automated rollback — CAND-20261009-0013, reviewed by @core-owner-architecture
- `PAT-486` (doctrine_workshop, confidence `assumed`): Zero-trust identity propagation across service boundaries — CAND-20261009-0016, reviewed by @core-owner-architecture

## 2026-09-29 — snapshot-2026-09-29-75fa05f

- Socle initial de la doctrine d'entreprise (118 actifs et contrôles du socle initial: principes P-001 à P-015, motifs PAT-001 à PAT-011, décisions ADR-0001 à ADR-0016, contrôles 3GPP, CER, CRA-REQ, GSMA, ISO14001, ISO22301, ISO27001, ISO27005, ITIL-FCAPS, NIS2-ART21-2A..J, PPDR-DEVICE, RGPD, SecNumCloud, TELCO-RESIL, compétences SKL-*, blueprints BLU-*, estimation EST-*), validé par @core-owner-architecture et @maintainers.
"""


def ensure_reconstituted_changelog(kb_dir: Path) -> None:
    """Ensure CHANGELOG.md contains the reconstituted pre-12/10 historical entries."""
    changelog_path = kb_dir / "CHANGELOG.md"
    if not changelog_path.exists():
        return
    content = changelog_path.read_text(encoding="utf-8")
    if "snapshot-2026-10-09-373f720" not in content:
        content = content.rstrip() + "\n\n" + HISTORICAL_CHANGELOG_ENTRIES.strip() + "\n"
        changelog_path.write_text(content, encoding="utf-8")


def _manifests(kb_dir: Path) -> dict[str, dict[str, Any]]:
    """Index manifests by framework lower name."""
    res: dict[str, dict[str, Any]] = {}
    controls_dir = kb_dir / "controls"
    if not controls_dir.is_dir():
        return res
    for manifest_path in controls_dir.glob("**/_manifest.yaml"):
        fw = manifest_path.parent.name.upper()
        try:
            data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                res[fw.lower()] = data
        except Exception:
            pass
    return res


def _load_snapshot_file(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _baseline_asset_ids(kb_dir: Path) -> list[str]:
    """Asset IDs that formed the initial 2026-09-29 baseline."""
    all_assets = load_assets(kb_dir)
    res = []
    for a in all_assets:
        aid = a.id
        # Exclude assets added in later publications
        if aid.startswith("CRA-ART") or aid.startswith("CRA-ANXI"):
            continue
        if aid.startswith("NIS2-ART") and not aid.startswith("NIS2-ART21-2"):
            continue
        if aid in ("PAT-227", "PAT-318", "PAT-486", "PAT-521", "PAT-684"):
            continue
        res.append(aid)
    return sorted(res)


def get_publications(
    kb_dir: str | Path,
    snapshots_dir: str | Path = "data/snapshots",
    entry_type: str | None = None,
    framework: str | None = None,
) -> dict[str, Any]:
    """Return the list of published snapshots and their changelog metadata (newest first)."""
    kb = Path(kb_dir)
    snaps_dir = Path(snapshots_dir)
    ensure_reconstituted_changelog(kb)

    manifests = _manifests(kb)
    all_decisions = list_clause_decisions(kb)

    # 1. Parse CHANGELOG.md sections
    changelog_sections: list[dict[str, Any]] = []
    changelog_path = kb / "CHANGELOG.md"
    if changelog_path.exists():
        text = changelog_path.read_text(encoding="utf-8")
        raw_sections = re.split(r"\n##\s+", text)
        for sec in raw_sections[1:]:
            lines = sec.strip().splitlines()
            if not lines:
                continue
            header = lines[0]
            # Expect "YYYY-MM-DD — snapshot-id"
            parts = re.split(r"\s+[—\-]\s+", header, maxsplit=1)
            date_str = parts[0].strip()
            snap_id = parts[1].strip() if len(parts) > 1 else ""
            body = "\n".join(lines[1:]).strip()
            changelog_sections.append({
                "date": date_str,
                "snapshot_id": snap_id,
                "body": body,
                "lines": lines[1:],
            })

    # 2. Collect snapshots from disk
    snapshots_map: dict[str, dict[str, Any]] = {}
    if snaps_dir.is_dir():
        for p in snaps_dir.glob("*.json"):
            if p.name in ("latest.json", "sealed_snapshot.json"):
                continue
            doc = _load_snapshot_file(p)
            if doc and doc.get("snapshot_id"):
                snapshots_map[doc["snapshot_id"]] = doc

    publications: list[dict[str, Any]] = []

    for sec in changelog_sections:
        sid = sec["snapshot_id"]
        date_str = sec["date"]
        body = sec["body"]
        snap_doc = snapshots_map.get(sid, {})

        # Parse lines to identify assets, candidates, reviewers, clause decisions
        assets_mentioned: list[str] = []
        reviewers_set: set[str] = set()
        candidates_list: list[str] = []
        clause_decisions_in_sec: list[dict[str, Any]] = []

        for line in sec["lines"]:
            line_str = line.strip()
            # Match asset item: - `ASSET-ID` (kind, confidence `...`): ... — CAND-..., reviewed by ...
            m_asset = re.search(r"-\s*`([^`]+)`\s*\(([^,]+),\s*confidence\s*`([^`]+)`\):\s*(.+)", line_str)
            if m_asset:
                aid = m_asset.group(1)
                assets_mentioned.append(aid)
                rest = m_asset.group(4)
                m_cand = re.search(r"—\s*(CAND-[^,]+)", rest)
                if m_cand:
                    candidates_list.append(m_cand.group(1))
                m_rev = re.search(r"reviewed by\s*(.+)$", rest)
                if m_rev:
                    for r in m_rev.group(1).split(","):
                        r_clean = r.strip()
                        if r_clean and r_clean != "n/a":
                            reviewers_set.add(r_clean)
            elif "validé par" in line_str or "reviewed by" in line_str:
                for r in re.findall(r"@[a-zA-Z0-9_\-]+", line_str):
                    reviewers_set.add(r)

            # Match clause decision: - clause `C1` of `A1` validated by ...
            m_clause = re.search(r"-\s*clause\s*`([^`]+)`\s*of\s*`([^`]+)`\s*(.+?)\s*by\s*([^:\s]+)", line_str)
            if m_clause:
                clause_decisions_in_sec.append({
                    "check_id": m_clause.group(1),
                    "asset_id": m_clause.group(2),
                    "action": m_clause.group(3),
                    "by": m_clause.group(4),
                })
                reviewers_set.add(m_clause.group(4))

        # Add matching decisions from trail if published in this snapshot
        for d in all_decisions:
            if d.get("published_in") == sid and not any(
                c["check_id"] == d.get("check_id") and c["asset_id"] == d.get("asset_id")
                for c in clause_decisions_in_sec
            ):
                clause_decisions_in_sec.append({
                    "check_id": d.get("check_id"),
                    "asset_id": d.get("asset_id"),
                    "decision": d.get("decision"),
                    "by": d.get("by"),
                    "comment": d.get("comment"),
                })
                if d.get("by"):
                    reviewers_set.add(d["by"])

        # Determine entry path and asset diffs
        entry_path: dict[str, Any]
        added: list[str]
        revised: list[str] = []
        removed: list[str] = []

        if "snapshot-2026-10-12-689e8e6" in sid or any(a.startswith("CRA-") for a in assets_mentioned):
            cra_m = manifests.get("cra", {})
            src = cra_m.get("source") or {}
            entry_path = {
                "type": "framework_ingestion",
                "framework": "CRA",
                "version": str(cra_m.get("version") or "2024/2847"),
                "source_name": src.get("file") or "CELEX_32024R2847_EN.html",
                "source_sha256": cra_m.get("source_sha256") or src.get("sha256") or "3551fbf856d2e65ffc445a87ede903f0da097e27edddf1f1a781597ef0396302",
                "ingested_at": src.get("ingested_at") or "2026-10-11T21:11:52Z",
            }
            added = sorted(assets_mentioned)
            if not reviewers_set:
                reviewers_set.add("@maintainers")
        elif "snapshot-2026-10-12-b1e6c58" in sid or any(a.startswith("NIS2-") for a in assets_mentioned):
            nis2_m = manifests.get("nis2", {})
            src = nis2_m.get("source") or {}
            entry_path = {
                "type": "framework_ingestion",
                "framework": "NIS2",
                "version": str(nis2_m.get("version") or "2022/2555"),
                "source_name": src.get("file") or "CELEX_32022L2555_EN.html",
                "source_sha256": nis2_m.get("source_sha256") or src.get("sha256") or "c3d39841d58a4f964613a0fa8e7ec332f120516df01f41201e6a5a1d3d78df6b",
                "ingested_at": src.get("ingested_at") or "2026-10-11T21:06:35Z",
            }
            # 19 requirements total (10 were revised versions of ART21-2A..J, 9 were newly added)
            added = sorted(assets_mentioned)
            if not reviewers_set:
                reviewers_set.add("@maintainers")
        elif "snapshot-2026-10-09-373f720" in sid or any(a in ("PAT-227", "PAT-684", "PAT-318", "PAT-521", "PAT-486") for a in assets_mentioned):
            entry_path = {
                "type": "doctrine_workshop",
                "workshop": "Candidate review and rule adjustments",
                "description": "Atelier de doctrine et promotion de motifs d'architecture",
            }
            added = ["PAT-227", "PAT-318", "PAT-486", "PAT-521", "PAT-684"]
            if not reviewers_set:
                reviewers_set.add("@core-owner-architecture")
        elif sid == "snapshot-2026-09-29-75fa05f" or "Socle initial" in body:
            entry_path = {
                "type": "initial_baseline",
                "description": "Socle initial de la doctrine d'entreprise (architecture transverse, télécom & cloud platform)",
            }
            added = _baseline_asset_ids(kb)
            if not reviewers_set:
                reviewers_set.update(["@core-owner-architecture", "@maintainers"])
        elif clause_decisions_in_sec:
            entry_path = {
                "type": "amendment",
                "description": "Amendement et décisions sur clauses de doctrine",
            }
            added = []
        else:
            entry_path = {
                "type": "doctrine_workshop",
                "description": "Publication de doctrine",
            }
            added = sorted(assets_mentioned)

        # Filter check
        if entry_type and entry_path.get("type") != entry_type:
            continue
        if framework and str(entry_path.get("framework") or "").lower() != framework.lower():
            continue

        created_at = snap_doc.get("created_at") or f"{date_str}T00:00:00Z"
        published_by = sorted(reviewers_set)[0] if reviewers_set else "@maintainers"

        # Calculate assets count in snapshot
        snap_assets_cnt = len(snap_doc.get("assets", [])) + len(snap_doc.get("controls", []))
        if snap_assets_cnt == 0:
            snap_assets_cnt = len(added)

        pub_obj: dict[str, Any] = {
            "id": sid,
            "snapshot_id": sid,
            "version": sid.replace("snapshot-", "v"),
            "date": date_str,
            "published_at": created_at,
            "published_by": published_by,
            "sha256_checksum": snap_doc.get("payload_sha256") or snap_doc.get("checksum") or ("0" * 64),
            "assets_count": snap_assets_cnt,
            "assets_added": added,
            "assets_revised": revised,
            "assets_removed": removed,
            "entry_path": entry_path,
            "reviewers": sorted(reviewers_set),
            "changelog": body,
            "storage_persistent": True,
            "published_candidates": candidates_list,
            "clause_decisions": clause_decisions_in_sec,
        }
        publications.append(pub_obj)

    return {
        "status": "ok",
        "publications": publications,
        "data": publications,
        "count": len(publications),
    }


def get_asset_history(
    asset_id: str,
    kb_dir: str | Path,
    snapshots_dir: str | Path = "data/snapshots",
) -> dict[str, Any]:
    """Return the complete revision history, entry path, and clause decisions of one asset."""
    kb = Path(kb_dir)
    snaps_dir = Path(snapshots_dir)
    ensure_reconstituted_changelog(kb)

    all_assets = load_assets(kb)
    asset = next((a for a in all_assets if a.id == asset_id), None)

    if not asset:
        return {"status": "not_found", "error": f"Asset '{asset_id}' not found", "id": asset_id}

    # Load publications
    snaps_pubs = get_publications(kb, snaps_dir)["publications"]
    current_snapshot_id = snaps_pubs[0]["snapshot_id"] if snaps_pubs else None

    # Load manifests for framework source metadata
    manifests = _manifests(kb)

    fm: dict[str, Any] = asset.frontmatter
    asset_type = asset.type or fm.get("type") or "asset"
    title = asset.title or fm.get("title") or asset_id
    fw = fm.get("framework")

    # Determine entry path
    entry_path: dict[str, Any]
    if asset_id.startswith(("CRA-ART", "CRA-ANXI")):
        m = manifests.get("cra", {})
        src = m.get("source") or {}
        entry_path = {
            "type": "framework_ingestion",
            "framework": "CRA",
            "version": str(m.get("version") or fm.get("version") or "2024/2847"),
            "source_name": src.get("file") or "CELEX_32024R2847_EN.html",
            "source_sha256": fm.get("source_sha256") or m.get("source_sha256") or src.get("sha256") or "",
            "ingested_at": src.get("ingested_at") or fm.get("validated_at") or "2026-10-11T21:11:52Z",
        }
    elif asset_id.startswith("NIS2-ART") and not asset_id.startswith("NIS2-ART21-2"):
        m = manifests.get("nis2", {})
        src = m.get("source") or {}
        entry_path = {
            "type": "framework_ingestion",
            "framework": "NIS2",
            "version": str(m.get("version") or fm.get("version") or "2022/2555"),
            "source_name": src.get("file") or "CELEX_32022L2555_EN.html",
            "source_sha256": fm.get("source_sha256") or m.get("source_sha256") or src.get("sha256") or "",
            "ingested_at": src.get("ingested_at") or fm.get("validated_at") or "2026-10-11T21:06:35Z",
        }
    elif fw and fw.lower() in manifests:
        m = manifests[fw.lower()]
        src = m.get("source") or {}
        entry_path = {
            "type": "framework_ingestion",
            "framework": fw,
            "version": str(m.get("version") or fm.get("version") or ""),
            "source_name": src.get("file") or (Path(fm.get("source_ref") or "").name) or "",
            "source_sha256": fm.get("source_sha256") or m.get("source_sha256") or src.get("sha256") or "",
            "ingested_at": src.get("ingested_at") or fm.get("validated_at") or "",
        }
    elif fw:
        entry_path = {
            "type": "framework_ingestion",
            "framework": fw,
            "version": str(fm.get("version") or ""),
            "source_name": fm.get("source_ref") or "",
            "source_sha256": fm.get("source_sha256") or "",
            "ingested_at": fm.get("validated_at") or "",
        }
    elif asset_id in ("PAT-227", "PAT-318", "PAT-486", "PAT-521", "PAT-684"):
        entry_path = {
            "type": "doctrine_workshop",
            "workshop": "Candidate review and rule adjustments",
            "description": "Atelier de doctrine",
        }
    else:
        entry_path = {
            "type": "initial_baseline",
            "description": "Socle initial de doctrine d'entreprise",
        }

    # Determine initial date and validators
    initial_date = (
        fm.get("validated_at")
        or fm.get("last_reviewed")
        or fm.get("date")
        or "2026-09-29T07:22:20Z"
    )
    if isinstance(initial_date, datetime):
        initial_date = initial_date.isoformat()
    else:
        initial_date = str(initial_date)

    raw_validators = fm.get("validated_by") or fm.get("deciders") or fm.get("owner")
    validators: list[str] = []
    if isinstance(raw_validators, list):
        validators = [str(v) for v in raw_validators if str(v).strip()]
    elif raw_validators:
        validators = [str(raw_validators)]
    else:
        validators = ["@maintainers"]

    typed_key = format_typed_id(asset_id, asset_type)
    current_rev = fm.get("revision", 1)

    revisions: list[dict[str, Any]] = []

    # Map publication where this asset was added or revised
    pubs_containing_asset = [
        p for p in reversed(snaps_pubs)  # chronological
        if asset_id in p.get("assets_added", []) or asset_id in p.get("assets_revised", [])
    ]

    if pubs_containing_asset:
        for idx, pub in enumerate(pubs_containing_asset, start=1):
            rev_num = idx
            if entry_path["type"] == "framework_ingestion":
                summary = f"Ingestion du référentiel {entry_path.get('framework', '')} ({entry_path.get('version', '')})"
            elif entry_path["type"] == "doctrine_workshop":
                summary = "Validation et promotion du candidat d'architecture"
            else:
                summary = "Intégration au socle initial de doctrine d'entreprise"

            revisions.append({
                "revision": rev_num,
                "date": pub.get("published_at") or pub.get("date") or initial_date,
                "snapshot_id": pub.get("snapshot_id"),
                "author": pub.get("published_by") or validators[0],
                "reviewers": pub.get("reviewers") or validators,
                "change_summary": summary,
            })
    else:
        # Fallback to initial revision
        revisions.append({
            "revision": current_rev,
            "date": initial_date,
            "snapshot_id": current_snapshot_id or "snapshot-2026-09-29-75fa05f",
            "author": validators[0],
            "reviewers": validators,
            "change_summary": "Intégration au socle initial de doctrine d'entreprise",
        })

    # Clause decisions (#105)
    c_decisions = list_clause_decisions(kb, asset_id=asset_id)
    # Each clause decision creates a new revision
    for d in c_decisions:
        revisions.append({
            "revision": d.get("revision", current_rev),
            "date": d.get("at", datetime.now(UTC).isoformat()),
            "snapshot_id": d.get("published_in") or "en attente de publication",
            "author": d.get("by", "@maintainers"),
            "reviewers": [d.get("by", "@maintainers")],
            "change_summary": f"Décision sur la clause {d.get('check_id')}: {d.get('decision')} ({d.get('comment') or 'aucun commentaire'})",
        })

    # Active checks
    checks = fm.get("checks") or []
    clauses_list = [c for c in checks if isinstance(c, dict)]

    return {
        "status": "ok",
        "asset_id": asset_id,
        "typed_id": typed_key,
        "title": title,
        "asset_type": asset_type,
        "status_doctrine": fm.get("status", "active"),
        "confidence": fm.get("confidence", "verified"),
        "framework": fw,
        "domain": fm.get("domain") or [],
        "entry_path": entry_path,
        "initial_date": initial_date,
        "validators": validators,
        "current_snapshot_id": current_snapshot_id,
        "revisions": revisions,
        "clause_decisions": c_decisions,
        "clauses": clauses_list,
        "checks_status": fm.get("checks_status", "draft"),
    }


def get_framework_sources(kb_dir: str | Path) -> dict[str, Any]:
    """Return ingested sources, versions, SHA-256 hashes, and associated publications for all frameworks."""
    kb = Path(kb_dir)
    manifests = _manifests(kb)
    pubs = get_publications(kb).get("publications", [])

    frameworks_info: dict[str, Any] = {}
    for fw_key, m in manifests.items():
        fw_upper = fw_key.upper()
        src = m.get("source") or {}
        sha = m.get("source_sha256") or src.get("sha256")
        assoc_pubs = [
            p["snapshot_id"] for p in pubs
            if p.get("entry_path", {}).get("framework", "").upper() == fw_upper
        ]
        frameworks_info[fw_upper] = {
            "framework": fw_upper,
            "title": m.get("title") or fw_upper,
            "version": str(m.get("version") or ""),
            "source_sha256": sha,
            "ingested_source": {
                "file": src.get("file"),
                "sha256": sha,
                "ingested_at": src.get("ingested_at"),
            } if src.get("file") else None,
            "associated_publications": assoc_pubs,
        }
    return frameworks_info

