# 🔌 External Interface Specification & MCP Response Schemas (ADR-0014 / ADR-0015)

This document is the official technical contract specification for the **FastMCP** server interface exposed by the **LLMOps** platform. It documents the response structure and all **53 MCP tools** exposed by the unified server (`mcp_server/main.py`) under `schema_version: "1.42"`.

> For full REST route specifications (`§5.1` to `§5.42`), see [`contracts/knowledge-hub-api-v1.md`](contracts/knowledge-hub-api-v1.md). For version history and compatibility guarantees, see [`VERSIONING.md`](VERSIONING.md).

---

## 🎯 1. Architecture Overview & The 4 Integration Surfaces

LLMOps provides **four distinct surfaces of integration** to accommodate both agentic workflows and decoupled client applications (e.g. *Archinex*, *Architecture Studio*, *Document Engine*):

```
1. Sealed Snapshot Channel (Offline JSON File / HTTP GET /snapshot/latest)
   ↳ Zero-latency, canonical-json v1 sealed snapshot with sha256 checksum, type:slug identifiers, and applicability index.
2. FastMCP Server (SSE / STDIO via JSON-RPC 2.0) + REST Governance API (/api/...)
   ↳ Interactive 53-tool MCP surface for LLM agents (Antigravity, Claude Desktop, Cursor) and typed REST routes for clients.
3. Python SDK (mcp_server.renderer_interface.RendererClient)
   ↳ Direct typed Python client for local renderers and scripts.
4. CLI Gateways (poetry run kb / poetry run elicit)
   ↳ Validated ingestion, publication, ontology checks, and engagement elicitation commands.
```

### 🔒 Guarantee: 100% Deterministic Core
- Zero server-side LLM calls on served routes or in `tools/elicitation/`.
- Level gate progression (`L0_named` → `L4_specified`), contradiction detection, conflict tracking, cascade derivation, and option checking are implemented via deterministic Cypher and symbolic logic.
- An elicitation session and every sealed snapshot are strictly replayable and auditable.

---

## 🌐 2. Transports, Endpoints & Authentication

- **Recommended Transport for Agents:** HTTP SSE (`Server-Sent Events`) at endpoint `/sse`.
- **Static / Web Application Channel:** `GET /snapshot/latest` and `GET /snapshot/{snapshot_id}` with `ETag` and `Cache-Control` headers.
- **STDIO Transport (Local Agents):** `poetry run mcp-server` (unified, 53 tools), `poetry run mcp-server-knowledge`, and `poetry run mcp-server-engagement`.
- **Public Production Endpoint (GCP Cloud Run):** `https://llmops-mcp-server-344571265365.europe-west1.run.app/sse`
- **HTTP Authentication & Actor Identity (contracts `1.37` / `1.39`):**
  - FastMCP HTTP startup requires `SERVER_TOKEN` (or `ENGAGEMENT_TOKENS` with scoped tokens such as `kb:review`, `kb:maintain`, `kb:delegate`, `eng:delegate`, `eng:service`, `eng:create`).
  - Requests supply the token via `Authorization: Bearer <TOKEN>` (or `X-API-Key: <TOKEN>`), verified in constant time (`secrets.compare_digest`).
  - Acting expert identity is carried via signed EdDSA (Ed25519) assertions (`X-Actor-Token`, published JWKS at `GET /.well-known/jwks.json`, anti-replay `jti`), enforced strictly when `LLMOPS_REQUIRE_SIGNED_ACTOR=1` (raw `X-Actor-Email` accepted only in non-strict mode).
- **Connection Safety & Semantics:**
  - Read-Only connection on the underlying **LadybugDB** (`.lbug`) graph databases for public read tools.
  - Any Cypher write attempt (`CREATE`, `SET`, `DELETE`) via `query_graph` is rejected at driver/validator level.

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
- **Error / Invalid Argument / Unauthorized (`status: "error"` / `"invalid_argument"` / `"unauthorized"`)**: Contains explanatory string in `reason`.

---

## 📚 4. Unified FastMCP Tools Catalog — All 53 Tools (`schema_version: "1.42"`)

The unified server (`mcp_server/main.py`, `LLMOPS_PLANE=all`) exposes **53 MCP tools** spanning the Knowledge Plane (43 tools, including shared graph utilities) and the Engagement Plane (10 engagement-specific tools; `query_graph` and `get_graph_summary` serve both planes).

### 4.1 Core Knowledge & Graph Tools (9 Tools)

| Tool Name | Description | Key Parameters |
|---|---|---|
| `list_assets` | List architecture asset identifiers, titles, and metadata from the knowledge base | `type`, `phase`, `domain`, `status` |
| `get_asset` | Retrieve full content and frontmatter metadata for an architecture asset (supports citable revisions/snapshots, K3) | `id`, `version`, `snapshot` |
| `get_assets` | Resolve a list of architecture asset identifiers in a single batch call | `ids` |
| `get_decision_trail` | Retrieve frontmatter, parsed sections, raw content, and full supersession chain (`SUPERSEDES`) for an ADR | `id` |
| `get_glossary_term` | Retrieve the canonical definition for an architecture glossary term | `term` |
| `search_assets` | Execute hybrid search over architecture asset titles, identifiers, and metadata | `query`, `filters` |
| `get_principles_for` | Retrieve architecture principles applicable to a specific phase or domain | `phase`, `domain` |
| `query_graph` | Execute a read-only Cypher query against the knowledge graph or a target engagement graph | `cypher_query`, `engagement` |
| `get_graph_summary` | Discover available databases and return node counts and `schema_version` (`1.42`) | *(none)* |

### 4.2 Compliance, Regulatory Frameworks & Skills Tools (7 Tools)

| Tool Name | Description | Key Parameters |
|---|---|---|
| `list_frameworks` | List regulatory and security frameworks embedded in the knowledge base with versions and control counts | *(none)* |
| `list_controls` | List security and compliance controls with optional filtering by framework, domain, or severity | `framework`, `domain`, `severity` |
| `get_compliance_trail` | Retrieve full compliance traceability for a specific control to implementing patterns/principles/ADRs | `control_id` |
| `get_compliance_matrix` | Evaluate compliance coverage of an engagement project against a regulatory framework | `engagement`, `framework` |
| `get_framework_coverage` | Compute coverage of regulatory frameworks by the knowledge base (contract `1.3`) | `frameworks` |
| `list_skills` | List canonical technical skills, expertises, and expected competencies from the knowledge base | `domain` |
| `get_skills_matrix` | Calculate the staffing skill coverage matrix and risk index for an engagement | `engagement`, `blueprint_path` |

### 4.3 RFP Analysis & Zero-Draft HLD Tools (5 Tools)

| Tool Name | Description | Key Parameters |
|---|---|---|
| `shred_rfp` | Deconstruct an RFP / tender document into atomic requirements and map them to KB assets | `rfp_text`, `engagement`, `persist` |
| `generate_zero_draft_hld` | Generate a structured High-Level Design (HLD) zero-draft from KB assets and RFP requirements (FR/EN) | `engagement`, `project_title`, `client_name`, `language` |
| `get_rfp_compliance_matrix` | Retrieve the triangular compliance matrix (RFP Requirements vs KB Assets vs Controls) | `engagement` |
| `get_rfp_coverage_gaps` | Analyze KB coverage blind spots (coverage gaps) on an RFP (contract `1.36`, Issue #133) | `engagement`, `rfp_text` |
| `trigger_rfp_elicitation` | Trigger targeted elicitation questions specifically for uncovered RFP requirements (gaps) | `engagement` |

### 4.4 Doctrine Evaluation, Candidate Governance & RBAC Tools (19 Tools)

| Tool Name | Description | Key Parameters |
|---|---|---|
| `get_doctrine_context` | Return applicable doctrine (active principles, all required regulatory controls, patterns) for a subject (contracts `1.1`, `1.25`, `1.38`) | `subject`, `domains`, `frameworks`, `phase`, `max_items`, `max_chars` |
| `check_option` | Judge an architecture option against the doctrine with deterministic check clauses (contract `1.1`) | `option`, `subject`, `domains`, `frameworks` |
| `suggest_knowledge_improvement` | Submit external REX, candidate pattern, or feedback to improve the knowledge base | `title`, `rationale`, `suggested_change`, `author`, `contact_email`, `source_engagement` |
| `submit_kb_candidate` | Submit a knowledge base candidate (`new_asset`, `amendment`, `rex`, `trigger`, `fact_key`) (contract `1.2` / `1.29`) | `candidate`, `candidate_id` |
| `list_kb_candidates` | List knowledge base candidates, newest first | `status`, `source`, `domain`, `engagement` |
| `get_kb_candidate` | Retrieve a knowledge base candidate with its deterministic checks, review, and history | `candidate_id` |
| `review_kb_candidate` | Review a knowledge base candidate (`accept`, `amend`, `reject`; requires `kb:review` and domain ownership) | `candidate_id`, `action`, `reviewer`, `reason`, `amended_content`, `auto_promote` |
| `get_kb_me` | Return the acting expert profile resolved from the authenticated assertion/header (contracts `1.4` / `1.37`) | *(none)* |
| `get_review_inbox` | List candidates waiting for the acting expert, oldest first, with due dates (contract `1.5`) | *(none)* |
| `assign_kb_candidate` | Reassign a candidate in review to another owner (current owner or `kb:maintain`) | `candidate_id`, `handle`, `reason` |
| `request_kb_review` | Request a second review or advisory opinion from a specific expert on a candidate in review | `candidate_id`, `handle`, `kind`, `message`, `due_at` |
| `comment_kb_candidate` | Add a comment to a candidate discussion thread (a comment is not a decision) | `candidate_id`, `body` |
| `list_domain_owners` | Return the registry of domain owners (without notification secrets), domains, and default owner | *(none)* |
| `get_kb_freshness` | Regulatory and doctrine freshness indicators (requires `kb:review`; contract `1.36`, Issue #131) | `framework`, `owner`, `days` |
| `list_kb_delegations` | List domain ownership and review delegations (requires `kb:review`; contract `1.37`) | `delegate`, `delegator`, `active_only` |
| `create_kb_delegation` | Delegate review rights and domain ownership temporarily to another expert (contract `1.37`) | `delegate`, `domains`, `roles`, `expires_at`, `starts_at` |
| `revoke_kb_delegation` | Revoke an active delegation immediately (delegator or `kb:maintain`; contract `1.37`) | `delegation_id` |
| `revoke_kb_auth` | Immediately revoke a token JTI or an expert handle/email (requires `kb:admin` or `kb:maintain`; contract `1.37`) | `identifier`, `reason`, `is_jti` |
| `get_kb_audit` | Query the governance access audit log (requires `kb:review`; contract `1.37`) | `actor`, `action`, `outcome`, `limit` |

### 4.5 Federating Ontology Tools (3 Tools — Contract `1.42`)

| Tool Name | Description | Key Parameters |
|---|---|---|
| `list_ontology_terms` | List federated ontology terms and projections (contract `1.42`, Issue #175) | `concept_class`, `status` |
| `get_ontology_term` | Retrieve a specific ontology term by its citable URN and optional revision (contract `1.42`, Issue #175) | `urn`, `revision` |
| `export_ontology_catalog` | Export the consolidated architecture ontology catalog (HLD concepts, axes, leaves, triplets; contract `1.42`) | `clause`, `leaf` |

### 4.6 Engagement Plane Tools (10 Engagement-Specific Tools)

*(Note: `query_graph` and `get_graph_summary` from §4.1 are also exposed on the standalone `mcp-server-engagement` plane, bringing it to 12 tools; the standalone `mcp-server-knowledge` plane additionally exposes `get_knowledge_analytics` and `get_domain_prominence_report`.)*

| Tool Name | Description | Key Parameters |
|---|---|---|
| `get_subject` | Retrieve details, maturity level, and framing definition for an architecture subject | `subject`, `engagement`, `db_path` |
| `get_subject_trajectory` | Retrieve maturity level progression trajectory (timeline of questions and answer excerpts) | `subject`, `engagement`, `db_path` |
| `get_board` | Retrieve the maturity board showing all subjects (`L0_named` to `L4_specified`), origin, and blocking questions | `engagement` |
| `get_statements` | Retrieve active architecture statements with confidence and attribution | `engagement`, `subject`, `section`, `status` |
| `get_conflicts` | Retrieve open and arbitrated architecture conflicts (`contradiction`, `principle_violation`, `stale_basis`) | `engagement`, `status` |
| `get_open_questions` | Retrieve open elicitation questions routed to specific architect roles | `engagement`, `role` |
| `get_diagram_graph` | Retrieve the architecture graph formatted as JSON nodes/edges or Mermaid flowchart syntax | `engagement`, `format`, `db_path` |
| `get_render_payload` | Retrieve complete structured render payload (`is_provisional`, `unripe_subjects`, `open_conflicts`) | `engagement`, `db_path` |
| `get_dangling_references` | Report unresolved citations referenced by statements but absent from the knowledge plane | `engagement` |
| `get_engagement_export` | Retrieve complete bulk export (board, render payload, diagram graph) in a single call (E4) | `engagement` |

---

## 🎨 5. Complementary Documentation

- 📋 **[Knowledge Hub REST API Contract (contracts/knowledge-hub-api-v1.md)](contracts/knowledge-hub-api-v1.md)**: Detailed REST contract (`§5.1` to `§5.42`).
- 🎨 **[Third-Party Integration Guide](THIRD-PARTY-INTEGRATION-GUIDE.md)**: Full guide to writing custom renderers (DOCX, PPTX, Web UI) without running the server.
- 📊 **[Graph Schema Specification (SCHEMA.md)](SCHEMA.md)**: LadybugDB (`.lbug`) table & property schemas.
- 📖 **[Architecture Document (ARCHITECTURE-LLMOps.md)](ARCHITECTURE-LLMOps.md)**: Current Knowledge Hub architecture (`1.42`).
