# 🔌 External Interface Specification & MCP Response Schemas (ADR-0014 / ADR-0015)

This document is the official technical contract specification for the **FastMCP** server interface exposed by the **LLMOps** platform. It provides the full response structure and **JSON Schemas** for all tools under `schema_version: "1.0"`.

---

## 🎯 1. Architecture Overview & The 4 Integration Surfaces

LLMOps provides **four distinct surfaces of integration** to accommodate both agentic workflows and decoupled client applications (e.g. *Architecture Studio*):

```
1. Sealed Snapshot Channel (Offline JSON File / HTTP GET /snapshot/latest)
   ↳ Zero-latency, sealed snapshot with sha256 checksum, type:slug identifiers, and applicability index.
2. FastMCP Server (SSE / STDIO via JSON-RPC 2.0)
   ↳ Interactive tool surface for LLM agents, Antigravity, Claude Desktop, and Cursor.
3. Python SDK (mcp_server.renderer_interface.RendererClient)
   ↳ Direct typed Python client for local renderers and scripts.
4. CLI Import Gateway (poetry run elicit import)
   ↳ Validated JSON payload ingestion enforcing controlled domain predicate vocabularies.
```

### 🔒 Guarantee: 100% Deterministic Core
- Zero server-side model calls in `tools/elicitation/`.
- Level gate progression (`L0_named` → `L4_specified`), contradiction detection, and conflict tracking are implemented via deterministic, parameterized Cypher and symbolic logic.
- An elicitation session is strictly replayable and auditable.

---

## 🌐 2. Transports, Endpoints & Authentication

- **Recommended Transport for Agents:** HTTP SSE (`Server-Sent Events`) at endpoint `/sse`.
- **Static / Web Application Channel:** `GET /snapshot/latest` and `GET /snapshot/{snapshot_id}` with `ETag` and `Cache-Control` headers.
- **STDIO Transport (Local Agents):** `poetry run mcp-server-knowledge` and `poetry run mcp-server-engagement`.
- **Public Production Endpoint (GCP Cloud Run):** `https://llmops-mcp-server-344571265365.europe-west1.run.app/sse`
- **HTTP Authentication (Bearer Token):**
  - FastMCP HTTP startup requires environment variable `SERVER_TOKEN` (or `LLMOPS_AUTH_TOKEN`).
  - Requests must supply the token in HTTP header: `Authorization: Bearer <SERVER_TOKEN>` (or `X-API-Key: <SERVER_TOKEN>`).
  - Constant-time verification (`secrets.compare_digest`) returns `HTTP 401 Unauthorized` if invalid or missing.
- **Connection Safety & Semantics:**
  - Read-Only connection on the underlying LadybugDB graph databases in production.
  - Any Cypher write attempt (`CREATE`, `SET`, `DELETE`) via public read tools is rejected at driver level.

---

## 📋 3. Standardized Response Envelope & Error Handling

All FastMCP tools return a **standardized JSON envelope**:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ResponseEnvelope",
  "type": "object",
  "properties": {
    "status": {
      "type": "string",
      "enum": ["ok", "not_found", "invalid_argument", "error", "unauthorized"]
    },
    "count": {
      "type": "integer",
      "minimum": 0
    },
    "data": {
      "description": "Response payload whose structure depends on the tool called."
    },
    "reason": {
      "type": "string",
      "description": "Provided when status is error, invalid_argument, or unauthorized."
    }
  },
  "required": ["status", "count", "data"]
}
```

### Behavior across Statuses:
- **Nominal Success (`status: "ok"`)**: Returns `count` (integer `>= 0`) and the data payload.
- **Not Found (`status: "not_found"`)**: Identifier not found in database. Returns `data: null`.
- **Error / Invalid Argument (`status: "error"` / `"invalid_argument"`)**: Contains explanatory string in `reason`.

---

## 📚 4. Knowledge Server Tools Catalog (18 Tools)

| Tool Name | Description | Key Parameters |
|---|---|---|
| `list_assets` | List architecture asset metadata with optional status, phase, type or domain filters | `type`, `phase`, `domain`, `status` |
| `get_asset` | Retrieve single asset with full content and metadata | `id` |
| `get_assets` | Batch retrieve multiple assets by ID list in a single call | `ids` |
| `search_assets` | Parameterized search across assets, titles, and identifiers | `query`, `filters` |
| `get_principles_for` | Fetch active architecture principles applicable to a domain or phase | `phase`, `domain` |
| `get_decision_trail` | Supersession history trail of an ADR (`SUPERSEDES` chain) | `id` |
| `get_glossary_term` | Fetch canonical definition for an architecture glossary term | `term` |
| `get_knowledge_analytics` | Knowledge base volume indicators, relations count, and lifecycle stats | *(none)* |
| `get_domain_prominence_report` | Domain gravity, cross-domain dependencies, and prominence score report | *(none)* |
| `list_frameworks` | List supported regulatory security frameworks (NIS2, 3GPP, SecNumCloud, ISO27001) | *(none)* |
| `list_controls` | List security controls with implementing principles and patterns | `framework` |
| `get_compliance_trail` | Lineage trail from regulatory control to satisfying architecture assets | `control_id` |
| `get_compliance_matrix` | Project compliance matrix and gaps for a regulatory framework | `framework`, `engagement` |
| `list_skills` | List canonical engineering skills, domains, and criticality levels | `domain` |
| `get_skills_matrix` | Staffing skills coverage matrix, gaps, and risk index for an engagement | `engagement`, `blueprint_path` |
| `suggest_knowledge_improvement` | Submit external REX, candidate pattern or feedback with instant Discord dispatch | `title`, `rationale`, `suggested_change`, `author`, `contact_email`, `source_engagement` |
| `query_graph` | Execute read-only Cypher query on knowledge graph | `cypher_query` |
| `get_graph_summary` | Graph summary node/rel counts and schema version | *(none)* |

---

## 🚀 5. Engagement Server Tools Catalog (12 Tools)

| Tool Name | Description | Key Parameters |
|---|---|---|
| `get_subject` | Subject maturity state and associated active statements count | `engagement`, `subject` |
| `get_subject_trajectory` | Maturity timeline history and questions answered for a subject | `engagement`, `subject` |
| `get_board` | Per-subject maturity board (`L0_named` to `L4_specified`) and staleness | `engagement` |
| `get_statements` | Active architectural statements with confidence and attribution | `engagement`, `subject` |
| `get_conflicts` | Open and arbitrated architecture conflicts (`contradiction`, `principle_violation`, `stale_basis`) | `engagement`, `status` |
| `get_open_questions` | Open elicitation questions routed to specific roles | `engagement`, `role` |
| `get_diagram_graph` | Structured component graph and Mermaid flowchart syntax string | `engagement`, `format` |
| `get_render_payload` | Complete render payload (`is_provisional`, `unripe_subjects`, `open_conflicts`) | `engagement` |
| `get_dangling_references` | Unresolved citations cited by statements but absent from knowledge plane | `engagement` |
| `get_engagement_export` | Single bulk export payload for third-party tools | `engagement` |
| `query_graph` | Execute read-only Cypher query on engagement graph | `cypher_query`, `engagement` |
| `get_graph_summary` | Graph summary node/rel counts and schema version | *(none)* |

---

## 🎨 6. Complementary Documentation

- 🎨 **[Third-Party Integration Guide](THIRD-PARTY-INTEGRATION-GUIDE.md)**: Full guide to writing custom renderers (DOCX, PPTX, Web UI) without running the server.
- 📊 **[Graph Schema Specification (SCHEMA.md)](SCHEMA.md)**: Automatically generated Kùzu DB table & property schemas.
- 📖 **[Software Architecture Specification (architecture.md)](architecture.md)**: ADR-0014 and ADR-0015 dual-plane specification.
