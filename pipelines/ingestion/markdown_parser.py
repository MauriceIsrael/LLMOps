"""Parser pour extraire le frontmatter YAML et les sections structurées de documents Markdown d'architecture."""

import re
from pathlib import Path
from typing import Any
import yaml


class MarkdownDocParser:
    """Parser de document Markdown d'architecture avec métadonnées YAML."""

    FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

    def parse_file(self, file_path: Path | str) -> dict[str, Any]:
        """Lit et parse un fichier Markdown d'architecture."""
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")
        return self.parse_content(content, source_path=str(path))

    def parse_content(self, content: str, source_path: str = "") -> dict[str, Any]:
        """Parse le contenu texte d'un document Markdown."""
        frontmatter: dict[str, Any] = {}
        body = content

        match = self.FRONTMATTER_PATTERN.match(content)
        if match:
            yaml_text = match.group(1)
            frontmatter = yaml.safe_load(yaml_text) or {}
            body = content[match.end():]

        # Extraire le premier titre H1 si non spécifié dans le frontmatter
        title = frontmatter.get("title")
        if not title:
            h1_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
            if h1_match:
                title = h1_match.group(1).strip()
            else:
                title = Path(source_path).stem if source_path else "Sans titre"

        # Extraire les sections par niveau H2
        sections: dict[str, str] = {}
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

        doc_id = frontmatter.get("id") or (Path(source_path).stem if source_path else "doc_id")

        return {
            "id": str(doc_id),
            "title": str(title),
            "type": frontmatter.get("type", "document"),
            "status": frontmatter.get("status", "active"),
            "confidence": frontmatter.get("confidence", "unverified"),
            "phase": frontmatter.get("phase", []),
            "domain": frontmatter.get("domain", []),
            "owner": frontmatter.get("owner", "unknown"),
            "last_reviewed": str(frontmatter.get("last_reviewed", "")),
            "frontmatter": frontmatter,
            "sections": sections,
            "raw_body": body.strip(),
            "source_path": source_path,
        }
