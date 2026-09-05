#!/usr/bin/env python3
"""RFP / CCTP Skill & Competency Extractor (Dream Team Staffing Matrix).

Analyzes external client tenders, RFPs (Request For Proposals), CCTP and architectural
specifications (Word DOCX, PDF, Markdown), projects requirements onto the Knowledge Hub
skills catalogue, detects regulatory targets, and derives the target staffing profile
(Dream Team Matrix) required to win and deliver the project.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipelines.ingestion.markdown_parser import MarkdownDocParser
from scripts.ingest_solution_doc import DocumentExtractor

console = Console()


def load_skills_catalog(skills_dir: Path | str = "data/kb/skills") -> list[dict[str, Any]]:
    """Loads all skills definitions and frontmatter metadata from data/kb/skills/."""
    skills_path = Path(skills_dir)
    if not skills_path.exists():
        return []

    parser = MarkdownDocParser()
    catalog = []
    for f in sorted(skills_path.glob("*.md")):
        doc = parser.parse_file(str(f))
        if not doc:
            continue
        meta = doc.get("frontmatter", {})
        catalog.append({
            "id": doc.get("id", f.stem),
            "title": doc.get("title", f.stem),
            "domain": meta.get("domain", "general"),
            "criticality": meta.get("criticality", "medium"),
            "keywords": [k.lower() for k in meta.get("keywords", [])],
            "description": doc.get("raw_body", "")[:400].strip(),
            "full_content": doc.get("raw_body", ""),
        })
    return catalog


def analyze_document_skills(
    doc_text: str, skills_catalog: list[dict[str, Any]]
) -> dict[str, Any]:
    """Analyzes text occurrences and derives required skills and staffing intensity."""
    lower_text = doc_text.lower()
    
    skill_hits = defaultdict(list)
    skill_scores = defaultdict(int)

    for skill in skills_catalog:
        s_id = skill["id"]
        # Match on skill ID or Title parts
        title_tokens = [t for t in re.split(r"[^\w]+", skill["title"].lower()) if len(t) > 3]
        
        # Match keywords
        for kw in skill["keywords"]:
            count = len(re.findall(rf"\b{re.escape(kw)}\b", lower_text))
            if count > 0:
                skill_hits[s_id].append((kw, count))
                skill_scores[s_id] += count * 2

        for t in title_tokens:
            count = len(re.findall(rf"\b{re.escape(t)}\b", lower_text))
            if count > 0 and (t, count) not in skill_hits[s_id]:
                skill_hits[s_id].append((t, count))
                skill_scores[s_id] += count

    # Detect Regulatory Frameworks
    regs_detected = []
    if re.search(r"\b(nis\s*2|directive\s*nis)\b", lower_text):
        regs_detected.append("NIS2")
    if re.search(r"\b(secnumcloud|anssi)\b", lower_text):
        regs_detected.append("SecNumCloud")
    if re.search(r"\b(3gpp|mcx|mcptt|rel-?\s*1[78])\b", lower_text):
        regs_detected.append("3GPP")
    if re.search(r"\b(iso\s*27001|iso/iec\s*27001)\b", lower_text):
        regs_detected.append("ISO27001")

    # Filter and rank required skills
    ranked_skills = []
    for skill in skills_catalog:
        s_id = skill["id"]
        score = skill_scores.get(s_id, 0)
        hits = skill_hits.get(s_id, [])
        if score > 0:
            if score >= 15:
                intensity = "Haute (Pilier Majeur)"
                fte_rec = "1.0 FTE"
                level_rec = "Expert"
            elif score >= 5:
                intensity = "Moyenne (Composant Clé)"
                fte_rec = "0.5 FTE"
                level_rec = "Senior"
            else:
                intensity = "Ponctuelle (Support)"
                fte_rec = "0.2 FTE"
                level_rec = "Intermediate"

            ranked_skills.append({
                "id": s_id,
                "title": skill["title"],
                "domain": skill["domain"],
                "criticality": skill["criticality"],
                "score": score,
                "intensity": intensity,
                "recommended_fte": fte_rec,
                "recommended_level": level_rec,
                "key_occurrences": [f"{k} ({c})" for k, c in hits[:4]],
            })

    ranked_skills.sort(key=lambda x: x["score"], reverse=True)

    # Derive Dream Team Roles
    dream_team = []
    # Role 1: Security & Cryptography Architect
    sec_skills = [s for s in ranked_skills if s["id"] in ("SKL-CRYPTO-HSM", "SKL-SEC-ZEROTRUST")]
    if sec_skills:
        dream_team.append({
            "role": "Lead Architecte Sécurité & Cryptographie",
            "skills": [s["id"] for s in sec_skills],
            "min_level": "Expert",
            "fte": "1.0 FTE",
            "mission": "Architecture Zero-Trust, gestion KMS/HSM qualifiés ANSSI et homologation de sécurité (NIS2 / SecNumCloud).",
        })

    # Role 2: Telco & 5G Core Specialist
    telco_skills = [s for s in ranked_skills if s["id"] in ("SKL-TELCO-CORE", "SKL-MOB-FLEET")]
    if telco_skills:
        dream_team.append({
            "role": "Architecte Cœur 5G & Services MCX",
            "skills": [s["id"] for s in telco_skills],
            "min_level": "Senior / Expert",
            "fte": "1.0 FTE",
            "mission": "Conception de l'architecture SBA, signalisation voix critique SIP/RTP et enrôlement flotte EMM/MDM.",
        })

    # Role 3: Cloud Platform & Automation Lead
    cloud_skills = [s for s in ranked_skills if s["id"] in ("SKL-KUBE-TELCO", "SKL-AUTO-GITOPS")]
    if cloud_skills:
        dream_team.append({
            "role": "Lead Ingénieur Cloud Télécom & GitOps",
            "skills": [s["id"] for s in cloud_skills],
            "min_level": "Senior",
            "fte": "1.0 FTE",
            "mission": "Déploiement et durcissement clusters Kubernetes/Rancher, chaînes CI/CD NetDevOps et réconciliation GitOps.",
        })

    # Role 4: Network & Continuity Expert
    net_skills = [s for s in ranked_skills if s["id"] in ("SKL-NET-UNDERLAY", "SKL-RESIL-DR", "SKL-OBS-SOC")]
    if net_skills:
        dream_team.append({
            "role": "Expert Réseau IP Transport, Résilience & SOC",
            "skills": [s["id"] for s in net_skills],
            "min_level": "Senior",
            "fte": "0.8 FTE",
            "mission": "Ingénierie BGP-EVPN, résilience multi-sites PCA/PRA et transmission des puits de logs au SOC.",
        })

    return {
        "ranked_skills": ranked_skills,
        "regulatory_targets": regs_detected,
        "dream_team": dream_team,
        "total_skills_detected": len(ranked_skills),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyseur d'appel d'offres (RFP/CCTP) et déducteur de compétences cibles")
    parser.add_argument("file_path", help="Chemin vers le document RFP/CCTP (.docx, .pdf, .md)")
    parser.add_argument("--output", "-o", help="Chemin optionnel pour exporter le rapport (JSON ou Markdown)")
    args = parser.parse_args()

    doc_path = Path(args.file_path)
    if not doc_path.exists():
        console.print(f"[bold red]❌ Fichier introuvable : {doc_path}[/bold red]")
        sys.exit(1)

    console.print(Panel(
        f"[bold cyan]📑 Analyse d'Appel d'Offres & Détection de Compétences[/bold cyan]\n"
        f"Fichier : [bold]{doc_path.name}[/bold] ({doc_path.stat().st_size // 1024} Ko)",
        border_style="cyan"
    ))

    # Extraction du contenu
    try:
        sections = DocumentExtractor.extract(doc_path)
    except Exception as e:
        console.print(f"[bold red]❌ Erreur lors de l'extraction : {e}[/bold red]")
        sys.exit(1)

    full_text = "\n".join([" ".join(s.content) for s in sections])
    console.print(f"✨ [green]Document extrait avec succès :[/green] {len(sections)} sections, {len(full_text.split())} mots analysés.\n")

    # Chargement catalogue et analyse
    skills_catalog = load_skills_catalog()
    results = analyze_document_skills(full_text, skills_catalog)

    # Déstructuration sémantique RFP & Matrice de conformité triangulaire
    from pipelines.rfp_shredder import RFPShredder
    shredder = RFPShredder(kb_dir="data/kb")
    requirements = shredder.shred_text(full_text, engagement=doc_path.stem)
    compliance_res = shredder.build_compliance_matrix(requirements)
    results["compliance_matrix"] = compliance_res

    # Affichage des référentiels détectés
    regs = results["regulatory_targets"]
    regs_str = ", ".join(f"[bold green]{r}[/bold green]" for r in regs) if regs else "[dim]Aucun référentiel formel mentionné[/dim]"
    console.print(f"🏛️ [bold]Référentiels Réglementaires Détectés :[/bold] {regs_str}")
    console.print(f"📋 [bold]Scorecard de Conformité Standard :[/bold] [bold green]{compliance_res['coverage_rate']} %[/bold green] ({compliance_res['covered']}/{compliance_res['total_requirements']} exigences couvertes, {compliance_res['gaps']} gaps)\n")

    # Table des compétences
    table_skills = Table(title="🎯 Compétences Techniques Requises par le Document")
    table_skills.add_column("Compétence", style="cyan")
    table_skills.add_column("Domaine", style="dim")
    table_skills.add_column("Intensité / Criticité", style="bold")
    table_skills.add_column("Niveau Attendu", style="magenta")
    table_skills.add_column("Occurrences Clés", style="green")

    for s in results["ranked_skills"]:
        crit_color = "red" if s["criticality"] == "high" else "yellow"
        crit_str = f"[{crit_color}]{s['intensity']}[/{crit_color}]"
        table_skills.add_row(
            f"{s['id']} — {s['title']}",
            s["domain"],
            crit_str,
            s["recommended_level"],
            ", ".join(s["key_occurrences"]),
        )
    console.print(table_skills)

    # Table Dream Team Staffing Profile
    table_team = Table(title="\n👥 Profil d'Équipe Cible (Dream Team Staffing Matrix)")
    table_team.add_column("Rôle Recommandé", style="bold cyan")
    table_team.add_column("Compétences Couvertes", style="magenta")
    table_team.add_column("Séniorité Min.", style="yellow")
    table_team.add_column("Charge Estimée", style="green")
    table_team.add_column("Missions & Responsabilités Clés", style="italic")

    total_fte = 0.0
    for member in results["dream_team"]:
        fte_val = float(member["fte"].split()[0])
        total_fte += fte_val
        table_team.add_row(
            member["role"],
            ", ".join(member["skills"]),
            member["min_level"],
            member["fte"],
            member["mission"],
        )
    console.print(table_team)

    console.print(f"\n📈 [bold]Dimensionnement Global Estimé :[/bold] [bold green]{total_fte:.1f} ETP[/bold green] (Équivalents Temps Plein)")
    console.print(f"💡 [bold]Conseil Avant-Vente :[/bold] Pour sécuriser la réponse à l'appel d'offres, mobiliser un profil expert sur [bold cyan]{results['ranked_skills'][0]['id']}[/bold cyan] dès la phase de bid.")

    if args.output:
        out_path = Path(args.output)
        if out_path.suffix.lower() == ".json":
            out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        else:
            # Markdown export
            md_lines = [
                f"# Analyse de Staffing RFP : {doc_path.name}",
                f"\n**Référentiels réglementaires identifiés :** {', '.join(regs)}",
                "\n## Compétences Requises",
                "| ID | Intitulé | Intensité | Niveau Requis |",
                "|---|---|---|---|",
            ]
            for s in results["ranked_skills"]:
                md_lines.append(f"| {s['id']} | {s['title']} | {s['intensity']} | {s['recommended_level']} |")
            md_lines.append("\n## Équipe Cible Recommandée (Dream Team Matrix)")
            md_lines.append("| Rôle | Compétences | Niveau | Charge |")
            md_lines.append("|---|---|---|---|")
            for m in results["dream_team"]:
                md_lines.append(f"| {m['role']} | {', '.join(m['skills'])} | {m['min_level']} | {m['fte']} |")
            out_path.write_text("\n".join(md_lines), encoding="utf-8")
        console.print(f"\n📁 [bold green]Rapport exporté vers :[/bold green] {out_path}")


if __name__ == "__main__":
    main()
