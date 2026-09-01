"""Extracteur d'ontologie et de graphe d'architecture utilisant LlamaIndex PropertyGraph."""

from typing import Any

from llama_index.core.graph_stores.types import EntityNode, Relation


class ArchitectureGraphExtractor:
    """Extracteur d'entités d'architecture et de relations pour Kùzu DB via LlamaIndex."""

    def __init__(self, model_name: str = "gpt-4o-mini") -> None:
        self.model_name = model_name

    def extract_nodes_and_relations(
        self, parsed_doc: dict[str, Any]
    ) -> tuple[list[EntityNode], list[Relation]]:
        """Sépare le document parsed en entités (Nodes) et relations typées (Edges)."""
        nodes: list[EntityNode] = []
        relations: list[Relation] = []

        doc_id = parsed_doc["id"]
        doc_title = parsed_doc["title"]
        doc_type = parsed_doc["type"]
        status = parsed_doc["status"]
        confidence = parsed_doc["confidence"]
        last_reviewed = parsed_doc.get("last_reviewed", "")

        phase_val = parsed_doc.get("phase", [])
        phase_str = ",".join(phase_val) if isinstance(phase_val, list) else str(phase_val)

        domain_val = parsed_doc.get("domain", [])
        domain_str = ",".join(domain_val) if isinstance(domain_val, list) else str(domain_val)

        import hashlib

        raw_markdown = parsed_doc.get("raw_body", "")
        raw_sha256 = hashlib.sha256(raw_markdown.encode("utf-8")).hexdigest()
        version_val = str(parsed_doc.get("frontmatter", {}).get("version", "1.0.0"))
        external_ref_val = f"KH:{doc_id}@v{version_val}"

        # Nœud Principal de l'Asset
        main_node = EntityNode(
            name=doc_id,
            label=doc_type.upper(),
            properties={
                "id": doc_id,
                "title": doc_title,
                "type": doc_type,
                "status": status,
                "confidence": confidence,
                "phase": phase_str,
                "domain": domain_str,
                "last_reviewed": last_reviewed,
                "owner": parsed_doc.get("owner", ""),
                "source_path": parsed_doc.get("source_path", ""),
                "version": version_val,
                "markdown_content": raw_markdown,
                "sha256": raw_sha256,
                "external_ref": external_ref_val,
            },
        )
        nodes.append(main_node)

        # Extraction des termes du Glossaire si le type est 'glossary' ou 'template' (glossary.md)
        if doc_id == "TPL-glossary" or doc_type == "glossary" or "glossary" in parsed_doc.get("source_path", ""):
            sections = parsed_doc.get("sections", {})
            for term, def_text in sections.items():
                if term == "Introduction":
                    continue
                term_node = EntityNode(
                    name=term,
                    label="GLOSSARY_TERM",
                    properties={"term": term, "definition": def_text},
                )
                nodes.append(term_node)
                relations.append(
                    Relation(
                        source_id=doc_id,
                        target_id=term,
                        label="DEFINES",
                    )
                )

        # Extraction des relations inter-documents depuis le frontmatter ou les sections
        frontmatter = parsed_doc.get("frontmatter", {})
        supersedes = frontmatter.get("supersedes")
        if supersedes:
            if isinstance(supersedes, str):
                supersedes = [supersedes]
            for target_id in supersedes:
                relations.append(
                    Relation(
                        source_id=doc_id,
                        target_id=target_id,
                        label="SUPERSEDES",
                    )
                )

        requires = frontmatter.get("requires")
        if requires:
            if isinstance(requires, str):
                requires = [requires]
            for target_id in requires:
                relations.append(
                    Relation(
                        source_id=doc_id,
                        target_id=target_id,
                        label="REQUIRES",
                    )
                )

        return nodes, relations
