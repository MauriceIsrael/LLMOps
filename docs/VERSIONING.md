# Contract Versioning Policy & Service Commitment (`schema_version: "1.x"`, current `"1.40"`)

This document defines the semantic versioning rules, stability guarantees, and deprecation policies for the LLMOps FastMCP tool contract.

---

## 1. Version Identifier

Every knowledge summary payload (`get_graph_summary`) and contract specification exposes:

```json
{
  "schema_version": "1.40"
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
| `1.22` | Question triggers attached to knowledge-base elements (K19, [contract §5.22](contracts/knowledge-hub-api-v1.md)): declarative rules `data/kb/triggers/TRG-*.yaml` over the facts vocabulary, validated at ingestion and publication, citable `trigger:<id>`; section `question_triggers` of the sealed knowledge snapshot (own seal, outside `payload_sha256`). |
| `1.23` | Cascade engine (K20, [contract §5.23](contracts/knowledge-hub-api-v1.md)): decisions open derived subjects from the pinned knowledge snapshot (`origin: derived`, truth maintenance `foundation_contested`), `GET …/lineage`, `PUT …/kb-pin` (admin, new `pin` action), `cascade` report on assert/withdraw/import, mandatory questions closed by a decider with a justification; engagement snapshot schema `1.4` (`lineage`, subject `origin`). |
| `1.24` | Rule adjustments per engagement (K21, [contract §5.24](contracts/knowledge-hub-api-v1.md)): justified deactivation of a reference rule, local rules proposed then asserted by another decider, `GET …/rules`; engagement snapshot schema `1.5` (`rule_adjustments`, lineage `scope`). |
| `1.25` | Local multilingual semantic search (issue #94, [contract §5.25](contracts/knowledge-hub-api-v1.md)): local model on the processor (`fastembed`, `intfloat/multilingual-e5-small`, pinned by SHA-256, no network at query time); `GET /health` → `embedding`; doctrine context items gain `relevant`, `semantic_relevance`, `combined_relevance`, `relevance_method` (package: `relevance_method`, `embedding`); `POST /api/knowledge/similar` encodes `query_text` on the server (`encoded_by`, `409 model-mismatch`); publications index the assets (`embedding_index`); sealed snapshot sections `embedding_model` and `embedding_index` (outside `payload_sha256`). Lexical ranking unchanged without the model. |
| `1.26` | Decision on each check clause (issues #101, #105, [contract §5.26](contracts/knowledge-hub-api-v1.md)): per-clause `status` (`draft`/`validated`/`rejected`) and `review`; `checks_status` becomes an aggregate (`partial` added); promotion never validates a clause; `GET /api/knowledge/checks`, `PATCH /api/knowledge/assets/{asset_id}/checks/{check_id}`; trail `data/kb/clause-decisions.jsonl`; publications list `clause_decisions`. |
| `1.27` | Decision on each requirement and requirements carried by a subject ([contract §5.27](contracts/knowledge-hub-api-v1.md)): `POST /api/engagements/{id}/requirements/{requirement_id}/disposition` (+ `/assert`, `/withdraw`), `POST …/subjects/{name}/requirements`, optional `requirement_ids` on `POST …/subjects`; engagement snapshot schema `1.6` (`requirements[].disposition`, `subjects[].requirement_ids`, both optional: an engagement that uses neither is sealed as before). |
| `1.29` | Trigger rules and facts-vocabulary keys in the candidate cycle, and their review (K22, [contract §5.29](contracts/knowledge-hub-api-v1.md)): candidate types `trigger` and `fact_key`, `kb extract-triggers`, `GET /api/knowledge/triggers`, `POST …/triggers/{validate,preview}`, `POST …/candidates/{id}/merge-key`. |
| `1.30` | Honest conformity snapshot (K6, [contract §5.30](contracts/knowledge-hub-api-v1.md)): no `verified` status, evidence origin `knowledge-hub`, `sourceSystem` not declarative (another `source_system` is refused with `400`). |
| `1.31` | Requirement → control coverage in the engagement snapshot (K17, [contract §5.31](contracts/knowledge-hub-api-v1.md)): section `compliance` (schema `1.7`), statuses `allocated` / `proposed` / `uncovered`, never `verified`, origin `knowledge-hub`. |
| `1.32` | Sealed capitalisation: no programme anchor in the knowledge base (K13, [contract §5.32](contracts/knowledge-hub-api-v1.md)): shared definition of an anchor for the candidate cycle and the reuse journal; engagement identifier, e-mail, member handle and programme front matter field now fail the `anonymization` check. |
| `1.33` | Channel of proposals suite → Hub (K7, [contract §5.33](contracts/knowledge-hub-api-v1.md)): sealed snapshot of proposals read by `kb import-proposals` and `POST /api/knowledge/proposals/import`; provenance on the candidate (`source.snapshot_id`, `snapshot_checksum`, `candidate_ref`); altered snapshot refused whole; idempotent. |
| `1.34` | Capitalisation of a local rule (K21 point 4, [contract §5.34](contracts/knowledge-hub-api-v1.md)): `POST …/rules/{trigger_id}/capitalise` returns a sealed snapshot of proposals (K7, `hub-engagement`), anchor-free (K13); never a direct write. |
| `1.35` | Requirement → control coverage also from the declared chain requirement ← subject ← decision → asset → control ([contract §5.35](contracts/knowledge-hub-api-v1.md)): rows with `basis: "declared_by_decision"` (engagement snapshot schema `1.8`), no matching of text; rows already produced by `matched_controls` unchanged. No route added or changed. |
| `1.36` | Governance freshness monitoring (issue #131), multilingual FR/EN doctrine matching (issue #132), and RFP coverage gap analytics (issue #133): `GET /api/knowledge/freshness` (MCP tool `get_kb_freshness`), enriched bilingual glossary synonyms and clause term expansion (`expand_terms`, `expand_clause_terms`), and RFP coverage blind spots analytics `GET /api/rfp/coverage-gaps`, `POST /api/rfp/coverage-gaps` (MCP tool `get_rfp_coverage_gaps`, and `coverage_gaps` in compliance matrix). K17 decision subject verification fix for matched controls (issue #127) ([contract §5.36](contracts/knowledge-hub-api-v1.md)). |
| `1.37` | Expert authentication and fine-grained RBAC for KB governance (issue #7, [contract §5.37](contracts/knowledge-hub-api-v1.md)): EdDSA (Ed25519) signed actor assertions with published JWKS (RFC 8037), anti-replay protection with mandatory unique `jti`, immediate token/actor revocation, domain-scoped roles, temporary delegations lifecycle (`kb:review`, `kb:evaluate`), strict separation of duties, and access audit logging (`kb_access_audit`). MCP tools: `list_kb_delegations`, `create_kb_delegation`, `revoke_kb_delegation`, `revoke_kb_auth`, `get_kb_audit`. REST routes: `GET /.well-known/jwks.json`, `GET|POST /api/knowledge/delegations`, `POST /api/knowledge/delegations/{id}/revoke`, `POST /api/knowledge/auth/revoke`, `GET /api/knowledge/audit`. |
| `1.38` | Judge reliability (issues #106, #85, [contract §5.38](contracts/knowledge-hub-api-v1.md)), additive: `GET /api/knowledge/context` (`get_doctrine_context`) always returns every control of the required frameworks (`max_items` caps the other doctrine only) and adds `required_total` and `omitted_required`; `GET /api/knowledge/health` (`get_kb_health`) adds `compiled_base` (status `ok`, `stale` or `unverified`: does the compiled graph describe the files?). CLI: `kb check [--strict]`. |
| `1.39` | Identity and rights of the people who act (issues #144, #90, #91, [contract §5.39](contracts/knowledge-hub-api-v1.md)): strict identity mode `LLMOPS_REQUIRE_SIGNED_ACTOR` (raw `X-Actor-Email` refused with 401 `signed_actor_required`), trusted assertion keys from `ARCHINEX_JWKS` / `ARCHINEX_JWKS_FILE` / `ARCHINEX_JWKS_URL`, bounded assertion lifetime and clock tolerance, rights to declare a framework covered, independent application of mandatory controls. No route added. |
| `1.40` | Conformity snapshot made honest and reproducible (issues #148, #149, [contract §5.40](contracts/knowledge-hub-api-v1.md)): `snapshotId` derives from the `checksum` (not the clock); a control no asset declares is `identified`, not `allocated`. Shape (`schemaVersion` `2.0`) unchanged and still refused by the Document Engine reader. No route added. |

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
- `make verify` (lint + types + contract + unit tests) runs this check by hand, and the CI runs it with the whole suite.
  The `pre-push` hook installed by `make hooks` only runs `make quick` (ruff + project-name guard).
