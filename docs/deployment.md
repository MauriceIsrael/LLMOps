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
| `ENGAGEMENT_TOKENS` | — | **Real engagement data goes in a *managed* engagement** (`POST /api/engagements`, needs the governance database; closed to all but its members in every environment, [contract §5.16](contracts/knowledge-hub-api-v1.md)). Scopes for the client token: `eng:delegate` (acts for the person in `X-Actor-Email`), `eng:service` (reads without a person), `eng:create`. **Unmanaged engagements** stay as below: **Required before any real engagement data** (ADR-KH-01 A10-d-1): without it, outside `LLMOPS_ENV=production`, every authenticated caller reads every engagement and the server logs an `ENGAGEMENT ACCESS IS OPEN` warning at startup; production fails closed. `GET /api/knowledge/engagements` lists only the engagements a token's scopes cover. Declares reviewer tokens with the `kb:review` scope, e.g. `reviewer-token:kb:review`; a delegating client (Archinex) adds `kb:delegate`: `archinex-token:kb:review,kb:delegate` and sends `X-Actor-Email` |
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


### Identity of the people who act (contracts 1.37 and 1.39)

By default the e-mail in `X-Actor-Email` is believed: anyone holding a `kb:delegate` or `eng:delegate` token can act as any expert.
**A shared deployment turns on the strict mode** and declares the keys it trusts:

| Setting | Meaning |
|---|---|
| `LLMOPS_REQUIRE_SIGNED_ACTOR=true` | refuse `X-Actor-Email` (401 `signed_actor_required`, audited); only a signed assertion (`X-Actor-Token`) names a person |
| `ARCHINEX_JWKS` / `ARCHINEX_JWKS_FILE` / `ARCHINEX_JWKS_URL` | public keys of the client that signs (Ed25519 JWKS, inline, a file, or an `https` URL kept 5 min, fail closed) |
| `ARCHINEX_ISSUER`, `ARCHINEX_AUDIENCE` | expected `iss` / `aud` (defaults `archinex`, `knowledge-hub`) |
| `ARCHINEX_ASSERTION_MAX_TTL`, `ARCHINEX_CLOCK_SKEW` | longest accepted lifetime (900 s), clock tolerance (30 s) |
| `LLMOPS_ASSERTION_ROLES_FOR_UNREGISTERED=true` | believe the `roles` / `domain_roles` of a person the experts registry does not know (off: such a person holds no role and is not an expert, like an unknown e-mail in the raw header) |

Order of a switch-over: declare the keys, make the client sign (the Hub keeps accepting the raw header meanwhile), check
`GET /api/knowledge/audit` shows `auth_method: assertion`, then set `LLMOPS_REQUIRE_SIGNED_ACTOR=true`. At start the server logs
how many keys it trusts, and an explicit error if the strict mode is on without any. The replay register is in memory: run one
process, or accept a replay window of the assertion lifetime across processes or restarts. The contract server and the tests
keep the default mode. Details: `docs/contracts/knowledge-hub-api-v1.md` §5.39.

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



## 7. Local semantic search (contract 1.25, issue #94)

The Hub finds the doctrine relevant to a subject whatever its language: a French subject brings up an English control.
It encodes with a **local** model on the processor (`intfloat/multilingual-e5-small`, int8 ONNX, 384 dimensions,
~118 MB, MIT licence) through `fastembed`; no GPU, no extra service, and **no network call at query time**
(`GET /health` → `embedding.local: true`).

| Step | Command |
|---|---|
| Install (dependency `fastembed`) | `poetry install` |
| Fetch the model once (pinned revision, every file checked against its SHA-256) | `poetry run kb models fetch` → `data/models/` (git-ignored) |
| Check | `poetry run kb models status` (`ready`, `absent` or `off`), or `GET /health` → `embedding` |
| Index the base (also done by every publication) | `poetry run kb embeddings index` (needs the governance database) |
| Evaluate (FR→EN set, on demand / nightly) | `make eval-semantic` |

**Behind a proxy that inspects HTTPS** (corporate network, antivirus, WSL that does not see the certificates
installed on Windows), `kb models fetch` fails with `certificate verify failed: self-signed certificate in certificate
chain`. TLS verification is never disabled; use one of:

1. **Trust the proxy's root certificate**: export it as PEM (on Windows: *certmgr.msc* → Trusted Root Certification
   Authorities → the proxy's certificate → Export, Base-64), then
   `export KB_MODELS_CA_BUNDLE=/mnt/c/Users/<me>/proxy-root.pem` and run `poetry run kb models fetch` again
   (`SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` are honoured too). Under WSL you can also add it to the system store:
   `sudo cp proxy-root.pem /usr/local/share/ca-certificates/proxy-root.crt && sudo update-ca-certificates`.
2. **Use a mirror** of huggingface.co (same URL layout): `export KB_MODELS_BASE_URL=https://<mirror>` (or `HF_ENDPOINT`).
3. **Install offline**: `poetry run kb models urls` lists the five files (name, URL, SHA-256); download them with a
   browser into one folder, then `poetry run kb models fetch --from-dir <folder>`. Each file is checked against its
   pinned SHA-256 before it is installed.

`HTTPS_PROXY` / `NO_PROXY` are honoured as usual.

The Docker image fetches and verifies the model at build time, in a cached layer. Without the model (or with
`KB_EMBEDDINGS=off`) the doctrine context is exactly the lexical one (`relevance_method: "lexical"`).

Settings: `KB_EMBEDDINGS=on|off` (default: on when the model is present), `KB_EMBEDDING_MODEL` (default
`intfloat/multilingual-e5-small`), `KB_EMBEDDING_PROVIDER=local` (the only provider of v1), `KB_MODELS_DIR`
(default `data/models`), `KB_EMBEDDING_THREADS` (ONNX threads, default 1: same model, snapshot and query give the same
order), `KB_HYBRID_WEIGHT` (unset: the combined score is `max(lexical, semantic)`; a value w in [0, 1] gives
`w * semantic + (1 - w) * lexical`).

**Calibration** (run of `scripts/eval/eval_semantic_search.py` on `tests/fixtures/similarity/fr-en-doctrine.yaml`,
56 cases: 48 French subjects, 8 English ones). Cosine similarities of the model are mapped onto [0, 1] with the band
[0.70, 0.95]; an asset is `relevant` from a calibrated score of 0.50 (cosine 0.825), and the closest control of each
declared framework from 0.40 (cosine 0.80).

| Measure | Hybrid | Lexical |
|---|---|---|
| Recall at 5 (all / French / English) | 0.90 / 0.88 / 1.00 | 0.72 / 0.67 / 0.92 |
| Expected assets flagged `relevant` | 0.93 | 0.59 |
| Other assets flagged `relevant`, per case | 3.6 | 2.2 |

Measured on a Windows laptop (one ONNX thread, passages encoded one by one so that a vector never depends on the other
texts of its batch): model load with the SHA-256 check ≈ 1.1 s, encoding a query ≈ 2.5 ms (semantic scores of the whole
base ≈ 18 ms), encoding the
93 active assets ≈ 2.5 s (once; the vectors are then read from the `embeddings` table), resident memory ≈ 490 MB
(peak ≈ 540 MB).

The relevance **orders** the package; it never decides whether an option complies (ADR-KH-01 D9): that stays with the
deterministic judge (`checks:` clauses).
