"""Vérification de fraîcheur et cycle de vie des exigences normatives et doctrines (Issue #131).

Permet d'auditer régulièrement la fraîcheur des référentiels (NIS2, RGPD, 3GPP, GSMA, ISO...)
et des doctrines internes :
1. Suivi des métadonnées de cycle de vie (source_version, last_verified_at, review_cycle_days, upstream_standard_ref).
2. Détection des échéances de revue dépassées (overdue).
3. Détection des évolutions de sources ou versions amont (drifts) nécessitant une revalidation des clauses checks: par l'owner.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from pipelines.frameworks.ingest import load_manifest
from pipelines.kb_candidates.kb import load_assets, split_frontmatter

DEFAULT_REVIEW_CYCLE_DAYS = 180


def _parse_date(val: Any) -> date | None:
    if not val:
        return None
    val_str = str(val).strip()
    if not val_str:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(val_str[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
    return None


@dataclass
class OverdueItem:
    id: str
    type: str
    title: str
    owner: str
    last_verified: str | None
    review_cycle_days: int
    due_date: str
    days_overdue: int


@dataclass
class SourceDriftItem:
    control_id: str
    framework: str
    owner: str
    current_version: str | None
    manifest_version: str | None
    upstream_standard_ref: str | None
    upstream_latest_version: str | None
    source_sha256_changed: bool
    checks_count: int
    validated_checks_count: int
    action_required: str  # "revalidate_checks" | "review_upstream_release"


@dataclass
class DoctrineDependencyAlert:
    asset_id: str
    asset_type: str
    asset_title: str
    owner: str
    affected_controls: list[str]


def check_kb_freshness(
    kb_dir: str | Path = "data/kb",
    now: datetime | None = None,
    default_review_cycle_days: int = DEFAULT_REVIEW_CYCLE_DAYS,
    upstream_versions: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Audit complet de la fraîcheur normative et doctrinale."""
    kb = Path(kb_dir)
    today = (now or datetime.now(UTC)).date()
    upstream_versions = upstream_versions or {}

    controls_dir = kb / "controls"
    frameworks: list[str] = sorted(d.name for d in controls_dir.iterdir() if d.is_dir()) if controls_dir.is_dir() else []

    manifests: dict[str, dict[str, Any]] = {}
    for fw in frameworks:
        mf = load_manifest(kb, fw)
        if mf:
            manifests[fw.lower()] = mf

    all_assets = load_assets(kb)
    active_assets = [a for a in all_assets if a.frontmatter.get("status", "active") == "active"]

    overdue_items: list[OverdueItem] = []
    source_drifts: list[SourceDriftItem] = []
    drifted_control_ids: set[str] = set()

    for asset in active_assets:
        fm = asset.frontmatter
        owner = str(fm.get("owner") or "unassigned")
        if not owner.startswith("@") and owner != "unassigned":
            owner = f"@{owner}"

        cycle_days = int(fm.get("review_cycle_days") or default_review_cycle_days)
        last_date = _parse_date(fm.get("last_verified_at") or fm.get("last_reviewed"))
        review_by = _parse_date(fm.get("review_by"))

        due_date: date | None = None
        if review_by:
            due_date = review_by
        elif last_date:
            due_date = last_date + timedelta(days=cycle_days)

        if due_date and today > due_date:
            days_overdue = (today - due_date).days
            overdue_items.append(
                OverdueItem(
                    id=asset.id,
                    type=asset.type,
                    title=asset.title,
                    owner=owner,
                    last_verified=last_date.isoformat() if last_date else None,
                    review_cycle_days=cycle_days,
                    due_date=due_date.isoformat(),
                    days_overdue=days_overdue,
                )
            )

        # Vérification spécifique des contrôles réglementaires (drifts)
        if asset.type == "control":
            fw = str(fm.get("framework") or "").lower()
            manifest = manifests.get(fw)

            ctrl_version = str(fm.get("source_version") or fm.get("version") or "")
            manifest_version = str(manifest.get("version") or "") if manifest else None
            upstream_latest = upstream_versions.get(fw.upper()) or upstream_versions.get(fw)
            if not upstream_latest and manifest:
                upstream_latest = manifest.get("upstream_latest_version")

            ref_path = fm.get("upstream_standard_ref")
            if ref_path and not upstream_latest:
                for candidate_p in (kb / ref_path, kb / "standards" / ref_path):
                    if candidate_p.is_file():
                        try:
                            import yaml
                            txt = candidate_p.read_text(encoding="utf-8")
                            if txt.startswith("---"):
                                parts = txt.split("---", 2)
                                if len(parts) >= 3:
                                    std_fm = yaml.safe_load(parts[1]) or {}
                                    upstream_latest = str(std_fm.get("version") or "")
                        except Exception:
                            pass
                        break

            ctrl_sha = fm.get("source_sha256")
            manifest_sha = manifest.get("source_sha256") if manifest else None
            sha_changed = bool(manifest_sha and ctrl_sha and manifest_sha != ctrl_sha)

            version_changed = bool(manifest_version and ctrl_version and manifest_version != ctrl_version)
            upstream_changed = bool(upstream_latest and ctrl_version and upstream_latest != ctrl_version)

            if sha_changed or version_changed or upstream_changed:
                checks = fm.get("checks") or []
                validated_checks = sum(1 for c in checks if isinstance(c, dict) and c.get("status") == "validated")
                drifted_control_ids.add(asset.id)
                source_drifts.append(
                    SourceDriftItem(
                        control_id=asset.id,
                        framework=fm.get("framework") or fw.upper(),
                        owner=owner,
                        current_version=ctrl_version or None,
                        manifest_version=manifest_version,
                        upstream_standard_ref=fm.get("upstream_standard_ref") or (manifest.get("upstream_standard_ref") if manifest else None),
                        upstream_latest_version=upstream_latest,
                        source_sha256_changed=sha_changed,
                        checks_count=len(checks),
                        validated_checks_count=validated_checks,
                        action_required="revalidate_checks" if validated_checks > 0 else "review_upstream_release",
                    )
                )

    # Détection des doctrines dont les contrôles mis en œuvre ont évolué
    doctrine_alerts: list[DoctrineDependencyAlert] = []
    for asset in active_assets:
        if asset.type in ("decision", "pattern", "principle"):
            fm = asset.frontmatter
            impls = fm.get("implements_controls") or []
            if isinstance(impls, str):
                impls = [impls]
            affected = sorted(set(impls) & drifted_control_ids)
            if affected:
                owner = str(fm.get("owner") or "unassigned")
                if not owner.startswith("@") and owner != "unassigned":
                    owner = f"@{owner}"
                doctrine_alerts.append(
                    DoctrineDependencyAlert(
                        asset_id=asset.id,
                        asset_type=asset.type,
                        asset_title=asset.title,
                        owner=owner,
                        affected_controls=affected,
                    )
                )

    # Regroupement des alertes par propriétaire (owner)
    alerts_by_owner: dict[str, dict[str, Any]] = {}
    for item in overdue_items:
        entry = alerts_by_owner.setdefault(item.owner, {"overdue_count": 0, "drift_count": 0, "controls_to_revalidate": [], "overdue_assets": []})
        entry["overdue_count"] += 1
        entry["overdue_assets"].append(item.id)

    for drift in source_drifts:
        entry = alerts_by_owner.setdefault(drift.owner, {"overdue_count": 0, "drift_count": 0, "controls_to_revalidate": [], "overdue_assets": []})
        entry["drift_count"] += 1
        if drift.action_required == "revalidate_checks":
            entry["controls_to_revalidate"].append(drift.control_id)

    is_ok = len(overdue_items) == 0 and len(source_drifts) == 0

    return {
        "status": "ok" if is_ok else "needs_update",
        "checked_at": today.isoformat(),
        "summary": {
            "total_assets_checked": len(active_assets),
            "total_controls": sum(1 for a in active_assets if a.type == "control"),
            "total_standards": sum(1 for a in active_assets if a.type == "standard"),
            "overdue_count": len(overdue_items),
            "source_drift_count": len(source_drifts),
            "revalidation_required_count": sum(1 for d in source_drifts if d.action_required == "revalidate_checks"),
            "affected_doctrine_count": len(doctrine_alerts),
        },
        "overdue_reviews": [asdict(i) for i in sorted(overdue_items, key=lambda x: -x.days_overdue)],
        "source_drifts": [asdict(d) for d in sorted(source_drifts, key=lambda x: x.control_id)],
        "doctrine_dependencies": [asdict(a) for a in sorted(doctrine_alerts, key=lambda x: x.asset_id)],
        "alerts_by_owner": dict(sorted(alerts_by_owner.items())),
    }


def render_freshness_report(report: dict[str, Any]) -> str:
    """Rendu Markdown du rapport de veille de fraîcheur réglementaire et doctrinale."""
    s = report["summary"]
    lines = [
        "# Rapport de veille et fraîcheur documentaire (Normes & Doctrines)",
        "",
        f"- **Date de vérification** : `{report['checked_at']}`",
        f"- **Statut global** : **{report['status'].upper()}**",
        f"- **Actifs vérifiés** : {s['total_assets_checked']}",
        f"- **Échéances dépassées (overdue)** : {s['overdue_count']}",
        f"- **Dérives normatives détectées (drifts)** : {s['source_drift_count']}",
        f"- **Contrôles exigeant une revalidation des clauses** : {s['revalidation_required_count']}",
        "",
        "## 1. Alertes par propriétaire de domaine",
        "",
    ]
    owners = report.get("alerts_by_owner") or {}
    if not owners:
        lines.append("_Aucune alerte : tous les référentiels et doctrines sont à jour._\n")
    else:
        lines.append("| Propriétaire (Owner) | Revues en retard | Dérives de source | Contrôles à revalider |")
        lines.append("|---|---:|---:|---|")
        for owner, a in owners.items():
            to_reval = ", ".join(f"`{c}`" for c in a["controls_to_revalidate"][:5])
            if len(a["controls_to_revalidate"]) > 5:
                to_reval += f" (+{len(a['controls_to_revalidate']) - 5})"
            lines.append(f"| **{owner}** | {a['overdue_count']} | {a['drift_count']} | {to_reval or '—'} |")
        lines.append("")

    drifts = report.get("source_drifts") or []
    if drifts:
        lines.append("## 2. Dérives de standards amont & textes sources (Drifts)")
        lines.append("")
        lines.append("| Contrôle | Référentiel | Version actuelle | Version amont / manifeste | Clauses validées | Action requise |")
        lines.append("|---|---|---|---|---:|---|")
        for d in drifts:
            v_amont = d.get("upstream_latest_version") or d.get("manifest_version") or "—"
            lines.append(f"| `{d['control_id']}` | {d['framework']} | {d['current_version'] or '—'} | {v_amont} | {d['validated_checks_count']} | **{d['action_required']}** |")
        lines.append("")

    overdue = report.get("overdue_reviews") or []
    if overdue:
        lines.append("## 3. Échéances de revue périodique dépassées (Overdue)")
        lines.append("")
        lines.append("| Identifiant | Type | Propriétaire | Dernière vérification | Échéance | Retard |")
        lines.append("|---|---|---|---|---|---:|")
        for o in overdue[:30]:
            lines.append(f"| `{o['id']}` | {o['type']} | {o['owner']} | {o['last_verified'] or '—'} | {o['due_date']} | **+{o['days_overdue']} j** |")
        if len(overdue) > 30:
            lines.append(f"\n_... et {len(overdue) - 30} autre(s) élément(s) en retard._")
        lines.append("")

    return "\n".join(lines)
