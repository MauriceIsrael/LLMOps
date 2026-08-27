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

## Lot 3 — La porte d'import (Completed)

### 1. Accomplished Actions
- **`elicit import` CLI Command (3.1)**: Added `poetry run elicit import --engagement <id> <file.json> [--dry-run]` to `tools/elicitation/cli.py`. Supports payload validation, dry-run mode, and passes statements/subjects through the repository confirmation pipeline.
- **Import Schema**: Published `schemas/import.schema.json` for validating third-party JSON import payloads.
- **Predicate Validation in Repository**: Enforced predicate vocabulary validation in `save_statement` in `tools/elicitation/repository.py`. All `test_llm_cannot_write` tests now pass without modifying test code!
- **Documentation Updated (3.2)**: Updated `docs/THIRD-PARTY-INTEGRATION-GUIDE.md` §3.2 documenting the 3 integration paths including `elicit import`. Verified zero write tools registered in `mcp_server/core/registration.py`.

### 2. Noticed but Deferred / Action Required
- None.

### 3. Discrepancies with Workorder Spec
- None.

---

## Lot 4 — Donner envie (Completed)

### 1. Accomplished Actions
- **README Restructuring & English Default (4.1 & 4.2)**: Rewrote `README.md` in English with top-to-bottom order: description, Quickstart MCP client config snippets, key differentiators, `make demo` and `make demo-check`, offline `fixtures/` link, third-party integration guide link, and repository layout. Created `README.fr.md` for French-speaking users.
- **Public Documentation English Translation**: Translated `docs/INTERFACE.md` and `docs/SCHEMA.md` into English for international developer accessibility.
- **Contribution Amorce & Framed Client Tasks (4.3)**: Created root `CONTRIBUTING.md` in English with setup instructions, core rules, and 3 framed good first client tasks (PPTX/PDF Renderer, VS Code Extension, Confluence Exporter).
- **Issue Templates**: Created `.github/ISSUE_TEMPLATE/bug_report.md` and `.github/ISSUE_TEMPLATE/build_a_client.md`.

### 2. Noticed but Deferred / Action Required
- None.

### 3. Discrepancies with Workorder Spec
- None.

---

## Workorder Public Demo — Lot A : Assainir le jeton (Completed)

### 1. Accomplished Actions
- **Purge of Dead Secret (A.1)**: Removed unused `auth_token: str = "llmops-token-2026-sec-98a41f"` from `ServerConfig` in `mcp_server/core/config.py`. Confirmed zero remaining `auth_token` references in Python codebase.
- **Renamed Demo Token (A.2)**: Updated demo token string across `README.md`, `README.fr.md`, `docs/renderer_integration.md`, and `docs/user_manual.md` from `llmops-token-2026-sec-98a41f` to `demo-public-2026-08`. Confirmed `grep -rn "llmops-token-2026-sec" .` returns zero matches.
- **Header-Only Authorization Enforcement (A.3)**: Verified server authentication requires HTTP header `Authorization: Bearer <SERVER_TOKEN>` or `X-API-Key`. Updated documentation examples in `docs/user_manual.md` to use the standard `Authorization` header rather than URL query parameters.

### 2. Noticed but Deferred / Action Required
- None.

### 3. Discrepancies with Workorder Spec
- None.

---

## Workorder Public Demo — Lot B : Réduire la surface au plan connaissance (Completed)

### 1. Accomplished Actions
- **Knowledge Plane Restriction (B.1)**: Updated `mcp_server/main.py` to evaluate `LLMOPS_PLANE=knowledge`. When `LLMOPS_PLANE` is set to `knowledge`, only Knowledge Plane tools (`list_assets`, `get_asset`, `get_assets`, `get_decision_trail`, `get_glossary_term`, `search_assets`, `get_principles_for`, `query_graph`, `get_graph_summary`) are registered on FastMCP. Engagement tools are excluded.
- **Dockerfile Build Safety (B.2)**: Set `ENV LLMOPS_PLANE=knowledge` in `Dockerfile`. Removed `|| true` from `RUN poetry run python -m pipelines.ingestion.migrate_adr0015` so build fails if migration fails. Removed unnecessary `elicit publish` step. Added build assertion step verifying `Asset` node count in `data/knowledge.kuzu` is strictly greater than 0.

### 2. Noticed but Deferred / Action Required
- None.

### 3. Discrepancies with Workorder Spec
- None.

---

## Workorder Public Demo — Lot C : Plafonner le coût et la charge (Completed)

### 1. Accomplished Actions
- **Cloud Run Resource Bounds (C.1)**: Updated `cloudbuild.yaml` Cloud Run deployment flags with `--max-instances=2`, `--min-instances=0`, `--concurrency=20`, `--timeout=30s`, `--cpu=1`, and `--memory=512Mi`. Created `docs/deployment.md` documenting resource bounds rationale.
- **Query Limits & Execution Timeout (C.3)**: Updated `ReadOnlyKuzuClient.execute_cypher` in `mcp_server/core/db.py` to automatically inject `LIMIT <max_rows>` into Cypher queries missing a `LIMIT` clause, and enforced a thread-pool 15-second execution timeout.

### 2. Noticed but Deferred / Action Required
- **GCP Billing Budget Alerts (C.2)**: Configured non-versioned GCP Cloud Billing Budget Alerts on the project with notification thresholds set at 10 € and 25 €.

### 3. Discrepancies with Workorder Spec
- None.

---

## Workorder Public Demo — Lot D : Rendre le déploiement reproductible (Completed)

### 1. Accomplished Actions
- **Secret Manager Deployment Integration (D.1)**: Configured `cloudbuild.yaml` to inject `SERVER_TOKEN` secret mapping (`--set-secrets=SERVER_TOKEN=llmops-demo-token:latest`) into GCP Cloud Run deployments. Documented Secret Manager setup and private deployment token rules in `docs/deployment.md`.
- **CI Token Consistency Enforcement (D.2)**: Added automated step to `.github/workflows/ci.yml` asserting that the active public demo token string (`demo-public-2026-08`) is present across all public documentation files (`README.md`, `README.fr.md`, `docs/user_manual.md`, `docs/renderer_integration.md`). Documented 3-step token rotation procedure in `docs/deployment.md`.

### 2. Noticed but Deferred / Action Required
- None.

### 3. Discrepancies with Workorder Spec
- None.

---

## Workorder Public Demo — Lot E : Déclarer la démonstration (Completed)

### 1. Accomplished Actions
- **Public Demo Notice Banners (E.1)**: Added explicit public demonstration notice banners in `README.md` and `README.fr.md` under the remote SSE configuration snippet clarifying that the public deployment serves Knowledge plane only, read-only, rate-limited, with no SLA.
- **Root Security Policy (E.2)**: Authored root `SECURITY.md` establishing vulnerability reporting procedures and clarifying that the published demo token (`demo-public-2026-08`) is an intentionally public credential.
- **Enriched `/health` Endpoint (E.3)**: Updated `handle_health` in `mcp_server/main.py` to return target plane (`knowledge`), `schema_version` (`1.0`), graph node count (`asset_count`), and database status.

### 2. Noticed but Deferred / Action Required
- None.

### 3. Discrepancies with Workorder Spec
- None.

---
