# Deprecation Policy

This document defines how an interface of the LLMOps contract (MCP tool, REST route,
response field, CLI command) is deprecated and eventually withdrawn. It complements
[`VERSIONING.md`](VERSIONING.md).

> **Status (contract `1.0`): no interface is deprecated.**

---

## 1. Principles

1. **Deprecation never changes behaviour.** A deprecated interface keeps the same inputs,
   the same response shape and the same status codes. Only the deprecation signals below
   are added. The frozen-shape contract test (`tests/contract/test_frozen_interfaces.py`)
   keeps running on it unchanged.
2. **Minimum service period.** A deprecated interface remains served for **at least two
   minor versions** after the version that deprecates it (deprecated in `1.2` → still
   served in `1.3` and `1.4`, removable in the next major version at the earliest), and in
   any case for the 6-month notice of a major version change.
3. **No removal without the consumers' agreement.** Removal requires the written
   agreement of every known consumer, and a major version bump.
4. **A replacement is documented before deprecation.** Each deprecated interface points
   to a migration guide (e.g. `docs/migration-archinex.md`).

---

## 2. Signals

### 2.1 HTTP headers (REST routes)

Every response of a deprecated route carries:

```http
Deprecation: true
Link: <https://github.com/MauriceIsrael/LLMOps/blob/main/docs/migration-archinex.md>; rel="deprecation"
```

(`Deprecation` follows RFC 9745; `Link rel="deprecation"` points to the migration guide.)

### 2.2 Envelope field (MCP tools and REST routes)

The response envelope gains an **optional** top-level field `deprecation`, added through
the `**extra` keyword arguments of `ok_response` (`mcp_server/core/envelope.py`):

```python
return ok_response(
    data,
    deprecation={
        "since": "1.2",                       # contract version that deprecated it
        "replaced_by": "archinex:GET /subjects/{id}/board",
        "doc": "docs/migration-archinex.md#arbitration-board",
    },
)
```

```json
{
  "status": "ok",
  "count": 3,
  "data": [ ... ],
  "deprecation": {"since": "1.2", "replaced_by": "...", "doc": "..."}
}
```

The field is optional: clients that ignore unknown keys are unaffected, and the frozen
shapes accept added keys.

### 2.3 Server logs

Each call to a deprecated interface logs a `WARNING` on the `mcp_server.deprecation`
logger with the interface name and the caller, so that remaining consumers can be
identified before removal.

### 2.4 Documentation

The interface is marked *deprecated* in `docs/contracts/knowledge-hub-api-v1.md`, in the
README (EN and FR), and listed in the table below.

---

## 3. Legacy (not deprecated)

An interface may be marked **legacy**: it is still supported and not scheduled for
removal, but receives no functional evolution. Legacy interfaces carry no deprecation
signal.

---

## 4. Register

| Interface | Status | Since | Replaced by | Guide |
|---|---|---|---|---|
| — | — | — | — | — |
