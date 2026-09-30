# Contract Versioning Policy & Service Commitment (`schema_version: "1.x"`, current `"1.2"`)

This document defines the semantic versioning rules, stability guarantees, and deprecation policies for the LLMOps FastMCP tool contract.

---

## 1. Version Identifier

Every knowledge summary payload (`get_graph_summary`) and contract specification exposes:

```json
{
  "schema_version": "1.2"
}
```

Clients can inspect this field upon connecting to verify compatibility.

### Version history

| Version | Additions |
|---|---|
| `1.0` | Reference contract (frozen shapes in `tests/contract/frozen/`). |
| `1.1` | `get_doctrine_context` / `GET /api/knowledge/context`, `check_option` / `POST /api/knowledge/check` ([contract §5.1](contracts/knowledge-hub-api-v1.md)). |
| `1.2` | KB candidate cycle: `submit_kb_candidate`, `list_kb_candidates`, `get_kb_candidate`, `review_kb_candidate`, `/api/knowledge/candidates` ([contract §5.2](contracts/knowledge-hub-api-v1.md)); optional `candidate_id` in the suggestion response. |

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
