#!/usr/bin/env python3
"""RFP Shredder & Semantic Compliance Matcher.

Déstructure les documents d'appel d'offres (RFP, CCTP, cahier des charges) en exigences
atomiques typées, les met en correspondance avec les actifs du Knowledge Hub
(Patterns, ADRs, Principes) et les contrôles réglementaires (SecNumCloud, ISO 27001,
NIS 2, 3GPP), et génère la matrice de conformité triangulaire.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pipelines.compliance_mapper import match_text_to_controls
from pipelines.ingestion.markdown_parser import MarkdownDocParser


@dataclass
class RFPRequirement:
    """Modèle d'une exigence atomique extraite d'un RFP."""

    id: str
    engagement: str
    section: str
    category: str
    text: str
    criticality: str = "mandatory"  # mandatory, desirable, optional
    status: str = "gap"  # covered, partially_covered, gap
    matched_assets: list[str] = field(default_factory=list)
    matched_controls: list[str] = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Mots-clés de catégorisation thématique
CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "security": [
        "sécurité", "chiffrement", "authentification", "tls", "mtls", "hsm", "kms", "pki",
        "bastion", "zero-trust", "secret", "rbac", "certificat", "vulnérabilité", "durcissement",
        "isolation", "firewall", "filtrage", "anonymisation", "audit"
    ],
    "sovereignty": [
        "souveraineté", "secnumcloud", "anssi", "extraterritorialité", "cloud de confiance",
        "qualification", "hébergement européen", "rgpd", "localisation", "ue"
    ],
    "infrastructure": [
        "infrastructure", "serveur", "bare-metal", "hyperviseur", "stockage", "san", "nvme",
        "ceph", "datacenter", "site", "cluster", "hci", "hardware", "matériel"
    ],
    "cloud-platform": [
        "kubernetes", "k8s", "conteneur", "docker", "rancher", "gitops", "argo", "flux",
        "cni", "orchestration", "ingress", "pod", "helm"
    ],
    "network": [
        "réseau", "bgp", "evpn", "underlay", "overlay", "routage", "commutateur", "vlan",
        "mpls", "bande passante", "latence", "qos", "mtu"
    ],
    "observability": [
        "observabilité", "monitoring", "métriques", "logs", "télémétrie", "prometheus",
        "grafana", "opentelemetry", "siem", "soc", "alerte", "dashboard", "supervision"
    ],
    "resilience": [
        "résilience", "pca", "pra", "bcp", "drp", "haute disponibilité", "secours",
        "tolérance aux pannes", "sauvegarde", "backup", "rto", "rpo", "redondance"
    ],
    "telco-core": [
        "3gpp", "5g", "core", "sba", "mcx", "mcptt", "mcdata", "mcvideo", "sip", "rtp",
        "sim", "e-sim", "provisioning", "radio", "ran"
    ],
    "ai-assistance": [
        "ia", "llm", "assistant", "modèle", "inférence", "agent", "rag", "prompt", "gpu"
    ],
}

# Patterns de détection de criticité
CRITICALITY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("mandatory", re.compile(r"\b(doit|doivent|obligatoire|impératif|exigé|exigence|strictement|shall|must|mandatory)\b", re.IGNORECASE)),
    ("desirable", re.compile(r"\b(devrait|souhaité|recommandé|privilégié|préconisé|should|desirable|recommended)\b", re.IGNORECASE)),
    ("optional", re.compile(r"\b(optionnel|facultatif|éventuel|atout|plus|bonus|may|optional)\b", re.IGNORECASE)),
]


class RFPShredder:
    """Extracteur et déstructurateur d'exigences d'appels d'offres."""

    def __init__(self, kb_dir: Path | str = "data/kb") -> None:
        self.kb_dir = Path(kb_dir)
        self.assets_index = self._load_kb_assets()

    def _load_kb_assets(self) -> list[dict[str, Any]]:
        """Charge et indexe les actifs de connaissances (Patterns, ADRs, Principes)."""
        parser = MarkdownDocParser()
        assets: list[dict[str, Any]] = []
        if not self.kb_dir.exists():
            return assets

        # Patterns, ADRs, Principes
        search_dirs = [
            self.kb_dir / "patterns",
            self.kb_dir / "decisions",
            self.kb_dir / "principles",
        ]

        for folder in search_dirs:
            if not folder.exists():
                continue
            for f in folder.glob("*.md"):
                doc = parser.parse_file(str(f))
                if not doc:
                    continue
                fm = doc.get("frontmatter", {})
                assets.append({
                    "id": doc.get("id", f.stem),
                    "title": doc.get("title", f.stem),
                    "type": doc.get("type", "asset"),
                    "domain": fm.get("domain", ""),
                    "implements_controls": fm.get("implements_controls", []),
                    "raw_body": doc.get("raw_body", ""),
                    "path": str(f),
                })
        return assets

    def shred_text(self, text: str, engagement: str = "default") -> list[RFPRequirement]:
        """Découpe un texte brut ou markdown de RFP en exigences atomiques."""
        lines = text.splitlines()
        current_section = "1.0 Cadrage Général"
        raw_items: list[tuple[str, str]] = []  # (section, text)

        current_item_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if current_item_lines:
                    raw_items.append((current_section, " ".join(current_item_lines)))
                    current_item_lines = []
                continue

            # Détection de titre de section
            if stripped.startswith("#"):
                if current_item_lines:
                    raw_items.append((current_section, " ".join(current_item_lines)))
                    current_item_lines = []
                current_section = stripped.lstrip("#").strip()
                continue

            # Détection d'élément de liste ou exigence numérotée
            is_bullet = re.match(r"^(\*|-|\d+[\.\)])\s+", stripped)
            is_req_tag = re.match(r"^\[?(REQ|EXIG|EXG|SEC|ARC|INF|FONC|PERF)[-_0-9A-Z]+\]?:?", stripped, re.IGNORECASE)

            if is_bullet or is_req_tag:
                if current_item_lines:
                    raw_items.append((current_section, " ".join(current_item_lines)))
                    current_item_lines = []
                # Nettoyer la puce
                clean_text = re.sub(r"^(\*|-|\d+[\.\)])\s+", "", stripped)
                current_item_lines.append(clean_text)
            else:
                if current_item_lines:
                    current_item_lines.append(stripped)
                else:
                    # Ligne isolée : si elle contient des marqueurs d'exigence, la prendre comme exigence
                    if any(p.search(stripped) for _, p in CRITICALITY_PATTERNS[:2]):
                        raw_items.append((current_section, stripped))
                    else:
                        current_item_lines.append(stripped)

        if current_item_lines:
            raw_items.append((current_section, " ".join(current_item_lines)))

        # Filtrer et normaliser en RFPRequirement
        requirements: list[RFPRequirement] = []
        req_counter = 1

        for section, item_text in raw_items:
            # Ignorer les lignes trop courtes qui ne sont pas des exigences
            if len(item_text) < 15:
                continue

            req_id = f"REQ-RFP-{req_counter:03d}"
            category = self._classify_category(item_text)
            criticality = self._determine_criticality(item_text)

            req = RFPRequirement(
                id=req_id,
                engagement=engagement,
                section=section,
                category=category,
                text=item_text,
                criticality=criticality,
            )
            # Match avec le Knowledge Hub
            self._match_with_knowledge_base(req)
            requirements.append(req)
            req_counter += 1

        return requirements

    def _classify_category(self, text: str) -> str:
        """Détermine la catégorie technique dominante de l'exigence."""
        lower = text.lower()
        scores: dict[str, int] = {}
        for cat, keywords in CATEGORY_KEYWORDS.items():
            count = sum(1 for kw in keywords if kw in lower)
            if count > 0:
                scores[cat] = count
        if scores:
            return max(scores, key=scores.get)  # type: ignore
        return "general"

    def _determine_criticality(self, text: str) -> str:
        """Détermine le niveau d'obligation de l'exigence."""
        for crit, pattern in CRITICALITY_PATTERNS:
            if pattern.search(text):
                return crit
        return "mandatory"

    def _match_with_knowledge_base(self, req: RFPRequirement) -> None:
        """Met en correspondance l'exigence avec les actifs KB et contrôles réglementaires."""
        text_lower = req.text.lower()
        matched_assets = []
        matched_controls = set()

        for asset in self.assets_index:
            score = 0
            # 1. Correspondance sur les mots du titre
            title_words = [w.lower() for w in re.split(r"[^\w]+", asset["title"]) if len(w) > 3]
            for tw in title_words:
                if tw in text_lower:
                    score += 2

            # 2. Correspondance sur le domaine
            dom_val = asset.get("domain") or []
            asset_domains = [d.strip().lower() for d in dom_val.split(",")] if isinstance(dom_val, str) else [str(d).lower() for d in dom_val]
            if any(d in req.category or req.category in d for d in asset_domains):
                score += 1

            # 3. Correspondance sur l'ID mentionné directement
            if asset["id"].lower() in text_lower:
                score += 10

            if score >= 3:
                matched_assets.append(asset["id"])
                for ctrl in asset.get("implements_controls", []):
                    matched_controls.add(ctrl)

        # Détection directe de contrôles réglementaires par conformité sémantique
        matches = match_text_to_controls(
            title=req.section,
            text=req.text,
            domain=[req.category],
            threshold=0.30,
        )
        for m in matches:
            matched_controls.add(m.control_id)

        # Rapprochement triangulaire : associer les actifs KB implémentant ces contrôles
        for ctrl_id in list(matched_controls):
            for asset in self.assets_index:
                if ctrl_id in asset.get("implements_controls", []):
                    matched_assets.append(asset["id"])

        req.matched_assets = sorted(list(set(matched_assets)))
        req.matched_controls = sorted(list(matched_controls))

        # Évaluation du statut et rationale
        if req.matched_assets:
            req.status = "covered"
            asset_str = ", ".join(req.matched_assets[:3])
            ctrl_str = f" (satisfait {', '.join(req.matched_controls[:2])})" if req.matched_controls else ""
            req.rationale = f"Couvert par les actifs standard du Knowledge Hub : {asset_str}{ctrl_str}."
        elif req.matched_controls:
            req.status = "partially_covered"
            req.rationale = f"Contrôles réglementaires identifiés ({', '.join(req.matched_controls[:3])}) sans pattern dédié affecté. Élicitation recommandée."
        else:
            req.status = "gap"
            req.rationale = "Aucun motif d'architecture ou décision standard n'a été identifié. Élicitation requise."

    def build_compliance_matrix(self, requirements: list[RFPRequirement]) -> dict[str, Any]:
        """Génère la matrice de conformité triangulaire et les statistiques."""
        total = len(requirements)
        covered = sum(1 for r in requirements if r.status == "covered")
        partial = sum(1 for r in requirements if r.status == "partially_covered")
        gaps = sum(1 for r in requirements if r.status == "gap")

        coverage_rate = round((covered / total * 100), 1) if total > 0 else 0.0

        by_cat: dict[str, dict[str, int]] = {}
        for r in requirements:
            by_cat.setdefault(r.category, {"total": 0, "covered": 0, "partially_covered": 0, "gap": 0})
            by_cat[r.category]["total"] += 1
            by_cat[r.category][r.status] += 1

        matrix_rows = [r.to_dict() for r in requirements]

        return {
            "total_requirements": total,
            "covered": covered,
            "partially_covered": partial,
            "gaps": gaps,
            "coverage_rate": coverage_rate,
            "breakdown_by_category": by_cat,
            "matrix": matrix_rows,
        }

    def persist_to_engagement(
        self,
        engagement: str,
        requirements: list[RFPRequirement],
        db_path: str | Path = "data/engagements/nordwave-mcx-2027.lbug",
    ) -> dict[str, Any]:
        """Persiste les exigences découpées dans la base d'engagement locale."""
        from tools.elicitation.repository import ElicitationRepository

        repo = ElicitationRepository(db_path=db_path)
        saved_count = 0
        for req in requirements:
            req.engagement = engagement
            repo.save_requirement(req.to_dict())
            saved_count += 1

        return {
            "engagement": engagement,
            "saved_requirements": saved_count,
            "db_path": str(db_path),
        }
