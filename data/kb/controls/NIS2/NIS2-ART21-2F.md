---
id: NIS2-ART21-2F
title: Policies and Procedures to Assess Risk Management Effectiveness
title_fr: Politiques et procédures d'évaluation de l'efficacité des mesures de sécurité
type: control
framework: NIS2
version: '2022/2555'
jurisdiction: EU
domain: [audit, compliance-evaluation]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: 2026-10-12
owner: security-compliance-team
source_ref: Directive (EU) 2022/2555 (NIS 2), Article 21(2)(f)
terms: [continuous-compliance-evaluation, service-plane, infrastructure-plane]
source_sha256: c3d39841d58a4f964613a0fa8e7ec332f120516df01f41201e6a5a1d3d78df6b
validated_by: ['@maintainers']
validated_at: '2026-10-12T05:57:59Z'
revision: 2
---

# NIS2-ART21-2F — Policies and Procedures to Assess Risk Management Effectiveness

## Regulatory Reference
Directive (EU) 2022/2555 (NIS 2), Article 21, Paragraph 2, Point (f).

## Legal Requirement
Policies and procedures to assess the effectiveness of cybersecurity risk-management measures.

## Architecture Acceptance Criteria
- Self-observing operational pipeline: continuous telemetry on auditability, configuration drift, and architectural compliance.
- Strict separation between the service plane and infrastructure plane with unified collection governance.
- Automated collection of compliance evidence for periodic regulatory audits.
