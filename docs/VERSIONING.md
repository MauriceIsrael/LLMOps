# Contract Versioning Policy & Service Commitment (`schema_version: "1.0"`)

This document defines the semantic versioning rules, stability guarantees, and deprecation policies for the LLMOps FastMCP tool contract.

---

## 1. Version Identifier

Every knowledge summary payload (`get_graph_summary`) and contract specification exposes:

```json
{
  "schema_version": "1.0"
}
```

Clients can inspect this field upon connecting to verify compatibility.

---

## 2. Version Increment Rules

We follow Semantic Versioning (`MAJOR.MINOR`) for the tool response contract:

### Minor Version Increments (`1.0` → `1.1`)
A minor version increment occurs when backward-compatible additions are made.
- Adding a new tool to the FastMCP server.
- Adding optional fields to an existing tool response envelope.
- Adding new enum values to non-critical fields.

**Client Guarantee:** Minor updates will **never** break existing integrators or change the type of existing fields.

### Major Version Increments (`1.0` → `2.0`)
A major version increment occurs when breaking changes are introduced.
- Removing or renaming an existing tool.
- Removing or renaming a required property in an envelope payload.
- Changing the semantic meaning or JSON data type of an existing field.

**Deprecation Commitment:** Major version changes will be announced at least **6 months** in advance. Legacy endpoints will remain accessible during the transition period.

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
