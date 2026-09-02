#!/usr/bin/env python3
"""Solution Document Ingestion & Architecture Gap Extractor (DOCX, PDF, Markdown).

Extracts structural sections and content from external architecture documents
(NetDevOps solution design, HLD, technical briefs in Word/PDF/Markdown),
maps them onto an architectural blueprint, initializes the project draft,
and can trigger immediate gap detection (elicit scan).
"""

import argparse
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@dataclass
class ExtractedSection:
    """Représente une section extraite du document source."""

    title: str
    level: int = 1
    content: list[str] = field(default_factory=list)
    section_id: str | None = None


class DocumentExtractor:
    """Extracteur universel multi-formats avec zéro dépendance obligatoire pour DOCX."""

    @classmethod
    def extract(cls, file_path: Path) -> list[ExtractedSection]:
        suffix = file_path.suffix.lower()
        if suffix == ".docx":
            return cls._extract_docx(file_path)
        elif suffix == ".pdf":
            return cls._extract_pdf(file_path)
        elif suffix in (".md", ".markdown", ".txt"):
            return cls._extract_markdown(file_path)
        else:
            raise ValueError(f"Format non supporté: {suffix}. Utilisez .docx, .pdf ou .md.")

    @classmethod
    def _extract_docx(cls, file_path: Path) -> list[ExtractedSection]:
        """Extraction native DOCX par zipfile + XML (zéro dépendance pip requise)."""
        # Tentative avec python-docx si disponible
        try:
            import docx

            doc = docx.Document(file_path)
            sections: list[ExtractedSection] = []
            current_sec = ExtractedSection(title="Document Header", level=1)

            for p in doc.paragraphs:
                text = p.text.strip()
                if not text:
                    continue
                style = p.style.name.lower() if p.style else ""
                if "heading 1" in style or "titre 1" in style:
                    sections.append(current_sec)
                    current_sec = ExtractedSection(title=text, level=1)
                elif "heading 2" in style or "titre 2" in style:
                    sections.append(current_sec)
                    current_sec = ExtractedSection(title=text, level=2)
                elif "heading 3" in style or "titre 3" in style:
                    sections.append(current_sec)
                    current_sec = ExtractedSection(title=text, level=3)
                else:
                    current_sec.content.append(text)
            sections.append(current_sec)
            return [s for s in sections if s.content or s.title != "Document Header"]
        except ImportError:
            pass

        # Fallback universel : parser XML interne de Word
        sections: list[ExtractedSection] = []
        current_sec = ExtractedSection(title="Document Header", level=1)

        with zipfile.ZipFile(file_path, "r") as z:
            xml_bytes = z.read("word/document.xml")
            root = ET.fromstring(xml_bytes)

            namespaces = {
                "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
            }

            for p in root.findall(".//w:p", namespaces):
                # Récupère le style
                p_style = p.find(".//w:pStyle", namespaces)
                style_val = (
                    p_style.attrib.get(
                        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val", ""
                    ).lower()
                    if p_style is not None
                    else ""
                )

                # Récupère le texte de tous les <w:t>
                text_elems = p.findall(".//w:t", namespaces)
                text = "".join([t.text for t in text_elems if t.text]).strip()

                if not text:
                    continue

                is_heading = False
                heading_level = 1
                if "heading" in style_val or "titre" in style_val or "heading1" in style_val:
                    is_heading = True
                    if "2" in style_val:
                        heading_level = 2
                    elif "3" in style_val:
                        heading_level = 3
                elif re.match(r"^\d+(\.\d+)*\s+[A-ZÀ-Ÿ]", text):
                    # Détection heuristique de titre numéroté (ex: "1.2 Architecture NetDevOps")
                    is_heading = True
                    heading_level = text.count(".") + 1

                if is_heading:
                    sections.append(current_sec)
                    current_sec = ExtractedSection(title=text, level=heading_level)
                else:
                    current_sec.content.append(text)

        sections.append(current_sec)
        return [s for s in sections if s.content or s.title != "Document Header"]

    @classmethod
    def _extract_pdf(cls, file_path: Path) -> list[ExtractedSection]:
        """Extraction PDF via pypdf ou pdfplumber."""
        try:
            import pypdf

            reader = pypdf.PdfReader(file_path)
            full_text = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    full_text.append(text)
            raw_text = "\n".join(full_text)
            return cls._parse_raw_text(raw_text)
        except ImportError:
            raise RuntimeError(
                "Pour lire des fichiers PDF, veuillez installer 'pypdf' : poetry run pip install pypdf"
            )

    @classmethod
    def _extract_markdown(cls, file_path: Path) -> list[ExtractedSection]:
        """Extraction depuis un document Markdown structuré."""
        raw_text = file_path.read_text(encoding="utf-8")
        return cls._parse_raw_text(raw_text)

    @classmethod
    def _parse_raw_text(cls, text: str) -> list[ExtractedSection]:
        """Parse un flux de texte brut ou markdown en sections."""
        lines = text.split("\n")
        sections: list[ExtractedSection] = []
        current_sec = ExtractedSection(title="Introduction", level=1)

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Titre Markdown (# Heading)
            md_match = re.match(r"^(#{1,4})\s+(.+)$", stripped)
            # Titre Numéroté (1.1 Title)
            num_match = re.match(r"^(\d+(\.\d+)*)\.?\s+([A-ZÀ-Ÿ].+)$", stripped)

            if md_match:
                sections.append(current_sec)
                current_sec = ExtractedSection(
                    title=md_match.group(2).strip(),
                    level=len(md_match.group(1)),
                )
            elif num_match and len(stripped) < 100:
                sections.append(current_sec)
                current_sec = ExtractedSection(
                    title=stripped,
                    level=num_match.group(1).count(".") + 1,
                    section_id=num_match.group(1),
                )
            else:
                current_sec.content.append(stripped)

        sections.append(current_sec)
        return [s for s in sections if s.content or s.title != "Introduction"]


class BlueprintMapper:
    """Associe intelligemment les sections extraites aux exigences du Blueprint d'architecture."""

    def __init__(self, blueprint_path: Path | str) -> None:
        self.blueprint_path = Path(blueprint_path)
        with open(self.blueprint_path, "r", encoding="utf-8") as f:
            self.blueprint_data = yaml.safe_load(f)
        self.bp_sections = self.blueprint_data.get("sections", [])

    def map_sections(self, extracted: list[ExtractedSection]) -> list[dict[str, Any]]:
        """Mappe les sections extraites avec le catalogue de sections du Blueprint."""
        mapped = []

        for ext in extracted:
            matched_bp = self._find_best_match(ext.title)
            mapped.append({
                "extracted_title": ext.title,
                "matched_section_id": matched_bp.get("id") if matched_bp else None,
                "matched_bp_title": matched_bp.get("title") if matched_bp else None,
                "subject": (
                    matched_bp.get("requires", [{}])[0].get("subject")
                    if matched_bp and matched_bp.get("requires")
                    else (matched_bp.get("subject") if matched_bp else None)
                ),
                "compliance_controls": matched_bp.get("compliance_controls", []) if matched_bp else [],
                "content_preview": (
                    ext.content[0][:150] + "..." if ext.content else "Section vide"
                ),
                "paragraph_count": len(ext.content),
                "content_lines": ext.content,
            })
        return mapped

    def _find_best_match(self, title: str) -> dict[str, Any] | None:
        t_clean = re.sub(r"^\d+(\.\d+)*\s*", "", title).strip().lower()

        # 1. Correspondance exacte ou forte inclusion
        for s in self.bp_sections:
            bp_title = s.get("title", "").lower()
            if t_clean == bp_title or (len(t_clean) > 5 and t_clean in bp_title):
                return s

        # 2. Table de synonymes conceptuels NetDevOps & Télécom
        synonyms_rules = [
            # Scope & Drivers
            (["purpose", "scope", "boundaries", "structuring assumptions"], "1.2"),
            (["executive summary", "value proposition"], "1.1"),
            (["business drivers", "operational directives"], "1.3"),
            (["principles", "architecture principles"], "1.4"),
            (["functional requirements", "use case", "scenarios"], "2.2"),
            (["non-functional requirements", "sla", "kpi"], "2.3"),
            # Service & MCX
            (["sim", "esim", "lifecycle"], "3.5"),
            (["floor control", "arbitration"], "3.2"),
            (["group management", "affiliation"], "3.3"),
            (["mcx services", "mission-critical services"], "3.1"),
            # Infra & Platform
            (["rancher", "container platform", "hosting domains", "virtualization", "compute"], "4.4"),
            (["transport", "ip transport", "underlay", "flow matrix", "physical view"], "4.3"),
            (["mobile core", "ericsson dedicated"], "4.2"),
            (["high availability", "resilience", "break-glass", "failure-domain"], "5.2"),
            (["disaster recovery", "backup"], "5.3"),
            # Security & Compliance
            (["security posture", "security and compliance", "zero-trust", "principles & zero-trust"], "7.1"),
            (["iam", "identity", "authentication", "access management"], "7.2"),
            (["cryptography", "encryption", "chiffrement", "kms"], "7.3"),
            (["threat protection", "hardening", "regulatory compliance"], "7.4"),
            (["soc", "csirt", "incident response"], "7.5"),
            # Observability & Dark NOC
            (["observability architecture", "dark noc", "operational vision"], "8.1"),
            (["service plane", "infrastructure plane", "observation planes"], "8.1.1"),
            (["ai assistance", "build profile", "agentic ai in build"], "8.2"),
            (["run profile", "autonomous agent capabilities in run"], "8.3"),
            (["guardrails", "execution guardrails", "single source of truth", "sot", "operational patterns"], "8.4"),
            (["auditing", "traceability", "non-repudiation"], "8.5"),
            # Delivery & OSS
            (["delivery plan", "phasing"], "10.1"),
            (["servicenow", "service management", "inventory", "orders"], "9.1"),
            (["ericsson enm", "enm integration"], "9.2"),
        ]

        for keywords, target_id in synonyms_rules:
            if any(kw in t_clean for kw in keywords):
                for s in self.bp_sections:
                    if str(s.get("id")) == str(target_id):
                        return s

        # 3. Calcul de score par chevauchement de tokens
        t_tokens = set(re.findall(r"\w{4,}", t_clean))
        if not t_tokens:
            return None

        best_section = None
        max_score = 0
        for s in self.bp_sections:
            bp_tokens = set(re.findall(r"\w{4,}", s.get("title", "").lower()))
            overlap = len(t_tokens & bp_tokens)
            if overlap > max_score:
                max_score = overlap
                best_section = s

        if max_score >= 2:
            return best_section

        return None


def export_engagement_draft(
    engagement: str,
    mapped_sections: list[dict[str, Any]],
    output_dir: Path = Path("projects"),
) -> Path:
    """Génère le document draft d'engagement d'architecture (draft.md)."""
    proj_dir = output_dir / engagement
    proj_dir.mkdir(parents=True, exist_ok=True)
    draft_file = proj_dir / "draft.md"

    lines = [
        f"# Dossier d'Architecture Solution — {engagement.upper()}",
        "",
        "> Document d'architecture préliminaire généré automatiquement par ingestion de solution.",
        "",
        "---",
        "",
    ]

    for sec in mapped_sections:
        bp_id = sec.get("matched_section_id")
        bp_label = f" (Section Blueprint : {bp_id} — {sec.get('matched_bp_title')})" if bp_id else " (Section Hors-Blueprint)"
        lines.append(f"## {sec['extracted_title']}{bp_label}")
        if sec.get("compliance_controls"):
            lines.append(f"> **Contrôles réglementaires ciblés :** {', '.join(sec['compliance_controls'])}")
            lines.append("")

        if sec["content_lines"]:
            for p in sec["content_lines"]:
                lines.append(p)
                lines.append("")
        else:
            lines.append("*Aucun contenu rédigé pour cette section.*")
            lines.append("")

    draft_file.write_text("\n".join(lines), encoding="utf-8")
    return draft_file


def main():
    parser = argparse.ArgumentParser(
        description="Ingestion et projection de documents d'architecture (Word, PDF, Markdown) vers le Knowledge Hub."
    )
    parser.add_argument("input_file", type=Path, help="Chemin vers le document source (.docx, .pdf, .md)")
    parser.add_argument(
        "--engagement",
        "-e",
        type=str,
        default="solution-draft",
        help="Identifiant d'engagement cible (ex: netdevops-2026)",
    )
    parser.add_argument(
        "--blueprint",
        "-b",
        type=Path,
        default=Path("data/kb/blueprints/BLU-hla-mcx.yaml"),
        help="Chemin vers le Blueprint d'architecture YAML",
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Déclencher immédiatement la détection des manques d'architecture (elicit scan)",
    )

    args = parser.parse_args()

    if not args.input_file.exists():
        console.print(f"[bold red]❌ Fichier introuvable : {args.input_file}[/bold red]")
        sys.exit(1)

    console.print(
        Panel.fit(
            f"[bold blue]🚀 Ingestion du document : {args.input_file.name}[/bold blue]\n"
            f"• Format : {args.input_file.suffix}\n"
            f"• Engagement cible : [bold cyan]{args.engagement}[/bold cyan]\n"
            f"• Blueprint référent : [bold yellow]{args.blueprint.name}[/bold yellow]",
            title="Knowledge Hub — Ingestion Solution",
        )
    )

    # 1. Extraction
    with console.status("[bold green]Extraction des sections du document..."):
        sections = DocumentExtractor.extract(args.input_file)
    console.print(f"✅ [bold green]{len(sections)} sections extraites du document.[/bold green]")

    # 2. Mapping Blueprint
    mapper = BlueprintMapper(args.blueprint)
    mapped = mapper.map_sections(sections)

    table = Table(title=f"Projection Blueprint — {args.input_file.name}")
    table.add_column("Section Extraite", style="cyan")
    table.add_column("Section Blueprint", style="magenta")
    table.add_column("Sujet Clé", style="yellow")
    table.add_column("Contrôles Sécurité", style="red")
    table.add_column("Paragraphes", justify="right", style="green")

    covered_count = 0
    for m in mapped:
        bp_label = f"{m['matched_section_id']} {m['matched_bp_title']}" if m["matched_section_id"] else "[grey]Non mappé[/grey]"
        if m["matched_section_id"]:
            covered_count += 1
        ctrls = ", ".join(m["compliance_controls"]) if m["compliance_controls"] else "-"
        table.add_row(
            m["extracted_title"][:40],
            bp_label[:40],
            m["subject"] or "-",
            ctrls,
            str(m["paragraph_count"]),
        )

    console.print(table)
    console.print(
        f"📊 Taux d'alignement avec le Blueprint : [bold cyan]{covered_count}/{len(mapped)} sections couvertes[/bold cyan]"
    )

    # 3. Export du Draft d'architecture
    draft_path = export_engagement_draft(args.engagement, mapped)
    console.print(f"📝 Draft d'architecture généré : [bold green]{draft_path}[/bold green]")

    # 4. Déclenchement facultatif du Scan de Manques (elicit scan)
    if args.scan:
        console.print(f"\n[bold yellow]🔎 Lancement automatique de l'analyse des manques d'architecture...[/bold yellow]")
        from tools.elicitation.flows.scan import build_scan_graph

        scan_graph = build_scan_graph()
        scan_state = {
            "engagement": args.engagement,
            "blueprint_id": args.blueprint.stem,
            "max_questions": 8,
            "strategy": "breadth",
        }
        res = scan_graph.invoke(scan_state)
        questions = res.get("questions", [])
        counts = res.get("counts_summary", {})

        console.print(
            f"[bold green]✅ Analyse terminée ! Lacunes détectées : "
            f"Nouveaux: {counts.get('new', 0)} · Ouverts: {counts.get('open', 0)} · Retenus: {counts.get('held_premature', 0)}[/bold green]"
        )

        if questions:
            q_table = Table(title=f"Manques Critiques Détectés & Questions Émises — {args.engagement}")
            q_table.add_column("ID", style="cyan")
            q_table.add_column("Section", style="magenta")
            q_table.add_column("Rôle Cible", style="yellow")
            q_table.add_column("Question à Résoudre", style="white")

            for q in questions[:8]:
                q_table.add_row(
                    q.get("id", ""),
                    q.get("section", ""),
                    q.get("routed_to", ""),
                    q.get("text", "")[:80] + "...",
                )
            console.print(q_table)


if __name__ == "__main__":
    main()
