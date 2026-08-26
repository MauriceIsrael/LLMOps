# Contributing to LLMOps Code & Client Integrations

> **Note:** This guide covers contributing code, tools, and third-party clients to the repository. To contribute architectural principles, patterns, or decisions to the Knowledge Base itself, see [`data/kb/CONTRIBUTING.md`](data/kb/CONTRIBUTING.md).

We welcome contributions from developers building clients, integrations, renderers, or extending the FastMCP server.

---

## 🚀 Good First Client Contributions

If you are looking for an impactful project to build against LLMOps, we have framed three high-value client integrations:

### 1. PPTX / PDF Executive Presentation Renderer
- **Goal:** Build an offline generator that reads `get_render_payload.json` or `get_engagement_export` and outputs a PowerPoint slide deck for client architecture reviews.
- **Key Requirement:** Render `verified` vs `assumed` statements with distinct visual weight / color codes, and highlight `is_provisional` status.

### 2. VS Code Extension for Subject Maturity Board
- **Goal:** Create a lightweight VS Code extension that connects via SSE (`/sse`) or STDIO to display the real-time subject maturity board (`get_board`) directly in the IDE sidebar.
- **Key Requirement:** Display progress from `L0_named` to `L4_specified` and highlight stalled subjects.

### 3. Confluence / Enterprise Wiki Exporter
- **Goal:** Create a script or web service that syncs the generated High-Level Architecture document (`get_render_payload` + `get_diagram_graph`) to Atlassian Confluence pages.

---

## 🛠️ Development Setup

```bash
# Clone and install dependencies
git clone https://github.com/MauriceIsrael/LLMOps.git
cd LLMOps
make install

# Run the local demonstration suite & health check
make demo
make demo-check

# Run unit & contract tests
make test

# Run linter
make lint
```

---

## 📏 Code & PR Guidelines

1. **Deterministic Server Core**: Never add non-deterministic LLM calls on the server. Model intelligence belongs client-side.
2. **Strict Physical Isolation (ADR-0015)**: Do not write queries that attempt to join `data/knowledge.kuzu` and `data/engagements/*.kuzu` in a single Cypher execution.
3. **No MCP Write Tools**: All writes must go through human confirmation or the `poetry run elicit import` pipeline.
4. **Contract Freshness**: If modifying MCP response payloads, regenerate schemas with `poetry run python scripts/generate_schemas.py` and update fixtures with `poetry run python scripts/export_fixtures.py`.
