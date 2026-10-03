# Using LLMOps from your own client

LLMOps is a knowledge hub (architecture principles, decisions, patterns, regulatory controls, doctrine) with three ways in. Archinex is
one client among others: nothing below is specific to it.

| You want to | Use | Needs |
|---|---|---|
| Query the knowledge, judge an option against the doctrine, search similar decisions | **REST** (`/api/…`) | a token |
| Let an AI agent / IDE use the knowledge as tools | **MCP** (remote SSE or local stdio) | a token (remote) |
| Work offline or cache everything | **Sealed snapshot** (`GET /snapshot/latest`) | a token or a file |
| Contribute knowledge, review it, ingest a regulation | REST with a **governance token** (see §3) | a service token |

## 1. Run a server (or use the demo)

- **Demo instance** (read-only, public token, may be rotated): `https://llmops-mcp-server-344571265365.europe-west1.run.app`, token `demo-public-2026-08`.
- **Your own**: `poetry run python scripts/serve_local.py` (Linux, macOS, Windows), see the [README](../README.md) §4 and [deployment](deployment.md) §6 (systemd, Docker).
- **Throw-away server for client tests**: `poetry run python scripts/contract_server.py --port 8099` or the image `llmops-contract:latest`.

## 2. Connect

All REST calls send `Authorization: Bearer <token>`. Responses share one envelope: `{"status": "ok", "count": n, "data": …}`;
failures carry `status` (`error`, `invalid_argument`, `not_found`, `unavailable`…) and a reason. The contract version is in
`GET /health` → `schema_version`; changes are additive within `1.x` ([versioning](VERSIONING.md), [deprecation](DEPRECATION.md)).

```bash
BASE=http://127.0.0.1:8000; TOKEN=<your token>
curl -s $BASE/health
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/knowledge/search?query=automation&limit=5"
curl -s -H "Authorization: Bearer $TOKEN" "$BASE/api/knowledge/context?subject=network%20automation"
curl -s -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"option":{"id":"o1","title":"Manual CLI changes","summary":"Operators edit routers by hand"},"subject":"network change","domains":["network-automation"]}' \
  "$BASE/api/knowledge/check"          # the option judge: verdict per applicable rule, with the rule and its source
```

```python
import requests
r = requests.get(f"{BASE}/api/knowledge/context", params={"subject": "network automation"},
                 headers={"Authorization": f"Bearer {TOKEN}"}, timeout=30)
r.raise_for_status(); doctrine = r.json()["data"]["items"]   # principles, controls, patterns, ADRs with excerpts
```

```ts
const res = await fetch(`${BASE}/api/knowledge/check`, { method: "POST",
  headers: { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" },
  body: JSON.stringify({ option, subject, domains }) });
const verdicts = (await res.json()).data;
```

Types for TypeScript clients: [`schemas/types.ts`](../schemas/types.ts); JSON Schemas: [`schemas/`](../schemas/).

**MCP** (agent / IDE): remote `{"url": ".../sse", "headers": {"Authorization": "Bearer <token>"}}` or local `poetry run mcp-server-knowledge`
(see the README quickstart). Tools mirror the REST routes (`search_assets`, `get_asset`, `get_doctrine_context`, `check_option`, …).

## 3. Tokens and identity

| Token | Can | Notes |
|---|---|---|
| Public/demo `SERVER_TOKEN` | read, submit candidates | cannot review; content failing the anonymisation check is redacted |
| Service token with `kb:review` | review candidates | declared in `ENGAGEMENT_TOKENS`, e.g. `my-token:kb:review` |
| Service token with `kb:review,kb:delegate` | act **for a person** | the client sends `X-Actor-Email`; LLMOps checks the e-mail against `data/kb/owners.yaml` (roles `kb:maintain`, `kb:admin`, `kb:evaluate`). **The e-mail must come from your authenticated session, never from user input.** |

## 4. REST routes by area

| Area | Routes | Contract |
|---|---|---|
| Knowledge read | `GET /api/knowledge/search`, `GET /api/knowledge/context`, `POST /api/knowledge/check`, `GET /snapshot/latest`, `GET /api/knowledge/templates/{type}` | 1.0, 1.1 |
| Enrichment cycle | `/api/knowledge/candidates…` (submit, review, comment, assign, promote), `GET /api/knowledge/events`, `GET /api/knowledge/reviews/inbox`, owners | 1.2–1.8 |
| Regulations | `/api/frameworks/ingestions…`, `/api/compliance/…`, coverage declaration | 1.7 |
| Similarity and reuse | `/api/knowledge/embeddings`, `/similar`, `/reuse-confirmations`, `/similarity-evals/…` (vectors are computed by **your** client; LLMOps has no model) | 1.9–1.12 |
| Doctrine workshop and evaluations | `/api/knowledge/checks/simulate`, `/evals/…`, `/verdict-feedback` | 1.6 |
| RFP helpers (legacy) | `/api/rfp/shred-to-candidates`, `/api/documents/zero-draft-blueprint` | supported, frozen |
| Writing assistance | `POST /api/prose/suggest-batch` (used by the Document Engine): grounded excerpts of the doctrine, or no draft | 1.x |
| Health, publication | `GET /api/knowledge/health`, `POST /api/knowledge/publications` | 1.8 |
| Engagement part | `/api/elicitation/*`, `/api/arbitration/*` | in service (the 1.13 deprecation was cancelled by 1.14; the Hub holds the engagement base, [ADR-KH-01 A10](adr/ADR-KH-01-contrats-exposes.md)) |

Full specification, bodies and status codes: [`contracts/knowledge-hub-api-v1.md`](contracts/knowledge-hub-api-v1.md); MCP tools and response shapes: [`INTERFACE.md`](INTERFACE.md).

## 5. Know the limits

- No OpenAPI file yet: the contract document and `tests/contract/frozen/` are the references.
- Fetching **one asset by id** is an MCP tool (`get_asset`) or a snapshot lookup; there is no `GET /api/knowledge/assets/{id}` REST route yet.
- Generating documents and diagrams from the knowledge: [third-party integration guide](THIRD-PARTY-INTEGRATION-GUIDE.md) (its engagement-plane sections predate 1.13).
