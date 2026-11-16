---
id: NIS2-ART23-4
title: 'Notification timelines: 24h early warning, 72h notification, 1-month final report'
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
source_ref: Directive (EU) 2022/2555 (NIS 2), Article 23(4)
source_sha256: c3d39841d58a4f964613a0fa8e7ec332f120516df01f41201e6a5a1d3d78df6b
validated_by: ['@maintainers']
validated_at: '2026-10-12T05:58:07Z'
revision: 2
title_fr: 'Délais de notification : alerte précoce 24 h, notification 72 h, rapport final à un mois'
terms: [early warning, 24 hours, 72 hours, final report, alerte précoce, 24 heures, 72 heures, rapport final]
satisfied_by: [P-008, PAT-021]
links_production_mode: llm-proposed-human-approved
---

# NIS2-ART23-4 — Notification timelines: 24h early warning, 72h notification, 1-month final report

## Regulatory Reference
Directive (EU) 2022/2555 (NIS 2), Article 23(4).

## Legal Requirement
Member States shall ensure that, for the purpose of notification under paragraph 1, the entities concerned submit to the CSIRT or, where applicable, the competent authority: (a) without undue delay and in any event within 24 hours of becoming aware of the significant incident, an early warning, which, where applicable, shall indicate whether the significant incident is suspected of being caused by unlawful or malicious acts or could have a cross-border impact; (b) without undue delay and in any event within 72 hours of becoming aware of the significant incident, an incident notification, which, where applicable, shall update the information referred to in point (a) and indicate an initial assessment of the significant incident, including its severity and impact, as well as, where available, the indicators of compromise; (c) upon the request of a CSIRT or, where applicable, the competent authority, an intermediate report on relevant status updates; (d) a final report not later than one month after the submission of the incident notification under point (b), including the following: (i) a detailed description of the incident, including its severity and impact; (ii) the type of threat or root cause that is likely to have triggered the incident; (iii) applied and ongoing mitigation measures; (iv) where applicable, the cross-border impact of the incident; (e) in the event of an ongoing incident at the time of the submission of the final report referred to in point (d), Member States shall ensure that entities concerned provide a progress report at that time and a final report within one month of their handling of the incident. By way of derogation from the first subparagraph, point (b), a trust service provider shall, with regard to significant incidents that have an impact on the provision of its trust services, notify the CSIRT or, where applicable, the competent authority, without undue delay and in any event within 24 hours of becoming aware of the significant incident.

## Architecture Acceptance Criteria
- Incident detection, qualification and escalation allow an early warning within 24 hours and an incident notification within 72 hours of becoming aware of a significant incident.
- Indicators of compromise, severity and impact are collected and kept so that the 72-hour notification and the final report within one month can be produced.
- Incident records keep the root cause, mitigation measures and cross-border impact needed for intermediate, progress and final reports.