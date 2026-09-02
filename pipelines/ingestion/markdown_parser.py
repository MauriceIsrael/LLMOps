"""Parser pour extraire le frontmatter YAML et les sections structurées de documents Markdown/YAML d'architecture."""

import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml


class MarkdownDocParser:
    """Parser de document d'architecture (Markdown & YAML) avec validation stricte de l'identifiant."""

    FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
    GLOSSARY_TERM_PATTERN = re.compile(
        r"^\*\*(.*?)\*\*\s*[\u2014\-]\s*(.*?)(?=\n\n|\n\*\*|\Z)", re.DOTALL | re.MULTILINE
    )

    def parse_file(self, file_path: Path | str) -> dict[str, Any] | None:
        """Lit et parse un fichier Markdown ou YAML d'architecture. Renvoie None si le fichier n'est pas un actif valide."""
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return None

        # Ignorer les fichiers système / schémas / prose sans identifiant d'actif
        if path.name.startswith("_") or path.name in ("README.md", "CONTRIBUTING.md", "GOVERNANCE.md", "deltas.md"):
            return None

        content = path.read_text(encoding="utf-8")

        if path.suffix in (".yaml", ".yml"):
            return self.parse_yaml_content(content, source_path=str(path))

        return self.parse_content(content, source_path=str(path))

    def parse_yaml_content(self, content: str, source_path: str = "") -> dict[str, Any] | None:
        """Parse un document purement YAML (.yaml / .yml)."""
        try:
            doc = yaml.safe_load(content)
        except Exception:
            return None

        if not isinstance(doc, dict):
            return None

        doc_id = doc.get("id")
        if not doc_id:
            return None

        last_reviewed = doc.get("last_reviewed", "")
        if isinstance(last_reviewed, date):
            last_reviewed = last_reviewed.isoformat()

        phase = doc.get("phase", [])
        if isinstance(phase, str):
            phase = [phase]

        domain = doc.get("domain", [])
        if isinstance(domain, str):
            domain = [domain]

        return {
            "id": str(doc_id),
            "title": str(doc.get("title", doc_id)),
            "type": str(doc.get("type", "yaml-asset")),
            "status": str(doc.get("status", "active")),
            "confidence": str(doc.get("confidence", "unverified")),
            "phase": phase,
            "domain": domain,
            "owner": str(doc.get("owner", "unknown")),
            "last_reviewed": str(last_reviewed),
            "frontmatter": doc,
            "sections": {"body": yaml.dump(doc, allow_unicode=True)},
            "raw_body": content.strip(),
            "source_path": source_path,
        }

    def parse_content(self, content: str, source_path: str = "") -> dict[str, Any] | None:
        """Parse le contenu texte d'un document Markdown."""
        frontmatter: dict[str, Any] = {}
        body = content

        match = self.FRONTMATTER_PATTERN.match(content)
        if match:
            yaml_text = match.group(1)
            try:
                frontmatter = yaml.safe_load(yaml_text) or {}
            except Exception:
                return None
            body = content[match.end():]

        # Règle d'or : Seuls les fichiers avec un 'id' explicite en frontmatter sont des actifs valides
        doc_id = frontmatter.get("id")
        if not doc_id:
            return None

        title = frontmatter.get("title")
        if not title:
            h1_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
            if h1_match:
                title = h1_match.group(1).strip()
            else:
                title = Path(source_path).stem if source_path else str(doc_id)

        last_reviewed = frontmatter.get("last_reviewed", "")
        if isinstance(last_reviewed, date):
            last_reviewed = last_reviewed.isoformat()

        phase = frontmatter.get("phase", [])
        if isinstance(phase, str):
            phase = [phase]

        domain = frontmatter.get("domain", [])
        if isinstance(domain, str):
            domain = [domain]

        sections: dict[str, str] = {}

        # Traitement spécial pour le fichier Glossaire
        if doc_id == "TPL-glossary" or "glossary" in source_path:
            matches = self.GLOSSARY_TERM_PATTERN.findall(body)
            for term, def_text in matches:
                clean_term = term.strip()
                clean_def = def_text.replace("\n", " ").strip()
                if clean_term:
                    sections[clean_term] = clean_def
        else:
            # Extraction des sections par niveau H2
            current_section = "Introduction"
            current_text: list[str] = []
            for line in body.splitlines():
                if line.startswith("## "):
                    if current_text:
                        sections[current_section] = "\n".join(current_text).strip()
                    current_section = line[3:].strip()
                    current_text = []
                else:
                    current_text.append(line)

            if current_text:
                sections[current_section] = "\n".join(current_text).strip()

        return {
            "id": str(doc_id),
            "title": str(title),
            "type": str(frontmatter.get("type", "document")),
            "status": str(frontmatter.get("status", "active")),
            "confidence": str(frontmatter.get("confidence", "unverified")),
            "phase": phase,
            "domain": domain,
            "owner": str(frontmatter.get("owner", "unknown")),
            "last_reviewed": str(last_reviewed),
            "framework": str(frontmatter.get("framework", "")),
            "version": str(frontmatter.get("version", "1.0.0")),
            "jurisdiction": str(frontmatter.get("jurisdiction", "")),
            "severity": str(frontmatter.get("severity", "mandatory")),
            "target_entities": frontmatter.get("target_entities", []),
            "frontmatter": frontmatter,
            "sections": sections,
            "raw_body": body.strip(),
            "source_path": source_path,
        }
