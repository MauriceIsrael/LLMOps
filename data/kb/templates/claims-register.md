---
id: TPL-claims-register
title: Claims register for proposals
type: template
status: active
confidence: verified
phase: [BID]
domain: [delivery]
owner: core-owner-architecture
last_reviewed: 2026-07-25
---

# Claims register

One row per statement in the proposal that a customer could hold us to. Filled
before the proposal is reviewed, not after.

| # | Claim as written in the proposal | Section | Evidence level | Evidence | Action |
|---|---|---|---|---|---|
| 1 | | | proven / designed / vendor-stated / aspirational | | keep / soften / drop / substantiate |

## Evidence levels

- **proven** — delivered and observed in a production engagement we can name.
- **designed** — designed and validated in a lab or a pre-production environment.
- **vendor-stated** — the vendor documents it; we have not verified it.
- **aspirational** — a target, a roadmap item, or a capability we intend to build.

## Rules

1. Any `aspirational` claim must be reworded as a trajectory ("the architecture
   supports progressing towards...") or dropped. It is never presented as a
   delivered capability.
2. Any `vendor-stated` claim that is load-bearing for the bid must have a
   questionnaire item attached, and the answer must arrive before signature.
3. The register is attached to the bid review pack. A proposal without one is
   not ready for review.

## Why this exists

Autonomous-operations proposals fail technical evaluation for over-claiming far
more often than for under-scoping. The register makes moderation a mechanical
step rather than an argument between the architect and the bid manager.
