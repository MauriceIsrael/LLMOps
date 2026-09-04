---
id: TPL-glossary
title: Glossary
type: template
status: active
confidence: verified
phase: [BID, BUILD, RUN]
domain: [delivery, governance, security]
owner: maintainers
last_reviewed: 2026-09-04
---

# Glossary

**Break-glass** — procedure allowing critical recovery actions when the
management platform itself is unavailable.

**Claims register** — bid artefact recording the evidence level behind every
statement made in a proposal.

**Closed loop** — chain from detection to remediation. *Supervised* when a human
approval gates the action.

**Continuous compliance evaluation** — automated, ongoing inspection of operational
posture against regulatory and architectural baselines to prevent compliance drift.

**Drift** — difference between the observed configuration of an asset and its
intended configuration.

**Early warning (24h)** — rapid formal notification mechanism triggering an initial
alert to national CSIRTs and stakeholders within 24 hours of detecting a significant incident.

**Essential entity / Important entity** — classification criteria under EU cybersecurity
regulations (NIS 2) defining the stringency of supervisory oversight and mandatory security baselines.

**Fallback plan** — pre-validated configuration applied to recover from a known
degraded condition; bound to the baseline it assumes.

**Harvest** — timeboxed end-of-phase session that returns field experience into
this base.

**Immutable audit log** — tamper-proof recording mechanism (such as WORM storage or
cryptographically signed audit trails) guaranteeing non-repudiation of administrative events.

**Northbound interface** — vendor-exposed management interface through which an
external system operates a domain without bypassing its element manager.

**Security baseline** — documented, version-controlled set of minimum cryptographic,
access, and configuration requirements that every deployed component must meet.

**Service plane / infrastructure plane** — the two observation planes: signals
contributing to a delivered service, and signals describing the hosting platform.

**Shadow environment** — isolated environment receiving duplicated production
telemetry, able to evaluate rules but not to act.

**Source of truth** — the system that holds the intended state; for
configuration, a version control repository.

**Sovereignty boundary** — architectural perimeter ensuring customer key autonomy,
strict EU data localization, and legal immunity against foreign extraterritorial disclosure orders.

**Supply chain security baseline** — mandatory verification of third-party software
provenance, signed Software Bill of Materials (SBOM), and strict vendor boundary enforcement.
