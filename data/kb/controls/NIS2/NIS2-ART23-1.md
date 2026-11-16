---
id: NIS2-ART23-1
title: Notification of significant incidents to CSIRT or competent authority
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
source_ref: Directive (EU) 2022/2555 (NIS 2), Article 23(1)
source_sha256: c3d39841d58a4f964613a0fa8e7ec332f120516df01f41201e6a5a1d3d78df6b
validated_by: ['@maintainers']
validated_at: '2026-10-12T05:58:05Z'
revision: 2
title_fr: Notification des incidents importants au CSIRT ou à l'autorité compétente
terms: [significant incident, incident notification, csirt, incident important, notification d'incident, soc, siem]
satisfied_by: [P-008, PAT-021]
links_production_mode: llm-proposed-human-approved
---

# NIS2-ART23-1 — Notification of significant incidents to CSIRT or competent authority

## Regulatory Reference
Directive (EU) 2022/2555 (NIS 2), Article 23(1).

## Legal Requirement
Each Member State shall ensure that essential and important entities notify, without undue delay, its CSIRT or, where applicable, its competent authority in accordance with paragraph 4 of any incident that has a significant impact on the provision of their services as referred to in paragraph 3 (significant incident). Where appropriate, entities concerned shall notify, without undue delay, the recipients of their services of significant incidents that are likely to adversely affect the provision of those services. Each Member State shall ensure that those entities report, inter alia, any information enabling the CSIRT or, where applicable, the competent authority to determine any cross-border impact of the incident. The mere act of notification shall not subject the notifying entity to increased liability. Where the entities concerned notify the competent authority of a significant incident under the first subparagraph, the Member State shall ensure that that competent authority forwards the notification to the CSIRT upon receipt. In the case of a cross-border or cross-sectoral significant incident, Member States shall ensure that their single points of contact are provided in due time with relevant information notified in accordance with paragraph 4.

## Architecture Acceptance Criteria
- The architecture detects incidents and qualifies their significance (impact on the provision of the services, cross-border impact) through centralised security monitoring.
- A notification path to the national CSIRT or competent authority (in Luxembourg, the authority designated under the national NIS2 law) and to affected recipients of the services is defined, with roles and contact points.
- Logs and evidence needed to report the incident and its cross-border impact are retained and protected against tampering.