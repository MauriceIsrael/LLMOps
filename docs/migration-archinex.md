# Migration guide — engagement interfaces to Archinex

Since contract **1.13**, LLMOps is the **knowledge hub and doctrine authority**; engagements (subjects,
statements, elicitation, arbitration) live in **Archinex**. The interfaces below still answer exactly as before
(same inputs, shapes and status codes) and now announce their deprecation
([policy](DEPRECATION.md)). They remain served for **at least two minor versions** and are removed only with the
written agreement of every consumer and a major version bump.

How to detect a remaining call: each response carries the `Deprecation: true` header, a
`Link: <…>; rel="deprecation"` header and a `deprecation` field; the server logs a `WARNING` on
`mcp_server.deprecation` with the interface and the caller.

## 1. Deprecated interfaces and their equivalent

| LLMOps interface (deprecated) | Equivalent in Archinex |
|---|---|
| `POST /api/elicitation/trigger` | elicitation per subject (lot A2) |
| `GET /api/elicitation/questions` | open questions of a subject (A2) |
| `GET /api/arbitration/board` | subjects maturity board (A3) |
| `GET /api/arbitration/conflicts` | conflicts and arbitration (A3) |
| `GET /api/arbitration/statements` | statements of a subject (A3) |
| MCP `get_subject`, `get_subject_trajectory`, `get_board`, `get_statements`, `get_conflicts`, `get_open_questions` | the corresponding Archinex screens/services (A2, A3) |
| MCP `get_diagram_graph`, `get_render_payload`, `get_dangling_references`, `get_engagement_export` | engagement document, diagrams and export (A4) |

What stays on LLMOps and is **not** deprecated: knowledge (`/api/knowledge/*`, assets, doctrine), candidates and
review, framework ingestion, option judge (`check_option`), similarity and reuse, snapshots, health.

## 2. Legacy (supported, no functional evolution)

`/api/rfp/shred-to-candidates`, `/api/documents/zero-draft-blueprint`, `/api/prose/suggest-batch`, MCP
`shred_rfp`, `generate_zero_draft_hld`, `trigger_rfp_elicitation`, the skills catalogue. They have other
consumers and carry no deprecation signal; do not build new features on them.

## 3. Checklist for the Archinex team

1. Run Archinex against a LLMOps instance and read the `mcp_server.deprecation` log (or grep responses for the
   `Deprecation` header): any line names a call still to remove.
2. Known remaining calls at the time of writing: `LLMOpsClient.getBoard`, `getStatements`, `getConflicts`
   (`src/lib/server/llmops/client.ts`) and `src/routes/api/llmops/+server.ts`. Replace them with Archinex's own
   data, then delete the methods.
3. When no call remains, tell the LLMOps maintainers in writing; removal is then a major-version decision.

## 4. Conflict detection (`CONFLICT_DETECTION_MODE`)

`run_checks` historically flags a conflict when two authors write the **same** value for a predicate. That clause
produces false conflicts. The flag `CONFLICT_DETECTION_MODE` selects the behaviour:

- `legacy` (default, unchanged): current behaviour;
- `strict`: only different values for the same predicate are flagged.

The default will not change without the written agreement of the Archinex team.
