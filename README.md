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

> **Public Demo Instance Notice:** Exposes both Knowledge plane and Engagement plane (scoped strictly to the reference demo engagement). Read-only, rate-limited, no SLA. The token above (`demo-public-2026-08`) is intentionally public and rotated periodically. Do not use it for private data.

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
- **Engagement Plane (`demo-engagement-2027`)**: `Subject`: 8 nodes, `Statement`: 9 nodes, `Conflict`: 2 nodes.

### 4. Run the governance server locally (for Archinex)

The KB is enriched and governed from Archinex, which talks to this server over REST. One command starts it with a
persistent governance database (SQLite) and a delegating service token:

```bash
poetry install
poetry run python scripts/serve_local.py      # or: make serve   (Windows: no make, use the first form)
```

- **Restart** = `Ctrl+C`, then run it again: the state (candidates, reviews, owners, embeddings, reuse journal) lives in
  `data/governance.db`, not in the process. Run it again after changing `data/kb/owners.yaml`
  (`poetry run kb migrate-governance --force-owners` applies the file to an already initialised database).
- The script prints the **service token** to configure in Archinex (`LLMOPS_AUTH_TOKEN`); it is generated once and kept in
  `.llmops-local-service-token` (git-ignored), so a restart does not change it. Archinex also needs `LLMOPS_BASE_URL`
  (`http://127.0.0.1:8000`) and `LLMOPS_ALLOWED_HOSTS` if the host is not local.
- It reads `.env` into the environment first. Secrets such as `OWNER_DISCORD_WEBHOOK` (Discord for owners without an
  Archinex account) belong in the environment or `.env`, **never** in `data/kb/owners.yaml`.
- Experts are identified by e-mail (`X-Actor-Email`, sent by Archinex): each e-mail must appear on **one** owner of
  `data/kb/owners.yaml`; roles (`kb:maintain`, `kb:admin`, `kb:evaluate`) are declared there.
- Test without a deployed instance: `poetry run python scripts/contract_server.py --port 8099` (scratch copy of the KB,
  fake experts) or the image `docker build -f docker/Dockerfile.contract -t llmops-contract:latest .` (see
  [`docs/deployment.md`](docs/deployment.md) for Cloud Run / Cloud SQL).

---

## Key Differentiators

1. **100% Deterministic & Auditable Core (0 Server LLM Costs)**  
   No non-deterministic LLM calls on the server. The knowledge server is backed by a typed graph database (LadybugDB) enforcing strict schemas. Model intelligence remains client-side. Elicitation rules, level gates, and conflict detections are pure symbolic logic.
2. **Provisional Statements & Confidence Tracking**  
   Every architectural statement explicitly tracks its confidence (`verified`, `designed`, `vendor-stated`, `stated-by-client`, `assumed`) and subject maturity level (`L0_named` to `L4_specified`). Generated documents know if they are provisional and state why (`is_provisional: true`, `unripe_subjects`, `open_conflicts`).
3. **Dual-Plane Physical Isolation (ADR-0015)**  
   Reusable enterprise patterns (`data/knowledge.lbug`) are physically separated from per-project dynamic state (`data/engagements/<id>.lbug`). Cross-plane queries are prohibited; references resolve strictly via asset identifiers.
4. **Sealed Snapshot Channel for Client Apps & CI/CD**  
   Publishes canonical, hashed JSON snapshots (`fixtures/sealed_snapshot.json` or `GET /snapshot/latest`) with normalized typed identifiers (`decision:ADR-0014`, `principle:P-002`), SHA-256 payload sealing, and an applicability index for zero-latency, resilient third-party integrations (e.g., *Architecture Studio*, *La Suite*).
5. **Skills Competency Meta-Model & Staffing Risk Audit (Gap G5)**  
   Projects architecture blueprint requirements onto a formal 9-skills catalogue. Audits mobilized team coverage in real time (`elicit audit-skills`), emits `G5_unstaffed_skill_gap` alerts, and enables Best-Match question routing based on engineer expertise.
6. **Pre-Sales RFP / CCTP Analyzer (Dream Team Staffing Matrix)**  
   Ingests client tenders and CCTP documents (Word DOCX, PDF, Markdown), detects regulatory security targets (NIS2, SecNumCloud, 3GPP, ISO27001), and automatically sizes the target project team in ETP with recommended roles, seniorities, and missions.
7. **Continuous Harvest & Multi-Channel Webhook Loop**  
   Proven field patterns and REX are harvested from projects (`elicit harvest`) and instantly dispatched to the Knowledge Owner via Discord Webhooks (rich embeds) and mobile push (`ntfy.sh`) for formal governance review.
8. **Sovereign TELCO MCX Regulatory Frameworks (14 Frameworks, 53 Controls)**  
   Exhaustive technical compliance coverage across European and mission-critical standards: NIS2, CER (Critical Entities Resilience EU 2022/2557), CRA (Cyber Resilience Act EU 2024/2847), GDPR, GSMA (SGP.22/32 eSIM, Central EIR, SAS EAL4+), 3GPP Rel-18 (MCX, NEF, SCAS/NESAS, MDA AIOps), ITIL v4 / FCAPS O&M, Telco Resilience (Tier IV dual-datacenter, G.8275.1 PTP sync, >30d Rubidium holdover), and PPDR Tactical Terminals (ECC Band 68/28, TETRA DMO, MIL-STD-810H, ATEX, ISO 11451/UN R2144 vehicle EMC).
9. **Automated RFP Shredder & Bilingual Zero-Draft HLD Engine (FR / EN)**  
   Deconstructs client tenders into atomic requirements (`shred-rfp`), builds the triangular compliance matrix against standard architecture decisions (ADRs) and regulatory controls, and auto-generates a High-Level Design pre-sales document (`zero-draft-hld`) in English or French with zero residual gaps. Ready-to-use deliverable templates are available in `templates/HLD-zero-draft-template.md` (FR) and `templates/HLD-zero-draft-template.en.md` (EN).
10. **Doctrine Context & Option Judge (contract 1.1)**  
    `get_doctrine_context` / `GET /api/knowledge/context` returns the doctrine applicable to a subject (active principles, required regulatory controls, patterns, ADRs) with bounded excerpts; `check_option` / `POST /api/knowledge/check` judges an option against structured `checks` clauses of the doctrine (`supports` / `violates` / `unassessed`, with citations). Both are fully deterministic — no LLM on the server. Evaluation: `make eval-check`.
11. **Knowledge Enrichment Cycle (contract 1.2)**  
    Every new piece of knowledge goes through a persisted candidate queue (`/api/knowledge/candidates`, `submit_kb_candidate`…), deterministic checks (schema, references, duplicates, anonymization, doctrine conflicts, unreviewed LLM content), routing to the domain owner (`data/kb/owners.yaml`) and a human review (second review for principles), before `kb promote` / `kb publish` write and seal it. Confidence is computed from evidence, never from the author.
12. **Governance from Archinex & reuse of validated knowledge (contracts 1.3 to 1.13)**  
    Experts act through Archinex (identity by e-mail, review inbox, solicitation, doctrine workshop and evaluations, regulatory framework ingestion, server-side promotion and publication, health). Similarity over vectors computed by the client (FR/EN), reuse confirmations judged assumption by assumption (never automatic), evaluation of the similarity thresholds. The engagement part is deprecated since 1.13. See [`docs/contracts/knowledge-hub-api-v1.md`](docs/contracts/knowledge-hub-api-v1.md) §5 and [`docs/VERSIONING.md`](docs/VERSIONING.md).
13. **Dual-Mode Architecture & Architecture Suite Contract v1**  
    Provides both synchronous REST endpoints (`/api/rfp/*`, `/api/compliance/*`, `/api/knowledge/*`, `/api/skills/*`) for interactive web interfaces and CLI tools, as well as sealed canonical snapshots (`latest.json`) for offline-first admission gates (per ADR-SUITE-05). All contracts follow strict provenance (`sourceSystem: "knowledge-hub"`), canonical SHA-256 sealing, and Fail Loud resilience.

---

## Development & Testing

```bash
# Run unit and contract test suite
make test

# Run linter
make lint

# Fast local gate: lint + frozen interface contract + unit tests
make verify

# Install the git pre-push hook running `make verify`
make hooks

# End-to-end scenarios of the reference demo (examples/), and the project-name guard
make test-e2e
make check-names

# Regulatory framework ingestion (offline) and coverage
poetry run kb ingest-framework --framework NIS2 --version 2022/2555 --source <official text>
poetry run kb review-sheet --framework NIS2 && poetry run kb apply-review data/staging/NIS2/2022-2555/review_sheet.csv
poetry run kb declare-coverage --framework NIS2 --by @expert-handle
poetry run kb coverage-report   # docs/COVERAGE.md

# Knowledge base candidate cycle (maintainers)
poetry run kb list --status in_review
poetry run kb promote CAND-20261001-0007
poetry run kb publish
poetry run kb remind   # schedule with cron

# Run interactive CLI elicitation scan
poetry run elicit scan --engagement demo-engagement-2027 --max-questions 3
```

> **No project is hard-coded.** Tools, routes and `elicit` commands that need an engagement or a
> blueprint take them explicitly or from `LLMOPS_ENGAGEMENT` / `LLMOPS_BLUEPRINT` (environment or
> `.env`; `make demo`, the Dockerfile and `cloudbuild.yaml` set them for the reference demo). The
> reference demo lives in [`examples/`](examples/README.md).

---

## Documentation Links

- **[Knowledge Hub API v1 Contract](docs/contracts/knowledge-hub-api-v1.md)**: Formal contract specification for the Architecture Suite (`requirements-intake`, `document-engine`, `Document-studio`, `WBS-engine`).
- **[Regulatory Coverage](docs/COVERAGE.md)**: coverage of each framework by the knowledge base (manifests, missing requirements).
- **[Versioning](docs/VERSIONING.md)** and **[Deprecation Policy](docs/DEPRECATION.md)**: contract `1.x` guarantees, frozen interface shapes (`tests/contract/frozen/`), deprecation signals. The engagement part (elicitation / arbitration) is **deprecated since 1.13** in favour of Archinex: see the [migration guide](docs/migration-archinex.md).
- **[Third-Party Integration Guide](docs/THIRD-PARTY-INTEGRATION-GUIDE.md)**: Full guide to writing custom renderers (DOCX, PPTX, Web UI) and consuming sealed snapshots.
- **[External Interface Specification (INTERFACE.md)](docs/INTERFACE.md)**: Technical MCP contract, response envelopes, JSON Schemas, and transport protocols.
- **[Epistemic Alignment Guide (EPISTEMIC-ALIGNMENT.md)](docs/EPISTEMIC-ALIGNMENT.md)**: Correspondence table between KH confidence and Architecture Studio proof models.
- **[Schema Specification (SCHEMA.md)](docs/SCHEMA.md)**: Automatically generated LadybugDB graph schema.
- **[Software Architecture (ADR-0014 / ADR-0015)](docs/architecture.md)**: Internal dual-plane architecture specification.
- **[User Manual](docs/user_manual.md)**: CLI elicitation workflow and level gates.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
