# WORKORDER-NOTES.md — LLMOps Third-Party Integration Audit Log

This document tracks the execution progress, audit findings, deferred items, and discrepancies identified during the execution of the Workorder for repository `MauriceIsrael/LLMOps`.

---

## Lot 0 — Déblocage légal et visibilité (Completed)

### 1. Accomplished Actions
- **LICENSE Created**: Installed root `LICENSE` file containing full MIT License text (Copyright (c) 2026 Maurice Israel).
- **Purge of Local `file://` URLs**:
  - Replaced all machine-specific `file://...` URLs in `README.md`, `docs/INTERFACE.md`, `docs/architecture.md`, `docs/renderer_integration.md`, `docs/user_manual.md`, `tests/golden/*.md`, `WORKED-EXAMPLE.md`, and `question.md.j2` with clean relative paths.
  - Added automated CI verification step in `.github/workflows/ci.yml` that checks `git grep -n "file://"` and fails the build if any matching link is found.
- **Repository Hygiene & Test Artifact Untracking**:
  - Executed `git rm --cached` on all tracked test-run artifacts matching `artifacts/test-*` and `projects/test-*` (89 items untracked).
  - Verified `git ls-files | grep -c "^artifacts/test-\|^projects/test-"` returns `0`.
  - Added build log exclusions (`npm_output.log`, `check_output.txt`, `svelte-check-output.txt`, `scratch/`) for `apps/kb-client-app/` under `.gitignore`.
  - Removed unused dependencies `llama-index-llms-openai` and `llama-index-embeddings-openai` from `pyproject.toml` and updated `poetry.lock`.

### 2. Noticed but Deferred / Action Required
- **GitHub Repository Metadata**:
  - `gh repo edit` failed due to missing GitHub CLI authentication (`HTTP 401: Bad credentials`).
  - **Human Action Required**: Set repository description and topics manually in GitHub Settings or via authenticated `gh auth login`:
    - **Description**: *"Queryable architecture knowledge graph in MCP: every statement carries confidence and maturity so your document generators know what they can assert."*
    - **Topics**: `mcp`, `model-context-protocol`, `knowledge-graph`, `architecture-decision-records`, `graphrag`, `langgraph`.

### 3. Discrepancies with Workorder Spec
- **Vendor Provenance Audit (0.2)**: `apps/kb-client-app/.agents` had already been removed in commit `c2e82fd`. The remaining contents of `apps/kb-client-app/` are internal web application code and configuration files.

---

## Lot 1 — Les dix premières minutes (Completed)

### 1. Accomplished Actions
- **Docker Compose Update (1.1)**: Updated `docker/docker-compose.yml` to reflect ADR-0015 volume mounts (`kuzu_data:/app/data`), added `SERVER_TOKEN=${SERVER_TOKEN:-llmops-dev-token-2026}`, and made `OPENAI_API_KEY` explicitly optional.
- **One-Line Onboarding Demo Targets (1.2)**: Created root `Makefile` featuring `make demo` and `make demo-check` targets. `make demo-check` queries `get_graph_summary` and asserts `knowledge.node_counts.Asset > 0` (Asset count: 47).
- **Versioned Demonstration Engagement (1.3)**: Published and versioned reference engagement `nordwave-mcx-2027.kuzu` (`!data/engagements/nordwave-mcx-2027.kuzu` in `.gitignore`) so repository clones have ready-to-use engagement graph data.
- **MCP Configuration Snippets (1.4)**: Updated `README.md` in English with copy-pasteable MCP client configuration snippets (STDIO local & SSE remote) placed within the first 30 lines. Created `README.fr.md` for French-speaking users.

### 2. Noticed but Deferred / Action Required
- None.

### 3. Discrepancies with Workorder Spec
- None.

---

## Lot 2 — Réduire le coût d'écriture d'un client (Completed)

### 1. Accomplished Actions
- **Published Offline Fixtures (2.1)**: Created `fixtures/` containing exported JSON files (`knowledge_snapshot.json`, `engagement_snapshot.json`, `get_render_payload.json`, `get_board.json`, `get_diagram_graph.json`) and `fixtures/README.md` in English. Added generator script `scripts/export_fixtures.py`.
- **Machine Contract & Schemas (2.2)**: Created `scripts/generate_schemas.py` producing `schemas/envelope.schema.json` and TypeScript definitions `schemas/types.ts`. Added contract test `tests/contract/test_fixtures_contract.py` enforcing fixture envelope validity and zero divergence from `scripts/export_fixtures.py`.
- **Contract Versioning Policy (2.3)**: Created `docs/VERSIONING.md` in English documenting semver rules for `schema_version: "1.0"`, stable vs transient fields, and deprecation policies.

### 2. Noticed but Deferred / Action Required
- None.

### 3. Discrepancies with Workorder Spec
- None.

---
