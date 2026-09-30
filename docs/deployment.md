# GCP Cloud Run Deployment & Cost Control Guide

This document specifies the deployment configuration, security bounds, resource limits, and token rotation procedures for the LLMOps FastMCP service on Google Cloud Run.

---

## 1. Cloud Run Resource & Cost Bounds (`cloudbuild.yaml`)

The production deployment (`llmops-mcp-server` in region `europe-west1`) is configured with deterministic resource bounds in `cloudbuild.yaml`:

```yaml
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'llmops-mcp-server'
      - '--image'
      - 'europe-west1-docker.pkg.dev/$PROJECT_ID/llmops/mcp-server:${_TAG}'
      - '--region'
      - 'europe-west1'
      - '--platform'
      - 'managed'
      - '--allow-unauthenticated'
      - '--max-instances=2'
      - '--min-instances=0'
      - '--concurrency=20'
      - '--timeout=30s'
      - '--cpu=1'
      - '--memory=512Mi'
      - '--set-env-vars'
      - 'GRAPH_BACKEND=ladybug,LLMOPS_TRANSPORT=sse,LLMOPS_PLANE=all,ENGAGEMENT_TOKENS=demo-public-2026-08:nordwave-mcx-2027'
      - '--set-secrets'
      - 'SERVER_TOKEN=llmops-auth-token:latest,OWNER_NOTIFICATION_WEBHOOK=llmops-discord-webhook:latest'
      - '--port'
      - '8000'
```

### Resource Rationale

| Flag | Value | Rationale & Guarantee |
|---|---|---|
| `--max-instances` | `2` | **Arithmetic cost cap**: Caps hourly Cloud Run spend regardless of incoming request spikes. |
| `--min-instances` | `0` | **Scale-to-zero**: Zero billing cost at rest when no traffic is being served. |
| `--concurrency` | `20` | Max simultaneous requests per container instance before spawning second instance. |
| `--timeout` | `30s` | Hard HTTP timeout for all read queries. Prevents hanging sockets. |
| `--cpu` / `--memory` | `1` / `512Mi` | Optimal resource allocation for LadybugDB read-only query serving. |

---

## 2. Public Demo vs Private Deployment Authentication

### Public Demo Deployment
For public demo deployments, Cloud Run runs with `LLMOPS_PLANE=all` to expose both Knowledge plane tools (architecture principles, controls, zero-draft HLD) and Engagement plane tools (maturity boards, interview statements, conflicts, trajectories). The public token (`demo-public-2026-08`) is strictly scoped to the reference demo engagement via `ENGAGEMENT_TOKENS=demo-public-2026-08:nordwave-mcx-2027`. Any attempt to access unauthorized engagements is rejected with a 403 Unauthorised error.

### Private Enterprise Deployment
> [!IMPORTANT]
> For private, internal, or non-public enterprise deployments:
> 1. Do **NOT** use the public demo token.
> 2. Create a dedicated secret in Secret Manager (e.g. `llmops-prod-token`) containing a cryptographically secure 256-bit random string (`openssl rand -hex 32`).
> 3. Deploy Cloud Run with `--set-secrets=SERVER_TOKEN=llmops-prod-token:latest`.
> 4. Ensure `--allow-unauthenticated` is removed or restricted via IAM policies if private ingress is required.

---

## 3. Public Demo Token Rotation Procedure (3 Steps)

When rotating the public demo token (e.g. monthly or quarterly):

### Step 1: Generate New Token String
Generate a new token string following the standard naming convention: `demo-public-YYYY-MM` (e.g., `demo-public-2026-09`).

### Step 2: Add New Version in Secret Manager & Redeploy
```bash
# Add new secret version to Secret Manager (secret name: llmops-auth-token)
echo -n "demo-public-2026-09" | gcloud secrets versions add llmops-auth-token --data-file=-

# Trigger automated build & deployment
gcloud builds submit --config=cloudbuild.yaml .
```

### Step 3: Update Documentation & Commit
Update the public token string across:
- `README.md`
- `README.fr.md`
- `docs/user_manual.md`
- `docs/renderer_integration.md`

Run CI to verify all documentation token references match:
```bash
poetry run pytest tests/contract/test_fixtures_contract.py -v
```

---

## 4. KB Candidate Queue & Review (contract 1.2)

The knowledge base enrichment cycle (`/api/knowledge/candidates`, `kb` CLI) persists candidates outside the knowledge graph.

| Variable | Default | Role |
|---|---|---|
| `CANDIDATES_BACKEND` | `file` | `file` (JSON documents) or `sql` (SQLite / PostgreSQL, see `GOVERNANCE_DATABASE_URL`) |
| `CANDIDATES_DIR` | `data/candidates` | Directory of the `file` backend (ignored by git) |
| `GOVERNANCE_DATABASE_URL` | `sqlite:///data/governance.db` with `sql` | SQLAlchemy URL; `postgresql://…` needs the `postgres` extra (`poetry install -E postgres`). Also holds the owners registry once `kb migrate-governance` was run |
| `LLMOPS_STORAGE_PERSISTENT` | `true` | Set to `false` on an ephemeral (demo) deployment: promotion and publication then warn that written doctrine is lost at restart (`GET /api/knowledge/health` → `storage.mode: demo`) |
| `ENGAGEMENT_TOKENS` | — | Declares reviewer tokens with the `kb:review` scope, e.g. `reviewer-token:kb:review`; a delegating client (Archinex) adds `kb:delegate`: `archinex-token:kb:review,kb:delegate` and sends `X-Actor-Email` |
| `KB_DUPLICATE_THRESHOLD` | `0.6` | Content similarity threshold of the `duplicate` check |
| `KB_NOTIFY_EMAIL_ENABLED`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_STARTTLS` | disabled | E-mail notification of domain owners (`data/kb/owners.yaml`) |
| `NTFY_BASE_URL` | `https://ntfy.sh` | Base URL of the owners' / consumers' ntfy topics |
| `KB_CONSUMER_WEBHOOKS`, `KB_CONSUMER_NTFY_TOPIC` | — | "New version published" notification sent by `kb publish` |

> ⚠️ **Cloud Run file systems are ephemeral.** With the `file` backend, candidates written in the container are lost at the next revision or scale-down. Use `CANDIDATES_BACKEND=sql` with a database that outlives the container (Cloud SQL), then run `kb migrate-governance` once. Promoted assets are still written to `data/kb/` of the container: on an ephemeral demo deployment they are lost at the next restart (known limitation of the demo mode).

The public demo token (`SERVER_TOKEN`) can submit and read candidates (content that failed the anonymization check is redacted) but **cannot review**: reviews require a token carrying the `kb:review` scope. Promotion (`kb promote`) and publication (`kb publish`) are run offline by a maintainer, who then commits `data/kb/`, `data/knowledge.lbug` and the snapshot. `kb remind` can be scheduled (cron) to re-notify owners of candidates waiting more than 5 business days.
