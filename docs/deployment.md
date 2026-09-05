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
      - 'GRAPH_BACKEND=ladybug,LLMOPS_TRANSPORT=sse,LLMOPS_PLANE=knowledge'
      - '--set-secrets'
      - 'SERVER_TOKEN=llmops-demo-token:latest'
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
For public demo deployments, Cloud Run runs with `LLMOPS_PLANE=all` to expose both Knowledge plane tools (architecture principles, controls, zero-draft HLD) and Engagement plane tools (maturity boards, interview statements, conflicts, trajectories). The public token (`demo-public-2026-08`) is strictly scoped to the reference demo engagement (`nordwave-mcx-2027`) via `ENGAGEMENT_TOKENS=demo-public-2026-08:nordwave-mcx-2027`. Any attempt to access unauthorized engagements is rejected with a 403 Unauthorised error.

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
# Add new secret version to Secret Manager
echo -n "demo-public-2026-09" | gcloud secrets versions add llmops-demo-token --data-file=-

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
