---
id: TPL-third-party-integration-guide
title: Third-party integration guide — generating documents, diagrams and interfaces from the knowledge base
type: template
status: active
confidence: verified
phase: [BID, BUILD, RUN]
domain: [ai-assistance, delivery]
owner: core-owner-automation
last_reviewed: 2026-07-29
related: [ADR-0014, ADR-0015, TPL-mcp-spec, TPL-planning-and-demo]
---

# Third-party integration guide

For a team that wants to build its own document generator, diagram renderer or
custom interface on top of this knowledge base, without adopting our CLI or our
templates. Verified against the deployed server on 2026-07-29.

Three things you can do, independently: read the reusable knowledge, inject and
read your own project data, and render either into whatever output format you
need. This guide covers all three, and ends with a list of what to build
yourself because the server does not yet provide it.

---

## 1. The two things you connect to

```
knowledge server   →  data/knowledge.kuzu        principles, decisions, patterns,
                                                   questionnaires, glossary
engagement server  →  data/engagements/<id>.kuzu  subjects, statements, questions,
                                                   conflicts, per project
```

They are two physically separate databases reached through one MCP endpoint.
`query_graph(cypher_query, engagement=None)` reads the knowledge graph when
`engagement` is omitted, and the named engagement's graph when it is supplied. A
single query cannot span both — that is deliberate, not a limitation to work
around. Cross-plane references are identifiers, resolved with `get_assets`, never
graph edges.

**Verify your connection first.**

```python
summary = mcp.call("get_graph_summary", {})
# {"schema_version": "1.0",
#  "knowledge": {"dataset": "...", "node_counts": {"Asset": 46, "GlossaryTerm": 10}},
#  "engagements": [{"id": "nordwave-mcx-2027",
#                    "node_counts": {"Subject": 8, "Statement": 9, "Conflict": 2}}]}
```

If `knowledge.node_counts.Asset` is `0`, the server has not been (re)ingested and
nothing below will work — this has happened during development and is worth
checking before debugging your own code.

---

## 2. Reading the reusable knowledge

```python
mcp.call("list_assets", {"type": "principle", "domain": "ai-assistance"})
mcp.call("search_assets", {"query": "shadow environment validation"})
mcp.call("get_asset", {"id": "ADR-0011"})
mcp.call("get_assets", {"ids": ["ADR-0005", "P-002", "PAT-006"]})     # batch
mcp.call("query_graph", {"cypher_query": "MATCH (a:Asset)-[:DEFINES]->(g) RETURN a,g LIMIT 20"})
```

Every asset response carries `confidence` (`verified` / `vendor-stated` /
`assumed`) and `last_reviewed`. **Any renderer you build must surface these**,
or propagate them into a generated document as a footnote or a colour code. An
asset marked `assumed` rendered with the same visual weight as one marked
`verified` reintroduces exactly the over-claiming problem this base exists to
prevent. This is not a stylistic suggestion — treat it as a functional
requirement of any output format you build.

`list_assets` accepts `type`, `domain`, `phase`, `status` and filters honestly —
verified directly: a domain filter on `ai-assistance` returns only the four
matching principles, not the full fifteen.

---

## 3. Injecting your own project data

This is the part most third parties will want and the part least finished on the
server side. Two paths exist today, at different levels of completeness.

### 3.1 Read path — fully usable today

Once an engagement graph exists, everything is readable:

```python
mcp.call("get_board", {"engagement": "your-engagement"})
mcp.call("get_statements", {"engagement": "your-engagement", "subject": "floor-control"})
mcp.call("get_conflicts", {"engagement": "your-engagement", "status": "open"})
mcp.call("get_open_questions", {"engagement": "your-engagement", "role": "security-architect"})
mcp.call("get_subject_trajectory", {"engagement": "your-engagement", "subject": "mcx-services"})
mcp.call("get_dangling_references", {"engagement": "your-engagement"})
mcp.call("get_render_payload", {"engagement": "your-engagement"})      # see §4
mcp.call("get_engagement_export", {"engagement": "your-engagement"})    # single bulk call (E4)
```

Verified live: an engagement graph with 8 subjects, 9 statements and 2 conflicts
returns rich, correct data through every one of these — including a statement
attributed to an external contributor with `confidence: observed`, and a
detected contradiction (`origin: detected`) correctly distinguished from a
declared one. The maturity board is genuinely rich: level, origin
(`blueprint` vs `discovered`), staleness (`days_at_level`, `is_stalled`) and
which document sections depend on each subject.

### 3.2 Write path — not exposed by MCP, by design

There is no `create_statement` or `submit_answer` tool, and there should not be
one: every write on our side goes through a human confirmation step (the
elicitation flow), which is precisely the guarantee that makes the base
trustworthy. A third party does not get to bypass that by calling a tool.

**What this means for you.** To inject project data, you populate an engagement
Kùzu database directly, following the schema below, or you run our elicitation
engine against your own project (see `TPL-elicitation-proto`) and let it produce
the graph through its own confirmation flow. The second is more work to adopt
and preserves the guarantee; the first is faster and puts the guarantee on you.

### 3.3 The engagement schema, reverse-engineered from live responses

Derived from `get_render_payload` and `get_diagram_graph` output (also published in `docs/SCHEMA.md`):

```
Subject     {name, level, origin ("blueprint"|"discovered"), days_at_level,
             updated_at, is_stalled, open_question_ref, assigned_role,
             dependent_sections[]}

Statement   {id, section, subject, predicate, value, unit,
             author, role, confidence, verbatim, status
             ("active"|"under_review"|"contested"), based_on[]}

Conflict    {id, kind, detail, status ("open"|"arbitrated"), origin
             ("declared"|"detected"), resolution, arbitrated_by}

Uncertainty {id, text, subject}
```

`based_on` is where cross-plane references live: a list of knowledge-base asset
identifiers a statement rests on. Resolve them with `get_assets` in one batch
call rather than one `get_asset` per statement — this is the intended pattern
and it is why `get_assets` exists.

**If you populate the database yourself**, keep confidence and predicate values
from the controlled vocabulary your own tooling defines — nothing enforces this
for you outside the elicitation engine, and an ungoverned predicate vocabulary is
what makes contradiction detection possible or impossible.

---

## 4. Generating documents in your own format

`get_render_payload` is built for exactly this: one call returns the maturity
board, every active statement with its confidence and verbatim, open conflicts,
uncertainties, and the list of subjects not yet mature — everything a renderer
needs, with no further graph traversal required.

```python
payload = mcp.call("get_render_payload", {"engagement": "your-engagement"})
# payload["is_provisional"]        → whether the deliverable is complete
# payload["active_statements"]     → grounds every sentence you write
# payload["open_conflicts"]        → must block a "final" rendering
# payload["unripe_subjects"]       → why it is provisional, if it is
```

### 4.1 The rule that keeps your output honest

`is_provisional` must gate what you claim. A document rendered while conflicts
are open, or while subjects the target sections depend on are below their
required maturity, is a draft — mark it as such visibly, regardless of output
format. This is not a cosmetic nicety: `payload["unripe_subjects"]` exists
specifically so a renderer never has to guess why a document is not finished.

### 4.2 Any output format is a projection of the same payload

Word, PDF, HTML, a slide deck, a wiki page, a PowerPoint — the payload does not
change; only the template does. Concretely:

- **Word / PDF**: one section per document section, statements filtered by
  `section`, rendered as prose with confidence-appropriate wording (`designed` →
  assertive, `stated-by-client` → attributed, `assumed`/`observed` → hedged).
- **Slides**: one slide per subject at or above the maturity your deck requires;
  use `get_subject_trajectory` to build a "how we got here" slide per subject.
- **Wiki / HTML**: render the maturity board as a live table, statements as
  expandable detail with `verbatim` preserved, conflicts as a visible panel
  rather than silently resolved.
- **Diagrams**: `get_diagram_graph` gives you nodes and edges, or Mermaid
  directly.

### 4.3 Mermaid output is valid and safe (Fix E1)

`get_diagram_graph(format="mermaid")` automatically quotes all node and edge target labels and truncates long values with an ellipsis to ensure valid Mermaid syntax across all renderers.

---

## 5. A minimal integration, end to end

```python
kb_id     = "your-engagement"
# Alternatively, use get_engagement_export(kb_id) for a single bulk call (E4)
export    = mcp.call("get_engagement_export", {"engagement": kb_id})
board     = export["data"]["board"]
payload   = export["data"]["render_payload"]
asset_ids = sorted({b["id"] for s in payload["active_statements"]
                    for b in s.get("based_on", [])})
assets    = mcp.call("get_assets", {"ids": asset_ids}) if asset_ids else {"data": []}

doc = render_docx(
    sections=your_blueprint.sections,
    statements=payload["active_statements"],
    conflicts=payload["open_conflicts"],
    provisional=payload["is_provisional"],
    unripe=payload["unripe_subjects"],
    asset_lookup={a["id"]: a for a in assets["data"]},
)
```

Everything on the right-hand side above is a verified, working call as of this
release. `render_docx` — or `_pptx`, `_html`, whatever you build — is the only
part you write.

---

## 6. Server Capabilities & Integration Status

All items from `WORKORDER-THIRD-PARTY-EVOLUTIONS.md` have been implemented:

| Feature / Evolution | Status | Notes / Usage |
|---|---|---|
| Published engagement schema | ✅ Done (E2) | Published in `docs/SCHEMA.md` and enforced by CI |
| Mermaid output quoting | ✅ Fixed (E1) | Quoted and truncated safely in `get_diagram_graph(format="mermaid")` |
| No write path for project data | 🛡️ By Design (E5) | Explicitly documented in `get_graph_summary` tool docstring |
| Stable `schema_version` | ✅ Done (E3) | Exposed as `"schema_version": "1.0"` in `get_graph_summary` payload |
| Single bulk export endpoint | ✅ Done (E4) | `get_engagement_export` tool combines board, payload, and diagram |

We would rather you build against `get_render_payload` and the read tools than
wait for a bulk export — the payload already contains everything, and a single
"export everything" endpoint would just be this guide's minimal integration
moved server-side.

## 7. What not to build

Do not build a write path that bypasses the confirmation flow, even for your own
convenience. Do not cache asset content inside your engagement store — resolve
`based_on` identifiers on read, every time, or your copy will silently diverge
from the knowledge base the day an asset is corrected. Do not render `assumed`
or `stated-by-client` content with the same assertiveness as `verified` content
in your output template — this is the one rule in this guide that is not
negotiable, because it is the entire reason the confidence field exists.
