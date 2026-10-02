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


## 5. Governance deployment (Archinex integration, contracts 1.4 to 1.8)

The experts act through Archinex, which calls LLMOps with a **service token** and the expert's e-mail
(`X-Actor-Email`). `cloudbuild.yaml` expects the following, created once:

| Resource | Content |
|---|---|
| Cloud SQL (PostgreSQL) instance | Governance state (candidates, reviews, owners registry, evaluations, ingestions). Pass it as `_CLOUDSQL_INSTANCE=PROJECT:REGION:INSTANCE`. |
| Secret `llmops-governance-db-url` | `postgresql://USER:PASSWORD@/DB?host=/cloudsql/PROJECT:REGION:INSTANCE` (the `postgres` extra is installed in the image). |
| Secret `llmops-engagement-tokens` | The whole `ENGAGEMENT_TOKENS` value, e.g. `demo-public-2026-08:nordwave-mcx-2027;ARCHINEX_SERVICE_TOKEN:kb:review,kb:delegate,nordwave-mcx-2027`. Archinex must use `ARCHINEX_SERVICE_TOKEN`; the demo token never carries a governance scope. |

At start the server creates the tables, seeds the owners registry from `data/kb/owners.yaml` when the
database has none (never overwrites it) and imports the evaluation dataset (`pipelines/governance/bootstrap.py`).
**The e-mail addresses and roles of the experts must be filled in** (`owners.yaml` before the first start, or
afterwards `PUT /api/knowledge/owners` with a `kb:admin` token): an expert without a registered e-mail gets `403`.
`kb:maintain` and `kb:admin` are roles of the registry entry of the maintainers.

The demo deployment sets `LLMOPS_STORAGE_PERSISTENT=false`: promoted doctrine written to the container disk is lost
at restart (announced by the API, see §4). Cloud Run is configured with a 300 s request timeout and 1 GiB (source
extraction and graph rebuild).

**Client contract tests**: `make contract-server` starts the real server on a scratch copy with a SQLite governance
database, the service token `contract-service-token` and four test experts (see `scripts/contract_server.py`), so a
client such as Archinex can be tested against the real contract instead of a fake.


## 6. Run the governance server on Linux (or macOS)

Tested here on Linux with the one-command launcher; the `systemd` unit and the Docker commands below are templates that were not run (no systemd service or Docker daemon in the test environment): report any difference.

**Prerequisites**: Python 3.11, Git, a C++ toolchain for the graph engine wheels (`sudo apt-get install -y build-essential g++ curl`),
and Poetry (`curl -sSL https://install.python-poetry.org | python3 -`).

```bash
git clone https://github.com/MauriceIsrael/LLMOps.git /opt/llmops && cd /opt/llmops
poetry config virtualenvs.in-project true && poetry install --no-root     # then: poetry install
cp .env.example .env && chmod 600 .env       # secrets: OWNER_DISCORD_WEBHOOK, SMTP_*, LLMOPS_SERVICE_TOKEN...
poetry run python scripts/serve_local.py --host 0.0.0.0 --port 8000       # foreground; Ctrl+C then rerun = restart
```

**As a service** (restart on failure and at boot). Keep the secrets in `/etc/llmops.env` (mode `600`, owned by root), not in git:

```ini
# /etc/systemd/system/llmops.service
[Unit]
Description=LLMOps knowledge hub (governance server)
After=network.target

[Service]
User=llmops
WorkingDirectory=/opt/llmops
EnvironmentFile=/etc/llmops.env
ExecStart=/opt/llmops/.venv/bin/python scripts/serve_local.py --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo useradd --system --home /opt/llmops llmops && sudo chown -R llmops: /opt/llmops   # the service token file and data/ must be writable
sudo systemctl daemon-reload && sudo systemctl enable --now llmops
sudo systemctl restart llmops          # restart
journalctl -u llmops -f                # logs (the owner notification lines are [KB_CANDIDATE_*])
curl -s http://127.0.0.1:8000/health
```

The launcher prints (and `/opt/llmops/.llmops-local-service-token` keeps) the service token to give to the client
(`LLMOPS_AUTH_TOKEN` in Archinex); to choose it, set `LLMOPS_SERVICE_TOKEN` in `/etc/llmops.env`. For a reverse proxy (TLS), forward
to `127.0.0.1:8000` and keep the `Authorization` and `X-Actor-Email` headers.

**Docker** instead of a service (state in a named volume; set the service token yourself):

```bash
docker build -t llmops:latest .                # the root Dockerfile (same image as Cloud Run); docker/Dockerfile.mcp lacks tools/
docker run -d --name llmops --restart unless-stopped -p 8000:8000 -v llmops-data:/app/data \
  -e SERVER_TOKEN="$(openssl rand -hex 24)" -e ENGAGEMENT_TOKENS="$SERVICE_TOKEN:kb:review,kb:delegate,*" \
  -e CANDIDATES_BACKEND=sql -e GOVERNANCE_DATABASE_URL=sqlite:////app/data/governance.db \
  -e OWNER_DISCORD_WEBHOOK="$OWNER_DISCORD_WEBHOOK" llmops:latest
docker restart llmops
```

Image for client tests (not for deployment): `docker build -f docker/Dockerfile.contract -t llmops-contract:latest .` then
`docker run --rm -p 8099:8000 llmops-contract:latest`.

| Task | Linux / macOS | Windows (PowerShell) |
|---|---|---|
| Start | `poetry run python scripts/serve_local.py` | same |
| Set a secret for the session | `export OWNER_DISCORD_WEBHOOK=…` | `$env:OWNER_DISCORD_WEBHOOK="…"` |
| Persist a secret | `/etc/llmops.env` or `.env` | `setx OWNER_DISCORD_WEBHOOK "…"` (new windows only) or `.env` |
| Free the port | `fuser -k 8000/tcp` | `Get-NetTCPConnection -LocalPort 8000 \| % { Stop-Process -Id $_.OwningProcess }` |
| Make targets | `make serve`, `make verify` | no `make`: use the `poetry run …` commands |

