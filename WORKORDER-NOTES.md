# WORKORDER-NOTES.md — LLMOps Third-Party Integration Audit Log

This document tracks the execution progress, audit findings, deferred items, and discrepancies identified during the execution of the Workorder for repository `MauriceIsrael/LLMOps`.

---

## Lot 0 — Déblocage légal et visibilité (Completed)

### 1. Accomplished Actions
- **LICENSE Created**: Installed root `LICENSE` file containing full MIT License text (Copyright (c) 2026 Maurice Israel).
- **Purge of Local `file:///` URLs**:
  - Replaced all machine-specific `file:///home/momo/Dev/LLMOps/...` URLs in `README.md`, `docs/INTERFACE.md`, `docs/architecture.md`, `docs/renderer_integration.md`, `docs/user_manual.md`, `tests/golden/*.md`, `WORKED-EXAMPLE.md`, and `question.md.j2` with clean relative paths.
  - Added automated CI verification step in `.github/workflows/ci.yml` that checks `grep -rn "file:///" --include=*.md .` and fails the build if any matching link is found.
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
