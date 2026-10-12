---
id: NIS2-ART21-2A
title: Risk Analysis and Information System Security Policies
title_fr: Politiques d'analyse des risques et sécurité des systèmes d'information
type: control
framework: NIS2
version: '2022/2555'
jurisdiction: EU
domain: [security-governance, risk-management]
severity: mandatory
target_entities: [essential, important]
status: active
confidence: verified
last_reviewed: 2026-10-12
owner: security-compliance-team
source_ref: Directive (EU) 2022/2555 (NIS 2), Article 21(2)(a)
terms: [risk-analysis, security-baseline, gitops-governance]
source_sha256: c3d39841d58a4f964613a0fa8e7ec332f120516df01f41201e6a5a1d3d78df6b
validated_by: ['@maintainers']
validated_at: '2026-10-12T05:57:55Z'
revision: 2
---

# NIS2-ART21-2A — Risk Analysis and Information System Security Policies

## Regulatory Reference
Directive (EU) 2022/2555 (NIS 2), Article 21, Paragraph 2, Point (a).

## Legal Requirement
Policies on risk analysis and information system security.

## Architecture Acceptance Criteria
- Formal risk identification and architectural threat modeling (e.g. structured risk register linked to interfaces and data flows).
- Definition of an explicit security accreditation boundary and governance of configuration baselines via GitOps.
- Periodic risk re-evaluation and automated triggers for architectural review upon detected configuration or dependency drift.
