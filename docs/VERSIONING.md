# Contract Versioning Policy & Service Commitment (`schema_version: "1.x"`, current `"1.21"`)

This document defines the semantic versioning rules, stability guarantees, and deprecation policies for the LLMOps FastMCP tool contract.

---

## 1. Version Identifier

Every knowledge summary payload (`get_graph_summary`) and contract specification exposes:

```json
{
  "schema_version": "1.21"
}
```

Clients can inspect this field upon connecting to verify compatibility.

### Version history

| Version | Additions |
|---|---|
| `1.0` | Reference contract (frozen shapes in `tests/contract/frozen/`). |
| `1.1` | `get_doctrine_context` / `GET /api/knowledge/context`, `check_option` / `POST /api/knowledge/check` ([contract §5.1](contracts/knowledge-hub-api-v1.md)). |
| `1.2` | KB candidate cycle: `submit_kb_candidate`, `list_kb_candidates`, `get_kb_candidate`, `review_kb_candidate`, `/api/knowledge/candidates` ([contract §5.2](contracts/knowledge-hub-api-v1.md)); optional `candidate_id` in the suggestion response. |
| `1.3` | `get_framework_coverage` and the optional `coverage` field of `GET /api/compliance/frameworks/applicable` ([contract §5.3](contracts/knowledge-hub-api-v1.md)). |
| `1.4` | Identity of the acting expert: `X-Actor-Email` header (token with `kb:delegate`), `get_kb_me` / `GET /api/knowledge/me` ([contract §5.4](contracts/knowledge-hub-api-v1.md)); SQL backend of the candidate queue. |
| `1.5` | Review inbox, reassignment, review requests, comments, governance event feed, owners registry ([contract §5.5](contracts/knowledge-hub-api-v1.md)). |
| `1.6` | Doctrine workshop and evaluations: templates, candidate dry run, clause simulation, evaluation dataset/runs, verdict feedback ([contract §5.6](contracts/knowledge-hub-api-v1.md)). |
| `1.7` | Framework ingestion through the API: upload, row review, link proposals, apply, coverage declaration ([contract §5.7](contracts/knowledge-hub-api-v1.md)). |
| `1.8` | Server-side promotion and publication, health indicators ([contract §5.8](contracts/knowledge-hub-api-v1.md)). |
| `1.9` | Semantic similarity over vectors computed by the client: pending texts, vector deposit, hybrid search ([contract §5.9](contracts/knowledge-hub-api-v1.md)). |
| `1.10` | Reuse of validated knowledge: assumptions, reuse confirmations with server-side rules, memory of judgements ([contract §5.10](contracts/knowledge-hub-api-v1.md)). |
| `1.11` | Similarity evaluation: FR/EN annotated dataset, runs with client vectors, threshold sweep ([contract §5.11](contracts/knowledge-hub-api-v1.md)). |
| `1.12` | Bilingual search metadata at ingestion: optional `terms` / `title_fr` in proposals and row decisions ([contract §5.12](contracts/knowledge-hub-api-v1.md)). |
| `1.13` | Deprecation of the engagement part (elicitation / arbitration routes and engagement MCP tools): `Deprecation` header, `deprecation` field, logs; no change of behaviour ([DEPRECATION.md](DEPRECATION.md), [migration guide](migration-archinex.md)). |
| `1.14` | Cancels the 1.13 deprecation (K10, [ADR-KH-01](adr/ADR-KH-01-contrats-exposes.md) A10): the engagement part is in service again, without `Deprecation` header or `deprecation` field. Authorisation answers `403` instead of `500` (K9). |
| `1.15` | Snapshot channel aligned on the suite ([ADR-KH-01](adr/ADR-KH-01-contrats-exposes.md) D6-D8). **K1: all seals follow `canonical-json v1`**; the `payload_sha256` of the sealed snapshot changes value for the same content (it was computed over an indented `json.dumps`), and so can the `checksum` of the conformity snapshot for non-string numbers; shapes unchanged. A value the profile refuses (`NaN`, integer beyond 2^53−1, non-JSON type) now fails the export. **K2: channel envelope** (additive): `emitter`, `checksum`, `rebuiltByEmitterTest`, `regenerate`, `is_provisional`, `provisional_reasons`; a freshness test rebuilds the snapshot from `data/kb`. `frameworks[].version` is now deterministic. **K3: citable versions** — per-element `revision`, `knowledge_ref`, `content`, `content_sha256` in the sealed snapshot; `version-ledger.json`; `GET /api/knowledge/assets/{id}` and `get_asset(id, version?, snapshot?)` resolve from a verified snapshot and refuse an absent version. |
| `1.16` | Managed engagements (K14, [ADR-KH-01](adr/ADR-KH-01-contrats-exposes.md) A11): roles, membership and audit, `/api/engagements*`; a managed engagement is closed to everyone but its members in every environment ([contract §5.16](contracts/knowledge-hub-api-v1.md)). |
| `1.17` | Writing into a managed engagement (K15, [contract §5.17](contracts/knowledge-hub-api-v1.md)): subjects, statements (proposed, then asserted by a decider who is not the author), questions and answers, requirements, conflict arbitration, maturity; idempotent; every write attributed to the member. |
| `1.18` | Sealed snapshot of an engagement (K11, [contract §5.18](contracts/knowledge-hub-api-v1.md)): the Hub emits the engagement channel (suite envelope, canonical-json v1, content-addressed identifier, handles only, `is_provisional` derived); refused when its verification fails. |
| `1.19` | Decisions in the engagement base (K16, [contract §5.19](contracts/knowledge-hub-api-v1.md)): proposed, asserted by a decider who is not the author, superseded; a subject is decided only on an asserted decision (**rule change**: was an asserted statement); the engagement snapshot gains `decisions` (schema `1.1`). |
| `1.20` | Import of an engagement from another system (K12, [contract §5.20](contracts/knowledge-hub-api-v1.md)): dry run, provenance kept, nothing asserted in the batch's name, imported items flagged in the snapshot (schema `1.2`); new `import` action for the `admin` role. |
| `1.21` | Facts carried by decisions (K18, [contract §5.21](contracts/knowledge-hub-api-v1.md)): vocabulary `data/kb/vocabulary/facts.yaml` (section `fact_vocabulary` of the sealed knowledge snapshot, outside `payload_sha256`), `facts` on decisions, `GET /api/engagements/{id}/facts`, engagement snapshot schema `1.3`. |

The sealed snapshot keeps its own format version (`schema_version: "1.0"` in `/snapshot/*`).

---

## 2. Version Increment Rules

We follow Semantic Versioning (`MAJOR.MINOR`) for the tool response contract:

### Minor Version Increments (`1.0` → `1.1`)
A minor version increment occurs when backward-compatible additions are made.
- Adding a new tool to the FastMCP server.
- Adding optional fields to an existing tool response envelope.
- Adding new enum values to non-critical fields.

**Client Guarantee:** Minor updates will **never** break existing integrators or change the type of existing fields.

> ⚠️ **Inputs are part of the contract too.** Adding a *required* parameter to a tool,
> a *required* query parameter or header to a route, or a *required* field to a request
> body is a **breaking** change (existing callers do not send it), even though it looks
> like an "addition". In a minor version, new inputs must be optional and default to
> the previous behaviour. Likewise, narrowing the accepted values of an existing input
> (new validation, shorter enum) is breaking.

### Major Version Increments (`1.0` → `2.0`)
A major version increment occurs when breaking changes are introduced.
- Removing or renaming an existing tool.
- Removing or renaming a required property in an envelope payload.
- Changing the semantic meaning or JSON data type of an existing field.
- Adding a required input (tool parameter, query parameter, header, request-body field).
- Changing the HTTP status code returned by a route for the same request.

**Deprecation Commitment:** Major version changes will be announced at least **6 months** in advance. Legacy endpoints will remain accessible during the transition period. The deprecation mechanics (headers, envelope field, minimum service period) are defined in [`DEPRECATION.md`](DEPRECATION.md).

---

## 3. Stability Guarantees

| Property / Field | Stability Level | Guarantee |
|---|---|---|
| `status` (`ok`, `not_found`, `invalid_argument`, `error`, `unauthorized`) | **Stable** | Guaranteed to remain unchanged in `1.x`. |
| `count` (integer `>= 0`) | **Stable** | Guaranteed to remain unchanged in `1.x`. |
| `data` (payload envelope) | **Stable** | Structure defined by tool schemas in `schemas/`. |
| `confidence` (`verified`, `vendor-stated`, `designed`, `stated-by-client`, `assumed`) | **Stable** | Critical core domain enum. Must be preserved by all client renderers. |
| `subject` level gates (`L0_named` .. `L4_specified`) | **Stable** | Core maturity board enum. |
| Graph node internal IDs | *Transient* | Do not hardcode internal node UUIDs; reference business identifiers (`ADR-xxx`, `P-xxx`, `PAT-xxx`, `Q-xxx`). |

---

## 4. Contract Schemas & Types

- **JSON Schemas**: Available in [`schemas/envelope.schema.json`](../schemas/envelope.schema.json).
- **TypeScript Types**: Available in [`schemas/types.ts`](../schemas/types.ts).
- **Offline Fixtures**: Available in [`fixtures/`](../fixtures/README.md).

---

## 5. Enforcement — frozen interface shapes

The `1.0` contract is enforced mechanically:

- `tests/contract/frozen/` holds the response *shape* of every v1 MCP tool and REST
  route (keys, JSON types, list item shapes) and the HTTP status codes of the routes,
  captured once on the reference code by [`scripts/freeze_interfaces.py`](../scripts/freeze_interfaces.py).
- `tests/contract/test_frozen_interfaces.py` compares the current responses to these
  shapes: a **removed key or a changed type fails**, an added key passes. It also fails
  when a served tool or route is missing from the catalogue, or when a frozen interface
  is no longer served.
- The frozen shapes are **never regenerated** to make the test pass. The script is only
  run with `--only <interface>` to freeze a newly added interface.
- `make verify` (lint + contract + unit tests) runs this check; `make hooks` installs it
  as a git `pre-push` hook.
