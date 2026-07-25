---
id: TPL-glossary
title: Glossary
type: template
status: active
confidence: verified
phase: [BID, BUILD, RUN]
domain: [delivery]
owner: maintainers
last_reviewed: 2026-07-25
---

# Glossary

**Break-glass** — procedure allowing critical recovery actions when the
management platform itself is unavailable.

**Claims register** — bid artefact recording the evidence level behind every
statement made in a proposal.

**Closed loop** — chain from detection to remediation. *Supervised* when a human
approval gates the action.

**Drift** — difference between the observed configuration of an asset and its
intended configuration.

**Fallback plan** — pre-validated configuration applied to recover from a known
degraded condition; bound to the baseline it assumes.

**Harvest** — timeboxed end-of-phase session that returns field experience into
this base.

**Northbound interface** — vendor-exposed management interface through which an
external system operates a domain without bypassing its element manager.

**Service plane / infrastructure plane** — the two observation planes: signals
contributing to a delivered service, and signals describing the hosting platform.

**Shadow environment** — isolated environment receiving duplicated production
telemetry, able to evaluate rules but not to act.

**Source of truth** — the system that holds the intended state; for
configuration, a version control repository.
