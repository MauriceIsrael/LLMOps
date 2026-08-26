# LLMOps Offline Fixtures for Third-Party Integrators

> **Guiding Principle:** Develop your document generator, PPTX/DOCX renderer, or web dashboard against these files without installing or running this project.

This directory contains real, machine-validated response payloads exported from the reference engagement `nordwave-mcx-2027` under `schema_version: "1.0"`.

---

## Fixture Files & Corresponding Tool Calls

| Fixture File | Tool / Function Call | Description & Usage |
|---|---|---|
| [`knowledge_snapshot.json`](knowledge_snapshot.json) | `get_graph_summary()` | Summary of the reusable knowledge graph (`data/knowledge.kuzu`), including node counts (`Asset`: 47, `GlossaryTerm`: 10). |
| [`engagement_snapshot.json`](engagement_snapshot.json) | `get_engagement_export(engagement="nordwave-mcx-2027")` | Single bulk export payload combining the maturity board, render payload, and Mermaid diagram for offline rendering. |
| [`get_render_payload.json`](get_render_payload.json) | `get_render_payload(engagement="nordwave-mcx-2027")` | Complete structured payload containing active statements, open conflicts, provisional status, and unripe subjects. |
| [`get_board.json`](get_board.json) | `get_board(engagement="nordwave-mcx-2027")` | Per-subject maturity board showing subject levels (`L0_named` to `L4_specified`), stall indicators, and active statement counts. |
| [`get_diagram_graph.json`](get_diagram_graph.json) | `get_diagram_graph(engagement="nordwave-mcx-2027", format="mermaid")` | Structured graph edges and pre-rendered Mermaid flowchart string ready for visual rendering. |

---

## Schema Version & Verification

All fixtures correspond to `schema_version: "1.0"`.

To re-export these fixtures from the live database or verify against CI:

```bash
poetry run python scripts/export_fixtures.py
```

CI will automatically enforce that committed fixtures do not diverge from the output of `scripts/export_fixtures.py`.
