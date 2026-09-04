"""Moteur de réconciliation sémantique et d'audit de conformité réglementaire.

Fournit le couplage bidirectionnel entre :
1. Les référentiels réglementaires externes (SecNumCloud, ISO 27001, NIS 2, 3GPP).
2. Les assets d'architecture internes (ADRs, Patterns, Principes).

Fonctionnalités :
- Détection sémantique automatique des contrôles applicables à un asset (Bottom-Up).
- Réconciliation et mise à jour des métadonnées frontmatter Markdown (`implements_controls`).
- Audit continu de complétude et détection des manques réglementaires (Top-Down Gap Analysis).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class RegulatoryControl:
    id: str
    framework: str
    version: str
    title: str
    title_fr: str | None
    domain: list[str]
    severity: str
    terms: list[str]
    source_ref: str | None
    summary_text: str = ""
    file_path: Path | None = None


@dataclass
class MatchResult:
    control_id: str
    framework: str
    control_title: str
    confidence_score: float
    matched_terms: list[str] = field(default_factory=list)
    matched_domains: list[str] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)


# Mappings sémantiques explicites éprouvés pour le socle d'architecture
EXPLICIT_KB_ALIGNMENTS: dict[str, list[str]] = {
    # ADRs
    "ADR-0001": ["ISO-27001-A8-09", "NIS2-ART21-2A"],
    "ADR-0002": ["ISO-27001-A8-09", "NIS2-ART21-2F"],
    "ADR-0005": ["3GPP-TS33501-SBI", "3GPP-TS33501-SEPP", "NIS2-ART21-2D", "ISO-27001-A5-15", "SNC-REQ-03"],
    "ADR-0006": ["ISO-27001-A8-09", "SNC-REQ-04"],
    "ADR-0007": ["SNC-REQ-02", "SNC-REQ-06", "NIS2-ART21-2C", "3GPP-TS33179-ISOLATED"],
    "ADR-0008": ["SNC-REQ-05", "ISO-27001-A8-28"],
    "ADR-0011": ["SNC-REQ-01", "NIS2-ART21-2H"],
    "ADR-0012": ["ISO-27001-A8-08"],
    "ADR-0013": ["ISO-27001-A8-01", "3GPP-TS33179-AFFILIATION"],
    # Patterns
    "PAT-001": ["NIS2-ART21-2B"],
    "PAT-002": ["NIS2-ART21-2E", "ISO-27001-A8-08"],
    "PAT-003": ["NIS2-ART21-2C", "SNC-REQ-06"],
    "PAT-004": ["NIS2-ART21-2C", "NIS2-ART21-2J", "3GPP-TS33179-ISOLATED", "3GPP-TS33179-KMS", "SNC-REQ-02", "SNC-REQ-03", "ISO-27001-A8-01", "ISO-27001-A8-24"],
    "PAT-005": ["NIS2-ART21-2F", "SNC-REQ-05", "ISO-27001-A8-28"],
    "PAT-006": ["NIS2-ART21-2D", "3GPP-TS33501-SBI", "3GPP-TS33501-SEPP", "SNC-REQ-01", "ISO-27001-A5-15"],
    "PAT-007": ["NIS2-ART21-2H"],
    # Principles
    "P-001": ["NIS2-ART21-2A", "ISO-27001-A8-09", "SNC-REQ-04"],
    "P-002": ["NIS2-ART21-2B"],
    "P-003": ["NIS2-ART21-2G"],
    "P-005": ["NIS2-ART21-2E", "ISO-27001-A8-08"],
    "P-007": ["NIS2-ART21-2D", "ISO-27001-A5-15", "3GPP-TS33501-SEPP"],
    "P-009": ["NIS2-ART21-2C", "SNC-REQ-02", "SNC-REQ-06"],
    "P-010": ["NIS2-ART21-2I", "ISO-27001-A8-09"],
    "P-011": ["SNC-REQ-05", "ISO-27001-A8-28"],
    "P-015": ["NIS2-ART21-2H", "SNC-REQ-01", "ISO-27001-A8-24"],
}


def load_all_controls(controls_dir: Path | str = "data/kb/controls") -> dict[str, RegulatoryControl]:
    """Charge l'ensemble des contrôles réglementaires depuis les fichiers Markdown."""
    base = Path(controls_dir)
    controls: dict[str, RegulatoryControl] = {}

    if not base.exists():
        return controls

    for file_path in base.rglob("*.md"):
        if file_path.name.startswith("_") or file_path.name.lower() in ("readme.md", "index.md"):
            continue

        try:
            content = file_path.read_text(encoding="utf-8")
            fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
            if not fm_match:
                continue

            fm = yaml.safe_load(fm_match.group(1)) or {}
            body = fm_match.group(2)

            cid = fm.get("id") or file_path.stem
            if not cid:
                continue

            domain = fm.get("domain", [])
            if isinstance(domain, str):
                domain = [domain]

            terms = fm.get("terms", [])
            if isinstance(terms, str):
                terms = [terms]

            controls[cid] = RegulatoryControl(
                id=cid,
                framework=fm.get("framework", "UNKNOWN"),
                version=str(fm.get("version", "1.0")),
                title=fm.get("title", cid),
                title_fr=fm.get("title_fr"),
                domain=[d.lower() for d in domain],
                severity=fm.get("severity", "mandatory"),
                terms=[t.lower() for t in terms],
                source_ref=fm.get("source_ref"),
                summary_text=body[:1000].lower(),
                file_path=file_path,
            )
        except Exception:
            continue

    return controls


def match_text_to_controls(
    title: str,
    text: str,
    domain: list[str] | str | None = None,
    terms: list[str] | None = None,
    controls: dict[str, RegulatoryControl] | None = None,
    threshold: float = 0.35,
) -> list[MatchResult]:
    """Détecte les contrôles applicables à un texte (proposition, suggestion ou asset) par affinité sémantique."""
    if controls is None:
        controls = load_all_controls()

    full_text = f"{title}\n{text}".lower()
    asset_domains = [domain.lower()] if isinstance(domain, str) else [d.lower() for d in (domain or [])]
    asset_terms = [t.lower() for t in (terms or [])]

    results: list[MatchResult] = []

    for cid, ctrl in controls.items():
        score = 0.0
        matched_terms = []
        matched_domains = []
        matched_keywords = []

        # 1. Correspondance sur les termes normés (poids très fort)
        for ct in ctrl.terms:
            clean_term = ct.replace("-", " ")
            if ct in full_text or clean_term in full_text or ct in asset_terms:
                score += 0.40
                matched_terms.append(ct)

        # 2. Correspondance sur les domaines communs
        for cd in ctrl.domain:
            for ad in asset_domains:
                if cd == ad or cd in ad or ad in cd:
                    score += 0.20
                    matched_domains.append(cd)

        # 3. Mots-clés spécifiques par contrôle
        kw_map: dict[str, list[str]] = {
            "SNC-REQ-01": ["extraterritorial", "souverain", "cloud act", "on-premise", "trust boundary", "local inference"],
            "SNC-REQ-02": ["bastion", "management cluster", "mtls", "segregation", "administration network"],
            "SNC-REQ-03": ["hsm", "envelope encryption", "kms", "key management", "root of trust"],
            "SNC-REQ-04": ["container", "hardened", "hypervisor", "rootless", "network policy", "kubernetes"],
            "SNC-REQ-05": ["audit log", "siem", "soc", "immutable", "telemetry", "observability", "tamper"],
            "SNC-REQ-06": ["disaster recovery", "bcp", "drp", "pra", "pca", "multi-site", "fallback", "failover"],
            "ISO-27001-A5-15": ["supplier", "vendor", "sbom", "supply chain", "third-party"],
            "ISO-27001-A8-01": ["endpoint", "fleet", "remote wipe", "device", "terminal"],
            "ISO-27001-A8-08": ["vulnerability", "scanner", "patch", "shadow validation", "devsecops"],
            "ISO-27001-A8-09": ["gitops", "source of truth", "drift", "configuration management", "declarative"],
            "ISO-27001-A8-24": ["cryptography", "ciphers", "key lifecycle", "encryption"],
            "ISO-27001-A8-28": ["log", "logging", "tamper-resistant", "retention", "non-repudiation"],
        }

        if cid in kw_map:
            for kw in kw_map[cid]:
                if kw in full_text:
                    score += 0.15
                    matched_keywords.append(kw)

        if score >= threshold:
            results.append(
                MatchResult(
                    control_id=cid,
                    framework=ctrl.framework,
                    control_title=ctrl.title,
                    confidence_score=min(round(score, 2), 1.0),
                    matched_terms=matched_terms,
                    matched_domains=list(set(matched_domains)),
                    matched_keywords=matched_keywords,
                )
            )

    results.sort(key=lambda r: r.confidence_score, reverse=True)
    return results


def reconcile_kb_assets(
    kb_dir: Path | str = "data/kb",
    dry_run: bool = False,
) -> dict[str, Any]:
    """Applique la réconciliation sémantique sur l'ensemble des fichiers Markdown du Knowledge Hub."""
    base = Path(kb_dir)
    controls = load_all_controls(base / "controls")
    
    updated_files: list[dict[str, Any]] = []
    
    target_dirs = [base / "decisions", base / "patterns", base / "principles"]

    for tdir in target_dirs:
        if not tdir.exists():
            continue

        for file_path in sorted(tdir.glob("*.md")):
            if file_path.name.startswith("_") or file_path.name.lower() in ("readme.md", "index.md"):
                continue

            content = file_path.read_text(encoding="utf-8")
            fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
            if not fm_match:
                continue

            fm = yaml.safe_load(fm_match.group(1)) or {}
            body = fm_match.group(2)
            aid = fm.get("id") or file_path.stem

            existing_controls = fm.get("implements_controls", [])
            if isinstance(existing_controls, str):
                existing_controls = [existing_controls]
            current_set = set(existing_controls)

            # Combinaison alignement explicite + détection sémantique
            candidates = set(EXPLICIT_KB_ALIGNMENTS.get(aid, []))

            # Matching sémantique additionnel
            detected = match_text_to_controls(
                title=fm.get("title", ""),
                text=body,
                domain=fm.get("domain", []),
                terms=fm.get("terms", []),
                controls=controls,
                threshold=0.45,
            )
            for d in detected:
                candidates.add(d.control_id)

            new_set = current_set.union(candidates)

            # Filtrer pour s'assurer que les contrôles existent bien dans le catalogue
            valid_new_set = {c for c in new_set if c in controls}

            if valid_new_set != current_set:
                sorted_ctrls = sorted(list(valid_new_set))
                fm["implements_controls"] = sorted_ctrls

                new_fm_str = yaml.dump(fm, sort_keys=False, allow_unicode=True).strip()
                new_content = f"---\n{new_fm_str}\n---\n{body}"

                if not dry_run:
                    file_path.write_text(new_content, encoding="utf-8")

                updated_files.append({
                    "asset_id": aid,
                    "file": str(file_path),
                    "added_controls": sorted(list(valid_new_set - current_set)),
                    "total_controls": len(sorted_ctrls),
                })

    return {
        "status": "ok",
        "dry_run": dry_run,
        "updated_assets_count": len(updated_files),
        "updated_assets": updated_files,
    }


def audit_compliance_gaps(
    kb_dir: Path | str = "data/kb",
    framework: str | None = None,
) -> dict[str, Any]:
    """Audite l'exhaustivité de la couverture réglementaire et retourne les manques (Top-Down Gap Detection)."""
    base = Path(kb_dir)
    controls = load_all_controls(base / "controls")

    # Recensement des implémentations actuelles dans la KB
    implementing_map: dict[str, list[str]] = {cid: [] for cid in controls}

    target_dirs = [base / "decisions", base / "patterns", base / "principles"]
    for tdir in target_dirs:
        if not tdir.exists():
            continue
        for file_path in tdir.glob("*.md"):
            if file_path.name.startswith("_") or file_path.name.lower() in ("readme.md", "index.md"):
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
                fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
                if not fm_match:
                    continue
                fm = yaml.safe_load(fm_match.group(1)) or {}
                aid = fm.get("id") or file_path.stem
                impls = fm.get("implements_controls", [])
                if isinstance(impls, str):
                    impls = [impls]
                for c in impls:
                    if c in implementing_map:
                        implementing_map[c].append(aid)
            except Exception:
                continue

    # Filtrage éventuel par framework
    fw_report: dict[str, Any] = {}
    for cid, ctrl in controls.items():
        if framework and ctrl.framework.lower() != framework.lower():
            continue

        fw = ctrl.framework
        if fw not in fw_report:
            fw_report[fw] = {
                "total": 0,
                "covered": 0,
                "uncovered": 0,
                "controls": [],
                "uncovered_controls": [],
            }

        impls = sorted(list(set(implementing_map[cid])))
        is_covered = len(impls) > 0

        fw_report[fw]["total"] += 1
        if is_covered:
            fw_report[fw]["covered"] += 1
        else:
            fw_report[fw]["uncovered"] += 1
            fw_report[fw]["uncovered_controls"].append({
                "id": cid,
                "title": ctrl.title,
                "severity": ctrl.severity,
                "terms": ctrl.terms,
            })

        fw_report[fw]["controls"].append({
            "id": cid,
            "title": ctrl.title,
            "severity": ctrl.severity,
            "covered": is_covered,
            "implemented_by": impls,
        })

    total_all = sum(r["total"] for r in fw_report.values())
    covered_all = sum(r["covered"] for r in fw_report.values())
    global_pct = round((covered_all / total_all) * 100, 1) if total_all > 0 else 0.0

    return {
        "global_total": total_all,
        "global_covered": covered_all,
        "global_coverage_percentage": global_pct,
        "frameworks": fw_report,
    }
