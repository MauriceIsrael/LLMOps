# LLMOps — Queryable Architecture Knowledge Graph (MCP)

> Queryable architecture knowledge graph in MCP: every statement carries confidence and maturity so your document generators know what they can assert.

[Version en français (README.fr.md)](README.fr.md)

---

## Quickstart & MCP Configuration

Connect any MCP client (Claude Desktop, Cursor, Antigravity, VS Code, or custom clients) in 30 seconds.

### 1. Remote Connection (GCP Cloud Run Serverless SSE)

Add the following to your MCP client configuration (e.g. `claude_desktop_config.json` or Cursor settings):

```json
{
  "mcpServers": {
    "llmops-remote": {
      "url": "https://llmops-mcp-server-344571265365.europe-west1.run.app/sse",
      "headers": {
        "Authorization": "Bearer demo-public-2026-08"
      }
    }
  }
}
```

### 2. Local Connection (STDIO via Poetry)

```json
{
  "mcpServers": {
    "llmops-knowledge": {
      "command": "poetry",
      "args": ["run", "mcp-server-knowledge"],
      "cwd": "/path/to/LLMOps"
    },
    "llmops-engagement": {
      "command": "poetry",
      "args": ["run", "mcp-server-engagement"],
      "cwd": "/path/to/LLMOps"
    }
  }
}
```

### 3. One-Command Onboarding & Health Check

Run the local demonstration suite in one command without API keys:

```bash
make demo
make demo-check
```

**Expected Node Counts after Demo Check (`make demo-check`):**
- **Knowledge Plane (`data/knowledge.kuzu`)**: `Asset`: ~46 nodes, `GlossaryTerm`: ~10 nodes.
- **Engagement Plane (`nordwave-mcx-2027`)**: `Subject`: 8 nodes, `Statement`: 9 nodes, `Conflict`: 2 nodes.

---

## Key Differentiators

1. **100% Deterministic & Auditable Core (0 Server LLM Costs)**  
   No non-deterministic LLM calls on the server. The knowledge server is backed by a typed graph database (LadybugDB / Kùzu DB) enforcing strict schemas. Model intelligence remains client-side.
2. **Provisional Statements & Confidence Tracking**  
   Every architectural statement explicitly tracks its confidence (`verified`, `designed`, `stated-by-client`, `assumed`) and subject maturity level (`L0_named` to `L4_specified`). Generated documents know if they are provisional and state why (`is_provisional: true`, `unripe_subjects`, `open_conflicts`).
3. **Dual-Plane Physical Isolation (ADR-0015)**  
   Reusable enterprise patterns (`data/knowledge.kuzu`) are physically separated from per-project dynamic state (`data/engagements/<id>.kuzu`). Cross-plane queries are prohibited; references resolve strictly via asset identifiers.

---

## Development & Testing

```bash
# Run unit and contract test suite
make test

# Run linter
make lint

# Run interactive CLI elicitation scan
poetry run elicit scan --engagement nordwave-mcx-2027 --max-questions 3
```

---

## Documentation Links

- **[Third-Party Integration Guide](docs/THIRD-PARTY-INTEGRATION-GUIDE.md)**: Full guide to writing custom renderers (DOCX, PPTX, Web UI) without running the server.
- **[External Interface Specification (INTERFACE.md)](docs/INTERFACE.md)**: Technical MCP contract, response envelopes, JSON Schemas, and transport protocols.
- **[Schema Specification (SCHEMA.md)](docs/SCHEMA.md)**: Automatically generated Kùzu DB graph schema.
- **[Software Architecture (ADR-0014 / ADR-0015)](docs/architecture.md)**: Internal dual-plane architecture specification.
- **[User Manual](docs/user_manual.md)**: CLI elicitation workflow and level gates.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
