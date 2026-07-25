---
id: TPL-mcp-spec
title: Knowledge server specification
type: template
status: active
confidence: verified
phase: [BID, BUILD, RUN]
domain: [ai-assistance]
owner: core-owner-automation
last_reviewed: 2026-07-25
---

# Knowledge server — specification

A read-only Model Context Protocol server over this repository, so that agents
consume **typed assets** rather than fragments of prose retrieved by similarity.

## Why not retrieval over the generated documents

Chunking a design dossier destroys the structure that gives the content meaning:
a principle separated from its verification clause, or a decision separated from
its rejected alternatives, reads as an assertion. An agent then recomposes
something plausible and wrong. Serving whole, typed assets with their metadata
avoids the failure mode entirely, and filtering on `phase` and `domain` is more
precise than semantic search over the same corpus.

## Tools

| Tool | Arguments | Returns |
|---|---|---|
| `list_assets` | `type`, `phase`, `domain`, `status` | Identifiers and titles matching the filter |
| `get_asset` | `id` | The full asset with its front matter |
| `search_assets` | `query`, filters | Whole assets ranked by relevance, never fragments |
| `get_principles_for` | `phase`, `domain` | Active principles with statement and verification clause |
| `get_decision_trail` | `id` | The decision plus what it supersedes and what superseded it |
| `list_open_questions` | `engagement` | Questionnaire items still unanswered in a project instance |
| `get_estimate` | `id`, `work_packages` | Range, variance drivers and any recorded actuals |
| `get_risks_for` | `domain`, `phase` | Register entries with mitigations and materialization history |
| `render_view` | `generator`, `parameters` | A rendered diagram from `views/generators` |
| `draft_asset` | `type`, `content` | A branch and pull request — **never a direct write** |

## Mandatory behaviours

- Only `status: active` assets are returned unless `status` is explicitly set.
- Every response carries the asset's `confidence` and `last_reviewed`. An agent
  that presents an `assumed` item as fact is misusing the base; prompt for it.
- `draft_asset` opens a pull request labelled `agent-drafted`. There is no write
  tool, no exception, and no service account with push rights to `main`.
- Assets under `projects/` are only served when the engagement is named
  explicitly, so that client material never leaks into a generic answer.

## Suggested agent prompt fragment

> Before answering an architecture question, call `get_principles_for` with the
> relevant phase and domain, and `get_decision_trail` for any decision you rely
> on. State the `confidence` of anything you assert. If the base contains no
> asset covering the question, say so and propose a `draft_asset` rather than
> inventing a position.
