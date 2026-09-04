---
id: NIS2-ART21-2B
title: Incident Handling and Remediation
title_fr: Traitement des incidents
type: control
framework: NIS2
version: "2022/2555"
jurisdiction: EU
domain: [incident-handling, resilience]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: 2026-09-04
owner: security-compliance-team
source_ref: "Directive (EU) 2022/2555 (NIS 2), Article 21(2)(b)"
terms: [incident-handling, closed-loop, early-warning]
---

# NIS2-ART21-2B — Incident Handling and Remediation

## Regulatory Reference
Directive (EU) 2022/2555 (NIS 2), Article 21, Paragraph 2, Point (b).

## Legal Requirement
Incident handling (prevention, detection, and response to incidents).

## Architecture Acceptance Criteria
- Supervised closed-loop automation: automated detection and remediation workflows gated by human validation for critical actions.
- Real-time telemetry routing to CSIRT/SOC with automated early-warning generation (within 24 hours).
- Automated generation of incident post-mortems feeding back into the knowledge base harvest process.
