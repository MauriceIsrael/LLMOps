"""Tests unitaires pour le parser de document Markdown et frontmatter YAML."""

from pipelines.ingestion.markdown_parser import MarkdownDocParser


def test_markdown_parser_with_frontmatter() -> None:
    content = (
        "---\n"
        "id: ADR-001\n"
        "title: Choice of GraphDB\n"
        "status: active\n"
        "type: decision\n"
        "confidence: verified\n"
        "---\n\n"
        "# Choice of GraphDB\n\n"
        "## Context\n"
        "We need an embedded graph database.\n\n"
        "## Decision\n"
        "We choose Kùzu DB.\n"
    )
    parser = MarkdownDocParser()
    result = parser.parse_content(content)

    assert result["id"] == "ADR-001"
    assert result["title"] == "Choice of GraphDB"
    assert result["status"] == "active"
    assert result["type"] == "decision"
    assert "Context" in result["sections"]
    assert "We choose Kùzu DB." in result["sections"]["Decision"]
