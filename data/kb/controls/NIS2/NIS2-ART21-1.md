---
id: NIS2-ART21-1
title: Appropriate and proportionate cybersecurity risk-management measures
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
source_ref: Directive (EU) 2022/2555 (NIS 2), Article 21(1)
source_sha256: c3d39841d58a4f964613a0fa8e7ec332f120516df01f41201e6a5a1d3d78df6b
validated_by: ['@maintainers']
validated_at: '2026-10-12T05:57:55Z'
revision: 2
title_fr: Mesures techniques, opérationnelles et organisationnelles appropriées et proportionnées
terms: [risk analysis, proportionate measures, state of the art, analyse de risques, mesures proportionnées, état de l'art]
satisfied_by: [PAT-022]
links_production_mode: llm-proposed-human-approved
---

# NIS2-ART21-1 — Appropriate and proportionate cybersecurity risk-management measures

## Regulatory Reference
Directive (EU) 2022/2555 (NIS 2), Article 21(1).

## Legal Requirement
Member States shall ensure that essential and important entities take appropriate and proportionate technical, operational and organisational measures to manage the risks posed to the security of network and information systems which those entities use for their operations or for the provision of their services, and to prevent or minimise the impact of incidents on recipients of their services and on other services. Taking into account the state-of-the-art and, where applicable, relevant European and international standards, as well as the cost of implementation, the measures referred to in the first subparagraph shall ensure a level of security of network and information systems appropriate to the risks posed. When assessing the proportionality of those measures, due account shall be taken of the degree of the entity’s exposure to risks, the entity’s size and the likelihood of occurrence of incidents and their severity, including their societal and economic impact.

## Architecture Acceptance Criteria
- The architecture is backed by a documented risk analysis of the network and information systems in scope, and each security measure is traceable to the risks it treats.
- The level of the measures is justified against the state of the art and the relevant European or international standards (e.g. ISO/IEC 27001), with the entity's exposure, size and incident likelihood and severity taken into account.
- The architecture states how the impact of an incident on the recipients of the services and on other services is prevented or minimised (isolation, degraded modes, containment).