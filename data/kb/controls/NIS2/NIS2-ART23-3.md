---
id: NIS2-ART23-3
title: Criteria for a significant incident
type: control
framework: NIS2
version: 2022/2555
jurisdiction: EU
domain: [security-governance]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: '2026-11-16'
owner: security-compliance-team
source_ref: Directive (EU) 2022/2555 (NIS 2), Article 23(3)
source_sha256: c3d39841d58a4f964613a0fa8e7ec332f120516df01f41201e6a5a1d3d78df6b
validated_by: ['@maintainers']
validated_at: '2026-10-12T05:58:06Z'
revision: 2
title_fr: Critères d'un incident important
terms: [incident severity, significant incident criteria, gravité de l'incident, seuil d'incident important]
satisfied_by: [PAT-021]
links_production_mode: llm-proposed-human-approved
---

# NIS2-ART23-3 — Criteria for a significant incident

## Regulatory Reference
Directive (EU) 2022/2555 (NIS 2), Article 23(3).

## Legal Requirement
An incident shall be considered to be significant if: (a) it has caused or is capable of causing severe operational disruption of the services or financial loss for the entity concerned; (b) it has affected or is capable of affecting other natural or legal persons by causing considerable material or non-material damage.

## Architecture Acceptance Criteria
- Severity thresholds that make an incident significant (severe operational disruption, financial loss, considerable damage to other persons) are defined per service and implemented in the incident qualification of the monitoring chain.
- The architecture provides the measurements (service availability, number of affected users, duration) needed to apply those thresholds.