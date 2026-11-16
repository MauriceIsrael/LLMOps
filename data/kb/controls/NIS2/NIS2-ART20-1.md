---
id: NIS2-ART20-1
title: Management body approval and oversight of risk-management measures
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
source_ref: Directive (EU) 2022/2555 (NIS 2), Article 20(1)
source_sha256: c3d39841d58a4f964613a0fa8e7ec332f120516df01f41201e6a5a1d3d78df6b
validated_by: ['@maintainers']
validated_at: '2026-10-12T05:57:53Z'
revision: 2
title_fr: 'Gouvernance : approbation et supervision des mesures par l''organe de direction'
terms: [management body, governance, risk acceptance, organe de direction, gouvernance cybersécurité, acceptation du risque]
satisfied_by: [PAT-020]
links_production_mode: llm-proposed-human-approved
---

# NIS2-ART20-1 — Management body approval and oversight of risk-management measures

## Regulatory Reference
Directive (EU) 2022/2555 (NIS 2), Article 20(1).

## Legal Requirement
Member States shall ensure that the management bodies of essential and important entities approve the cybersecurity risk-management measures taken by those entities in order to comply with Article 21, oversee its implementation and can be held liable for infringements by the entities of that Article. The application of this paragraph shall be without prejudice to national law as regards the liability rules applicable to public institutions, as well as the liability of public servants and elected or appointed officials.

## Architecture Acceptance Criteria
- The cybersecurity risk-management measures embodied in the architecture (security baseline, residual risks, accepted exceptions) are listed in a register that the management body formally approves.
- Each architecture decision that accepts a cybersecurity risk or deviates from a measure of Article 21(2) names its approver at management-body level and keeps the approval traceable.
- The architecture provides the indicators the management body needs to oversee the implementation of the measures (coverage of the baseline, open findings, incident trends).