# Architecture knowledge base

Reusable architecture assets for mission-critical telecom and network automation
engagements, consumable by architects **and** by an agentic framework across the
**BID**, **BUILD** and **RUN** phases.

This repository is the source; documents (HLA instances, design dossiers, slide
decks) are **generated from it**, never the other way round.

## What is in here

| Directory | Asset type | Lifecycle |
|---|---|---|
| `principles/` | Durable architecture principles (P-xxx) | Rarely change; changing one is a significant event |
| `decisions/` | Architecture decision records (ADR-xxxx) | Append-only; superseded, never deleted |
| `patterns/` | Reusable design patterns (PAT-xxx) | Promoted once used twice; amended from field feedback |
| `questionnaires/` | Vendor and platform due-diligence instruments (QST-xxx) | Amended when a question proves useless or missing |
| `estimates/` | Effort models with variance drivers (EST-xxx) | Updated at every project harvest with actuals |
| `risks/` | Risk registers with mitigations (RSK-xxx) | Updated at every project harvest |
| `views/` | Diagram generators as code | Parameterized and reused, not redrawn |
| `templates/` | Document blueprints, section maps, claims register | Stable |
| `projects/` | Client instances: answers, choices, deltas | One directory per engagement |
| `mcp/` | Specification of the read-only knowledge server | Follows the asset schema |

## Start here

- Publishing this for the first time: read `GETTING-STARTED.md`.
- New contributor: read `CONTRIBUTING.md` — it answers *what goes where, and when*.
- Reviewer or owner: read `GOVERNANCE.md`.
- Building an agent on top: read `mcp/SPEC.md`.

## Conventions

Every asset is a Markdown or YAML file with a typed front matter block. The
front matter is what makes the base machine-consumable — see
`schema/frontmatter.schema.json`. CI rejects a file whose front matter does not
validate.

Language of record is English, including for assets first drafted in another
language, so that vendor documentation, tooling and agent prompts stay
consistent.
