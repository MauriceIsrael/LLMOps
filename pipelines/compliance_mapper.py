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
from datetime import UTC
from functools import lru_cache
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
    legal_text: str = ""
    from_source: bool = False
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
    "ADR-0005": [
        "3GPP-TS33501-SBI", "3GPP-TS33501-SEPP", "3GPP-TS29522-NEF", "3GPP-TS33926-SCAS",
        "NIS2-ART21-2D", "ISO-27001-A5-15", "SNC-REQ-03"
    ],
    "ADR-0006": ["ISO-27001-A8-09", "SNC-REQ-04"],
    "ADR-0007": [
        "SNC-REQ-02", "SNC-REQ-06", "NIS2-ART21-2C", "3GPP-TS33179-ISOLATED",
        "CER-ART13-RESIL", "TELCO-RESIL-TIER4", "TELCO-RESIL-GNSS-HOLDOVER", "ISO-22301-BCP"
    ],
    "ADR-0008": ["SNC-REQ-05", "ISO-27001-A8-28", "FCAPS-OAM-PROT", "RGPD-REQ-BREACH-02"],
    "ADR-0011": ["SNC-REQ-01", "NIS2-ART21-2H"],
    "ADR-0012": ["ISO-27001-A8-08", "CRA-REQ-VULN-01"],
    "ADR-0013": [
        "ISO-27001-A8-01", "3GPP-TS33179-AFFILIATION", "GSMA-SGP22-RSP", "GSMA-SGP32-IOT",
        "GSMA-CEIR-PEI", "PPDR-DEVICE-RUGGED", "PPDR-DEVICE-ATEX", "PPDR-VEHICLE-CEM",
        "PPDR-RADIO-B68", "CRA-REQ-SECBYDES-02"
    ],
    # Patterns
    "PAT-001": ["NIS2-ART21-2B", "ISO-27005-RISK"],
    "PAT-002": ["NIS2-ART21-2E", "ISO-27001-A8-08", "CRA-REQ-VULN-01"],
    "PAT-003": ["NIS2-ART21-2C", "SNC-REQ-06", "TELCO-RESIL-TIER4", "CER-ART13-RESIL", "ISO-22301-BCP"],
    "PAT-004": [
        "NIS2-ART21-2C", "NIS2-ART21-2J", "3GPP-TS33179-ISOLATED", "3GPP-TS33179-KMS",
        "SNC-REQ-02", "SNC-REQ-03", "ISO-27001-A8-01", "ISO-27001-A8-24",
        "3GPP-TS37579-ICS", "TELCO-RESIL-PTP-01", "TELCO-RESIL-GNSS-HOLDOVER"
    ],
    "PAT-005": ["NIS2-ART21-2F", "SNC-REQ-05", "ISO-27001-A8-28", "FCAPS-OAM-PROT", "RGPD-REQ-BREACH-02"],
    "PAT-006": [
        "NIS2-ART21-2D", "3GPP-TS33501-SBI", "3GPP-TS33501-SEPP", "SNC-REQ-01",
        "ISO-27001-A5-15", "3GPP-TS29522-NEF", "3GPP-TS33926-SCAS"
    ],
    "PAT-007": ["NIS2-ART21-2H"],
    # Principles
    "P-001": ["NIS2-ART21-2A", "ISO-27001-A8-09", "SNC-REQ-04", "ISO-14001-DECOM"],
    "P-002": ["NIS2-ART21-2B"],
    "P-003": ["NIS2-ART21-2G"],
    "P-005": ["NIS2-ART21-2E", "ISO-27001-A8-08", "CRA-REQ-VULN-01"],
    "P-007": ["NIS2-ART21-2D", "ISO-27001-A5-15", "3GPP-TS33501-SEPP", "GSMA-SAS-EAL4"],
    "P-009": [
        "NIS2-ART21-2C", "SNC-REQ-02", "SNC-REQ-06", "TELCO-RESIL-TIER4",
        "TELCO-RESIL-PTP-01", "TELCO-RESIL-MTBF"
    ],
    "P-010": ["NIS2-ART21-2I", "ISO-27001-A8-09", "ITIL-SERV-MGMT"],
    "P-011": ["SNC-REQ-05", "ISO-27001-A8-28", "FCAPS-OAM-PROT"],
    "P-015": ["NIS2-ART21-2H", "SNC-REQ-01", "ISO-27001-A8-24", "RGPD-REQ-PRIVACY-01"],
}


_LEGAL_SECTION = re.compile(r"## Legal Requirement\n(.*?)(?:\n## |\Z)", re.DOTALL)
_WORD = re.compile(r"[a-zà-ÿ0-9]+")
# Function words of the two working languages: a phrase made only of these carries no information.
_STOPWORDS = frozenset(
    "the a an and or of to in on for by with from that this these those as at is are be been shall may must not "
    "any all such their its it which who whom where when than then under over into within without upon per "
    "le la les un une des du de et ou en dans sur pour par avec sans que qui dont où au aux ce cette ces son "
    "sa ses leur leurs est sont être doit doivent peut peuvent ne pas plus".split()
)


def _legal_text(title: str, body: str) -> str:
    """Title and legal text of a control (the ``Legal Requirement`` section of an ingested control)."""
    section = _LEGAL_SECTION.search(body)
    return f"{title}\n{section.group(1) if section else ''}".lower()


def _phrases(text: str) -> set[str]:
    """Pairs of consecutive content words, and numbers with their unit (``24 hours``): the distinctive
    phrases two texts about the same obligation share, whatever the order of the surrounding words."""
    words = [w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS and len(w) > 1]
    return {f"{a} {b}" for a, b in zip(words, words[1:], strict=False)}


def legal_text_matches(requirement_text: str, control: RegulatoryControl) -> list[str]:
    """Distinctive phrases shared by a requirement text and the legal text of a control."""
    if not control.legal_text:
        return []
    return sorted(_phrases(requirement_text) & _phrases(control.legal_text))


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
                legal_text=_legal_text(str(fm.get("title") or ""), body),
                from_source=bool(fm.get("source_sha256")),
                file_path=file_path,
            )
        except Exception:
            continue

    return controls


@lru_cache(maxsize=4)
def load_control_keywords(path: str | None = None) -> dict[str, list[str]]:
    """Mots-clés additionnels par contrôle : données de la base de connaissance, jamais dans le code."""
    file = Path(path) if path else Path(__file__).resolve().parent.parent / "data" / "kb" / "taxonomy" / "control_keywords.yaml"
    if not file.is_file():
        return {}
    data = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
    return {str(k): [str(x) for x in v or []] for k, v in data.items()}


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

        # 3. Mots-clés spécifiques par contrôle (data/kb/taxonomy/control_keywords.yaml)
        kw_map = load_control_keywords()

        if cid in kw_map:
            for kw in kw_map[cid]:
                if kw in full_text:
                    score += 0.15
                    matched_keywords.append(kw)

        # 4. Controls without ``terms``, or ingested from a source (`source_sha256`: `kb ingest-framework`, even once
        #    terms were added to them), are also matched on their legal text: each distinctive phrase shared with
        #    the text counts, up to a cap. Hand-curated controls that never went through an ingestion keep
        #    matching on their own terms only.
        if not ctrl.terms or ctrl.from_source:
            shared = legal_text_matches(f"{title}\n{text}", ctrl)
            if shared:
                score += min(0.15 * len(shared), 0.60)
                matched_keywords.extend(f"legal:{s}" for s in shared[:6])

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


def get_applicable_frameworks(engagement: str = "default") -> list[str]:
    """Retourne la liste des codes de référentiels applicables pour un engagement."""
    import json
    meta_path = Path("data/engagements") / f"{engagement}.meta.json"
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            fws = data.get("applicable_frameworks")
            if isinstance(fws, list) and fws:
                return fws
        except Exception:
            pass
    controls = load_all_controls("data/kb/controls")
    return sorted(list({c.framework for c in controls.values()}))


def set_applicable_frameworks(engagement: str, frameworks: list[str]) -> dict[str, Any]:
    """Définit les référentiels applicables pour un engagement donné."""
    import json
    meta_path = Path("data/engagements") / f"{engagement}.meta.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if meta_path.exists():
        try:
            existing = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    existing["applicable_frameworks"] = frameworks
    meta_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "status": "ok",
        "engagement": engagement,
        "applicable_frameworks": frameworks,
    }


def to_conformity_snapshot(
    engagement: str = "default",
    framework: str = "ALL",
    controls_dir: Path | str = "data/kb/controls",
    source_system: str = "knowledge-hub",
) -> dict[str, Any]:
    """Génère un ConformitySnapshot conforme au contrat ExternalSnapshotEnvelope<ConformityData> pour document-engine."""
    from datetime import datetime

    from pipelines import canonical

    controls = load_all_controls(controls_dir)
    target_fw = framework.upper().replace("-", "").replace("_", "")

    applicable_fws = [fw.upper().replace("-", "").replace("_", "") for fw in get_applicable_frameworks(engagement)]

    requirements: list[dict[str, Any]] = []

    for cid, ctrl in controls.items():
        ctrl_fw = ctrl.framework.upper().replace("-", "").replace("_", "")
        if target_fw != "ALL":
            if target_fw not in ctrl_fw and ctrl_fw not in target_fw:
                continue
        else:
            if not any(afw in ctrl_fw or ctrl_fw in afw for afw in applicable_fws):
                continue

        covered_by: list[str] = []
        for asset_id, mapped_ctrls in EXPLICIT_KB_ALIGNMENTS.items():
            if cid in mapped_ctrls:
                covered_by.append(asset_id)

        domain = "COMPLIANCE"
        if "security" in ctrl.domain or "securite" in ctrl.domain:
            domain = "SECURITY"
        elif "resilience" in ctrl.domain:
            domain = "RESILIENCE"
        elif "network" in ctrl.domain:
            domain = "NETWORK"

        evidence = [
            {
                "mode": "architecture-model",
                "type": "graph-item",
                "reference": ref,
                "source": "architecture-studio",
            }
            for ref in sorted(covered_by)
        ]

        req: dict[str, Any] = {
            "id": ctrl.id,
            "title": ctrl.title_fr or ctrl.title,
            "domain": domain,
            "verificationModes": ["architecture-model"],
            "status": "verified" if covered_by else "allocated",
            "evidence": evidence,
            "appliesTo": {
                "programRef": engagement.upper(),
                "lotRefs": [],
                "pbsRefs": [],
            },
        }
        requirements.append(req)

    # Tri déterministe des exigences par id
    requirements.sort(key=lambda r: r["id"])

    data = {
        "requirements": requirements,
    }

    checksum = canonical.sha256(data)  # canonical-json v1 (K1)
    now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    prefix = "kh" if source_system == "knowledge-hub" else ("tuleap-kh" if source_system == "tuleap" else f"{source_system}-kh")

    return {
        "snapshotId": f"{prefix}-{engagement}-{framework.lower()}-{int(datetime.now().timestamp())}",
        "sourceSystem": source_system,
        "schemaVersion": "2.0",
        "createdAt": now_iso,
        "checksum": checksum,
        "data": data,
    }



def compute_framework_coverage(frameworks: list[str], kb_dir: str | Path = "data/kb") -> dict[str, Any]:
    """Coverage of each framework by the knowledge base (plan L3 §6.2).

    ``{framework: {status: covered|partial|missing, version, expected, present, validated,
    missing_ids, declared_by, ...}}`` — see ``pipelines/frameworks/coverage.py``.
    """
    from pipelines.frameworks.coverage import compute_framework_coverage as _compute

    return _compute(frameworks, kb_dir)
