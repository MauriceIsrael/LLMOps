#!/usr/bin/env python3
"""Générateur de Zero-Draft HLD (High-Level Design) & Élicitation Ciblée sur les Gaps.

Compile automatiquement un document d'architecture de haut niveau (HLD) structuré à
80% à partir des actifs du Knowledge Hub (Patterns, ADRs, Principes) et des exigences RFP
ingérées, tout en ciblant les questions d'élicitation sur les seuls manques (gaps).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pipelines.ingestion.markdown_parser import MarkdownDocParser
from tools.elicitation.repository import ElicitationRepository

# Routage des questions d'élicitation selon la catégorie
CATEGORY_ROLE_ROUTING: dict[str, str] = {
    "security": "security-architect",
    "sovereignty": "compliance-lead",
    "infrastructure": "infrastructure-expert",
    "cloud-platform": "cloud-architect",
    "network": "network-architect",
    "observability": "sre-lead",
    "resilience": "resilience-engineer",
    "telco-core": "telco-specialist",
    "ai-assistance": "ai-architect",
    "general": "lead-architect",
}


class ZeroDraftAssembler:
    """Assembleur déterministe de Zero-Draft HLD avec focalisation sur les gaps."""

    def __init__(
        self,
        db_path: str | Path = "data/engagements/nordwave-mcx-2027.lbug",
        kb_dir: Path | str = "data/kb",
    ) -> None:
        self.db_path = str(db_path)
        self.kb_dir = Path(kb_dir)
        self.repo = ElicitationRepository(db_path=self.db_path)
        self.parser = MarkdownDocParser()

    def load_kb_asset_details(self, asset_ids: list[str]) -> list[dict[str, Any]]:
        """Charge les détails textuels complets des actifs KB référencés."""
        details = []
        id_set = set(asset_ids)

        for folder in ["patterns", "decisions", "principles"]:
            p = self.kb_dir / folder
            if not p.exists():
                continue
            for f in sorted(p.glob("*.md")):
                doc = self.parser.parse_file(str(f))
                if doc and doc.get("id") in id_set:
                    details.append(doc)
        return details

    def generate_zero_draft_hld(
        self,
        engagement: str,
        project_title: str = "Système d'Architecture Télécom & Plateforme Sécurisée",
        client_name: str = "Client RFP",
    ) -> dict[str, Any]:
        """Génère le document HLD complet au format Markdown et la synthèse de conformité."""
        requirements = self.repo.get_requirements(engagement)

        # Statistiques de conformité
        total_reqs = len(requirements)
        covered_reqs = [r for r in requirements if r.get("status") == "covered"]
        partial_reqs = [r for r in requirements if r.get("status") == "partially_covered"]
        gap_reqs = [r for r in requirements if r.get("status") == "gap"]

        coverage_rate = round((len(covered_reqs) / total_reqs * 100), 1) if total_reqs > 0 else 0.0

        # Récupération de tous les assets KB référencés
        referenced_assets: set[str] = set()
        for r in requirements:
            m = r.get("matched_assets") or "[]"
            import json
            try:
                asset_list = json.loads(m) if isinstance(m, str) else m
                referenced_assets.update(asset_list)
            except Exception:
                pass

        kb_assets = self.load_kb_asset_details(list(referenced_assets))
        patterns = [a for a in kb_assets if a.get("id", "").startswith("PAT-")]
        adrs = [a for a in kb_assets if a.get("id", "").startswith("ADR-")]
        principles = [a for a in kb_assets if a.get("id", "").startswith("P-")]

        # Construction du document Markdown
        doc_lines: list[str] = []

        # 1. En-tête
        doc_lines.append(f"# High-Level Design (HLD) — {project_title}")
        doc_lines.append("")
        doc_lines.append(f"> **Engagement :** `{engagement}`  ")
        doc_lines.append(f"> **Destinataire :** {client_name}  ")
        doc_lines.append(f"> **Date de génération :** {datetime.now().strftime('%Y-%m-%d')}  ")
        doc_lines.append(f"> **Statut du document :** `{'FINALISÉ' if not gap_reqs else 'ZERO-DRAFT (PROVISOIRE - ÉLICITATION REQUISE)'}`  ")
        doc_lines.append(f"> **Couverture Standard KB :** `{coverage_rate}%` ({len(covered_reqs)}/{total_reqs} exigences satisfaites d'emblée)  ")
        doc_lines.append("")
        doc_lines.append("---")
        doc_lines.append("")

        # 2. Synthèse Exécutive
        doc_lines.append("## 1. Synthèse Exécutive & Scorecard de Conformité")
        doc_lines.append("")
        doc_lines.append(
            f"Ce document High-Level Design (HLD) constitue la réponse architecturale technique au cahier des charges "
            f"fourni par **{client_name}**. Il capitalise sur le socle neuro-symbolique standardisé du Knowledge Hub, "
            f"garantissant la réutilisation immédiate des patterns éprouvés en production et le respect strict des réglementations en vigueur."
        )
        doc_lines.append("")
        doc_lines.append("### Scorecard de Couverture Réglementaire & Technique")
        doc_lines.append("")
        doc_lines.append("| Indicateur | Valeur | Statut |")
        doc_lines.append("|---|---|---|")
        doc_lines.append(f"| **Exigences Totales Analysées** | {total_reqs} | 📋 Inventoriées |")
        doc_lines.append(f"| **Conformité Standard Immédiate** | {len(covered_reqs)} ({coverage_rate}%) | {'✅ Excellente' if coverage_rate >= 70 else '⚠️ À consolider'} |")
        doc_lines.append(f"| **Conformité Partielle** | {len(partial_reqs)} | 🔍 Sous réserve de cadrage |")
        doc_lines.append(f"| **Écarts Résiduels (Gaps)** | {len(gap_reqs)} | {'✅ Aucun gap' if not gap_reqs else '🚨 Élicitation active'} |")
        doc_lines.append("")

        # 3. Principes Directeurs
        doc_lines.append("## 2. Principes Directeurs d'Architecture")
        doc_lines.append("")
        doc_lines.append("L'architecture globale de la solution est gouvernée par les principes souverains et immuables suivants :")
        doc_lines.append("")
        if principles:
            for p in sorted(principles, key=lambda x: x.get("id", "")):
                p_id = p.get("id")
                p_title = p.get("title")
                doc_lines.append(f"### `{p_id}` — {p_title}")
                body = p.get("raw_body", "").strip()
                # Extraire un extrait pertinent
                summary = body[:300].replace("\n", " ").strip()
                doc_lines.append(f"{summary}...")
                doc_lines.append("")
        else:
            doc_lines.append("*Les principes d'architecture fondamentaux du socle (P-001, P-009, P-015) sont appliqués par défaut.*")
            doc_lines.append("")

        # 4. Architecture de Référence & Patterns
        doc_lines.append("## 3. Architecture de Référence & Motifs Clés (Patterns)")
        doc_lines.append("")
        doc_lines.append("Pour couvrir les exigences fonctionnelles et de sécurité, les motifs d'architecture suivants sont intégrés :")
        doc_lines.append("")
        if patterns:
            for pat in sorted(patterns, key=lambda x: x.get("id", "")):
                pat_id = pat.get("id")
                pat_title = pat.get("title")
                fm = pat.get("frontmatter", {})
                ctrls = fm.get("implements_controls", [])
                ctrl_txt = f" *(Conforme à {', '.join(ctrls)})*" if ctrls else ""
                doc_lines.append(f"### `{pat_id}` — {pat_title}{ctrl_txt}")
                body = pat.get("raw_body", "").strip()
                doc_lines.append(f"{body[:400]}...")
                doc_lines.append("")
        else:
            doc_lines.append("*Motifs standard appliqués selon la matrice de conformité.*")
            doc_lines.append("")

        # 5. Décisions d'Architecture Structurantes (ADRs)
        doc_lines.append("## 4. Décisions d'Architecture Structurantes (ADRs)")
        doc_lines.append("")
        doc_lines.append("Les choix techniques majeurs s'appuient sur les ADRs validées de la plateforme :")
        doc_lines.append("")
        if adrs:
            for adr in sorted(adrs, key=lambda x: x.get("id", "")):
                a_id = adr.get("id")
                a_title = adr.get("title")
                doc_lines.append(f"- **`{a_id}`** : {a_title}")
            doc_lines.append("")
        else:
            doc_lines.append("- **ADR-0001** : Git as the source of truth for network and platform configuration")
            doc_lines.append("- **ADR-0007** : Dedicated management cluster with its own storage and southbound paths")
            doc_lines.append("- **ADR-0011** : Inference served locally on general-purpose processors")
            doc_lines.append("")

        # 6. Matrice Triangulaire Complète
        doc_lines.append("## 5. Matrice Triangulaire de Conformité RFP")
        doc_lines.append("")
        doc_lines.append("| ID Exigence | Section RFP | Énoncé / Exigence | Statut | Actifs KB Mobilisés | Preuves Normatives | Rationale |")
        doc_lines.append("|---|---|---|---|---|---|---|")
        for req in requirements:
            r_id = req.get("id")
            r_sec = req.get("section", "-")
            r_txt = req.get("text", "").replace("|", "\\|")[:80] + ("..." if len(req.get("text", "")) > 80 else "")
            r_stat = "✅ Conforme" if req.get("status") == "covered" else ("🔍 Partiel" if req.get("status") == "partially_covered" else "🚨 Écart (Gap)")
            
            import json
            m_a = req.get("matched_assets") or "[]"
            m_c = req.get("matched_controls") or "[]"
            try:
                assets_l = json.loads(m_a) if isinstance(m_a, str) else m_a
                ctrls_l = json.loads(m_c) if isinstance(m_c, str) else m_c
            except Exception:
                assets_l = []
                ctrls_l = []
            
            assets_str = ", ".join(assets_l[:2]) or "-"
            ctrls_str = ", ".join(ctrls_l[:2]) or "-"
            rat = req.get("rationale", "-").replace("|", "\\|")
            doc_lines.append(f"| `{r_id}` | {r_sec} | {r_txt} | {r_stat} | {assets_str} | {ctrls_str} | {rat} |")
        doc_lines.append("")

        # 7. Écarts & Élicitation Ciblée
        doc_lines.append("## 6. Écarts Identifiés & Plan d'Élicitation Ciblée (Gaps)")
        doc_lines.append("")
        if gap_reqs or partial_reqs:
            doc_lines.append("> [!WARNING]")
            doc_lines.append("> **Attention : Clauses spécifiques du client non couvertes par le standard standardisé.**")
            doc_lines.append(f"> Le système a détecté {len(gap_reqs)} écarts stricts et {len(partial_reqs)} points d'attention partielle. ")
            doc_lines.append("> Des questions d'élicitation ciblées ont été générées dans la boîte aux lettres des architectes.")
            doc_lines.append("")

            for g in gap_reqs:
                g_id = g.get("id")
                g_txt = g.get("text")
                g_cat = g.get("category", "general")
                role = CATEGORY_ROLE_ROUTING.get(g_cat, "lead-architect")
                doc_lines.append(f"### Point d'arbitrage : `{g_id}` ({g.get('section', 'Cadrage')})")
                doc_lines.append(f"- **Texte de l'exigence :** *\"{g_txt}\"*")
                doc_lines.append(f"- **Criticité :** `{g.get('criticality', 'mandatory')}` | **Catégorie :** `{g_cat}`")
                doc_lines.append(f"- **Expert sollicité pour décision :** `{role}`")
                doc_lines.append("- **Action requise :** Valider ou compléter l'énoncé d'architecture pour lever le statut provisoire.")
                doc_lines.append("")
        else:
            doc_lines.append("✅ **Aucun écart résiduel.** Toutes les exigences du cahier des charges sont intégralement satisfaites par le socle.")
            doc_lines.append("")

        full_markdown = "\n".join(doc_lines)

        return {
            "engagement": engagement,
            "project_title": project_title,
            "client_name": client_name,
            "status": "final" if not gap_reqs else "provisional",
            "coverage_rate": coverage_rate,
            "total_requirements": total_reqs,
            "covered_count": len(covered_reqs),
            "partial_count": len(partial_reqs),
            "gap_count": len(gap_reqs),
            "document_markdown": full_markdown,
        }

    def trigger_targeted_elicitation(self, engagement: str) -> dict[str, Any]:
        """Génère automatiquement les questions d'élicitation pour combler les exigences non couvertes."""
        requirements = self.repo.get_requirements(engagement)
        uncovered = [r for r in requirements if r.get("status") in ("gap", "partially_covered")]

        created_questions: list[dict[str, Any]] = []

        for req in uncovered:
            r_id = req.get("id", "REQ-000")
            q_id = f"Q-RFP-{r_id.replace('REQ-RFP-', '')}"
            category = req.get("category", "general")
            role = CATEGORY_ROLE_ROUTING.get(category, "lead-architect")
            crit = req.get("criticality", "mandatory")

            q_data = {
                "id": q_id,
                "engagement": engagement,
                "gap_type": "rfp_uncovered_requirement",
                "section": req.get("section", "4.0"),
                "question": f"Comment l'architecture doit-elle satisfaire l'exigence client : '{req.get('text')}' ?",
                "why_it_matters": f"Exigence {crit} du RFP non couverte par les motifs standards du Knowledge Hub.",
                "expected_shape": "Un énoncé technique (has_property ou implements) précisant la technologie, le composant ou la décision retenue.",
                "routed_to": role,
                "status": "open",
                "level": "L2_framed",
            }

            self.repo.save_question(q_data)
            created_questions.append(q_data)

        return {
            "engagement": engagement,
            "total_gaps_targeted": len(uncovered),
            "questions_created": len(created_questions),
            "questions": created_questions,
        }
