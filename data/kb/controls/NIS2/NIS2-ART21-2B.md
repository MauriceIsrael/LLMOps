---
id: NIS2-ART21-2B
title: Incident Handling and Remediation
title_fr: Traitement des incidents
type: control
framework: NIS2
version: '2022/2555'
jurisdiction: EU
domain: [incident-handling, resilience]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: 2026-10-12
owner: security-compliance-team
source_ref: Directive (EU) 2022/2555 (NIS 2), Article 21(2)(b)
terms: [incident-handling, closed-loop, early-warning]
source_sha256: c3d39841d58a4f964613a0fa8e7ec332f120516df01f41201e6a5a1d3d78df6b
validated_by: ['@maintainers']
validated_at: '2026-10-12T05:57:56Z'
revision: 2
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
